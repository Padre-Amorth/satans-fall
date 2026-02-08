#!/usr/bin/env bash
set -euo pipefail

echo "== Dev setup helper =="

if ! command -v python >/dev/null 2>&1; then
  echo "Python not found in PATH. Install Python first." >&2
  exit 1
fi

if [ -f requirements-dev.txt ]; then
  echo "Installing dev requirements..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements-dev.txt
else
  echo "requirements-dev.txt not found, skipping pip install."
fi

echo "Installing/upgrading pre-commit and running install hooks..."
python -m pip install --upgrade pre-commit
pre-commit install --install-hooks || true

echo "Running pre-commit hooks across all files (may auto-fix formatting)..."
pre-commit run --all-files || echo "Some hooks reported issues; fix them and re-run 'pre-commit run --all-files'."

echo "Done. You can now develop with pre-commit enabled."