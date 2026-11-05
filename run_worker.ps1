$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$PYTHON = Join-Path $ROOT "venv\Scripts\python.exe"
Write-Host "Starting Queue Worker with $PYTHON..."
& $PYTHON -m apps.worker.main
