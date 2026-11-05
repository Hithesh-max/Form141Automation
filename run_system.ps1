#powershell
$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot
$VENV = Join-Path $ROOT "venv"
$ENV_FILE = Join-Path $ROOT ".env"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  FORM 141 AUTOMATION PLATFORM" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --------------------------------------------------
# 1. Check prerequisites
# --------------------------------------------------
Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Yellow

$PYTHON = $null
if (Test-Path "D:\antigrav\FormFilling141\venv\Scripts\python.exe") {
    $PYTHON = "D:\antigrav\FormFilling141\venv\Scripts\python.exe"
} elseif (Test-Path "$VENV\Scripts\python.exe") {
    $PYTHON = "$VENV\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PYTHON = (Get-Command python).Source
} else {
    throw "Python is not installed or available."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm is not installed."
}

# --------------------------------------------------
# 2. Python environment
# --------------------------------------------------
Write-Host "[2/7] Using Python: $PYTHON" -ForegroundColor Green

$PIP = Join-Path (Split-Path $PYTHON) "pip.exe"
if (-not (Test-Path $PIP)) {
    $PIP = "pip"
}

# --------------------------------------------------
# 3. Install Python dependencies + Playwright
# --------------------------------------------------
Write-Host "[3/7] Checking Python dependencies..." -ForegroundColor Yellow

try {
    & $PIP install -r (Join-Path $ROOT "requirements.txt") --quiet
} catch {
    Write-Host "Dependencies check note: $_" -ForegroundColor DarkGray
}

Write-Host "Playwright Chromium check..." -ForegroundColor Green
try {
    & $PYTHON -m playwright install chromium
} catch {
    Write-Host "Playwright install note: $_" -ForegroundColor DarkGray
}

# --------------------------------------------------
# 4. Frontend setup
# --------------------------------------------------
Write-Host "[4/7] Checking frontend..." -ForegroundColor Yellow

$DESKTOP = Join-Path $ROOT "apps\desktop"

Push-Location $DESKTOP

# Node dependencies check
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Green
    npm install
}

Pop-Location

# --------------------------------------------------
# 5. Create .env automatically
# --------------------------------------------------
Write-Host "[5/7] Checking environment configuration..." -ForegroundColor Yellow

if (-not (Test-Path $ENV_FILE)) {

    Write-Host "Creating .env..." -ForegroundColor Green

    $KEY = & $PYTHON -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    $SECRET = [guid]::NewGuid().ToString("N")

    @"
ENV=development

DATABASE_URL=sqlite:///./form141.db

REDIS_URL=redis://localhost:6379/0

MAX_CONCURRENT_JOBS=1
MAX_RETRIES=3
BROWSER_HEADLESS=false
PAGE_TIMEOUT=30000
ELEMENT_TIMEOUT=15000
HEARTBEAT_INTERVAL=5000

WEBSOCKET_RECONNECT=true

SECRET_KEY=$SECRET
ENCRYPTION_MASTER_KEY=$KEY

PORTAL_MODE=real
"@ | Set-Content $ENV_FILE

    Write-Host ".env created successfully." -ForegroundColor Green
}
else {
    Write-Host ".env already exists - keeping existing configuration." -ForegroundColor Green
}

# --------------------------------------------------
# 6. Clean old Python processes
# --------------------------------------------------
Write-Host "[6/7] Cleaning old processes..." -ForegroundColor Yellow

Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1

# --------------------------------------------------
# 7. Start components
# --------------------------------------------------
Write-Host "[7/7] Starting application..." -ForegroundColor Green

# Backend
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ROOT'; `$env:DATABASE_URL='sqlite:///./form141.db'; `$env:REDIS_URL='redis://localhost:6379/0'; `$env:PORTAL_MODE='real'; & '$PYTHON' -m uvicorn apps.backend.app.main:app --host 0.0.0.0 --port 8000"
)

Start-Sleep -Seconds 5

# Worker
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ROOT'; `$env:DATABASE_URL='sqlite:///./form141.db'; `$env:REDIS_URL='redis://localhost:6379/0'; `$env:PORTAL_MODE='real'; & '$PYTHON' -m apps.worker.main"
)

Start-Sleep -Seconds 2

# Frontend
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$DESKTOP'; npm run dev"
)

Start-Sleep -Seconds 3

# --------------------------------------------------
# Open dashboard
# --------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  FORM 141 PLATFORM STARTED" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API:       http://localhost:8000" -ForegroundColor White
Write-Host "API Docs:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "Dashboard: http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Mode:      MOCK PORTAL" -ForegroundColor Yellow
Write-Host "Database:  SQLite" -ForegroundColor Yellow
Write-Host ""
Write-Host "Opening dashboard..." -ForegroundColor Green

Start-Process "http://localhost:5173"
