Set-Location $PSScriptRoot
$env:DATABASE_URL = "sqlite:///./form141.db"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:PORTAL_MODE = "real"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  FORM 141 FASTAPI BACKEND (PORT 8001)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

& "D:\antigrav\FormFilling141\venv\Scripts\python.exe" -m uvicorn apps.backend.app.main:app --host 0.0.0.0 --port 8001
