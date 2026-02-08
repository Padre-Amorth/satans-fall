<#
PowerShell helper: initialize git, create branch, commit, install pre-commit hooks,
run pre-commit across files, and push branch to remote.

Usage (interactive):
  .\scripts\setup_ci.ps1

Usage (non-interactive):
  .\scripts\setup_ci.ps1 -RemoteUrl "https://github.com/you/yourrepo.git" -Branch "ci-setup"

Notes:
  - Requires Git, Python, and pip available in PATH.
  - If your repo root is different, run the script from the repo root directory.
#>

param(
    [string]$RemoteUrl = "",
    [string]$Branch = "ci-setup"
)

function FailExit($msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

Write-Host "== CI setup helper ==" -ForegroundColor Cyan

# Verify Git
try {
    $gitVersion = git --version 2>&1
} catch {
    FailExit "Git is not installed or not in PATH. Install Git first: https://git-scm.com/downloads"
}
Write-Host "Git available: $gitVersion"

# Verify we're in repo root-ish
if (-not (Test-Path './README.md')) {
    $cont = Read-Host "README.md not found in current directory. Are you in the repo root? Type Y to continue anyway"
    if ($cont -ne 'Y' -and $cont -ne 'y') { FailExit "Run the script from the repository root." }
}

# Initialize repo if needed
if (-not (Test-Path '.git')) {
    Write-Host "Initializing new git repository..." -ForegroundColor Yellow
    git init || FailExit "git init failed"
} else {
    Write-Host ".git already exists — using existing repository" -ForegroundColor Green
}

# Determine branch
if (-not $Branch -or $Branch -eq '') {
    $Branch = Read-Host "Enter branch name to create (default 'ci-setup')"
    if (-not $Branch -or $Branch -eq '') { $Branch = 'ci-setup' }
}

# Create or switch to branch
Write-Host "Creating/switching to branch '$Branch'..." -ForegroundColor Yellow
$existingBranches = git branch --list $Branch
if ($existingBranches) {
    git checkout $Branch || FailExit "Failed to checkout existing branch $Branch"
} else {
    git checkout -b $Branch || FailExit "Failed to create branch $Branch"
}

# Stage files
Write-Host "Staging all changed files..." -ForegroundColor Yellow
git add -A

# Commit if there are staged changes
$porcelain = git status --porcelain
if (-not [string]::IsNullOrWhiteSpace($porcelain)) {
    $message = Read-Host "Enter commit message (default: 'chore: add CI, linters, pre-commit')"
    if (-not $message -or $message -eq '') { $message = "chore: add CI, linters, pre-commit" }
    git commit -m "$message" || FailExit "Commit failed"
    Write-Host "Committed changes." -ForegroundColor Green
} else {
    Write-Host "No changes to commit." -ForegroundColor Yellow
}

# Remote handling
if (-not $RemoteUrl -or $RemoteUrl -eq '') {
    $RemoteUrl = Read-Host "Enter remote URL to push to (e.g. https://github.com/you/repo.git). Leave blank to skip push"
}

if ($RemoteUrl -and $RemoteUrl -ne '') {
    $originUrl = git remote get-url origin 2>$null
    if ($originUrl) {
        Write-Host "Remote 'origin' already exists: $originUrl" -ForegroundColor Yellow
        $useOrigin = Read-Host "Replace origin with $RemoteUrl? (y/N)"
        if ($useOrigin -eq 'y' -or $useOrigin -eq 'Y') {
            git remote set-url origin $RemoteUrl || FailExit "Failed to set remote URL"
            Write-Host "Updated origin URL." -ForegroundColor Green
        } else {
            Write-Host "Keeping existing origin." -ForegroundColor Yellow
        }
    } else {
        git remote add origin $RemoteUrl || FailExit "Failed to add remote origin"
        Write-Host "Added remote origin: $RemoteUrl" -ForegroundColor Green
    }

    Write-Host "Pushing branch '$Branch' to origin..." -ForegroundColor Yellow
    git push -u origin $Branch || FailExit "git push failed; please check your credentials and remote URL"
    Write-Host "Branch pushed." -ForegroundColor Green
} else {
    Write-Host "No remote specified, skipping push." -ForegroundColor Yellow
}

# Ensure Python and pip available
try {
    $py = python --version 2>&1
    Write-Host "Python available: $py" -ForegroundColor Green
} catch {
    Write-Host "Python not found in PATH. Skipping pre-commit installation. Install Python and run: pre-commit install --install-hooks" -ForegroundColor Yellow
    exit 0
}

# Install/enable pre-commit
Write-Host "Installing pre-commit (if missing) and running hooks..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install --upgrade pre-commit

# Install hooks
pre-commit install --install-hooks
if ($LASTEXITCODE -ne 0) { Write-Host "pre-commit install returned non-zero status" -ForegroundColor Yellow }

# Run hooks against all files
pre-commit run --all-files
if ($LASTEXITCODE -ne 0) {
    Write-Host "Some pre-commit hooks reported issues. Fix them, then re-run 'pre-commit run --all-files' and commit the fixes." -ForegroundColor Red
} else {
    Write-Host "pre-commit hooks passed and auto-fixed issues where possible." -ForegroundColor Green
}

# Run tests
Write-Host "Running test suite (pytest) ..." -ForegroundColor Yellow
python -m pytest -q
if ($LASTEXITCODE -eq 0) {
    Write-Host "All tests passed." -ForegroundColor Green
} else {
    Write-Host "Tests failed (exit code $LASTEXITCODE). Fix failing tests before merging." -ForegroundColor Red
}

Write-Host "Done. Review remote branch and open a PR on GitHub when ready." -ForegroundColor Cyan
