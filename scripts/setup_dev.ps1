<#
PowerShell helper: setup development environment quickly.

Usage:
  .\scripts\setup_dev.ps1

This script will:
  - Install dev requirements from requirements-dev.txt
  - Install/upgrade pre-commit
  - Install pre-commit hooks
  - Run pre-commit on all files (auto-fix where possible)
#>

function FailExit($msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

Write-Host "== Dev setup helper ==" -ForegroundColor Cyan

# Check for Python
try {
    $py = python --version 2>&1
    Write-Host "Python available: $py" -ForegroundColor Green
} catch {
    FailExit "Python is not available in PATH. Install Python before running this script."
}

# Install dev dependencies
if (-not (Test-Path './requirements-dev.txt')) {
    Write-Host "requirements-dev.txt not found, skipping pip install." -ForegroundColor Yellow
} else {
    Write-Host "Installing dev requirements..." -ForegroundColor Yellow
    python -m pip install --upgrade pip
    python -m pip install -r requirements-dev.txt || FailExit "Failed to install dev requirements"
}

# Install and enable pre-commit
Write-Host "Installing/upgrading pre-commit and running install hooks..." -ForegroundColor Yellow
python -m pip install --upgrade pre-commit
pre-commit install --install-hooks
if ($LASTEXITCODE -ne 0) { Write-Host "pre-commit install returned non-zero status" -ForegroundColor Yellow }

# Run hooks across repository
Write-Host "Running pre-commit hooks across all files (this may auto-fix formatting)..." -ForegroundColor Yellow
pre-commit run --all-files
if ($LASTEXITCODE -ne 0) {
    Write-Host "Some pre-commit hooks reported issues. Fix them and re-run 'pre-commit run --all-files'." -ForegroundColor Red
} else {
    Write-Host "pre-commit hooks ran and auto-fixed issues where possible." -ForegroundColor Green
}

Write-Host "Done. You can now develop with pre-commit enabled." -ForegroundColor Cyan
