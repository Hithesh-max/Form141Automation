@echo off
title Form 141 Automation Platform Launcher
cd /d "%~dp0"

echo ============================================
echo   FORM 141 AUTOMATION PLATFORM LAUNCHER
echo ============================================
echo.

echo [1/3] Starting FastAPI Backend (Port 8001)...
start "Form 141 - Backend" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0start_backend.ps1"

ping 127.0.0.1 -n 4 >nul

echo [2/3] Starting Worker...
start "Form 141 - Worker" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0start_worker.ps1"

ping 127.0.0.1 -n 3 >nul

echo [3/3] Starting Desktop UI (Port 5173)...
start "Form 141 - UI" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0start_frontend.ps1"

ping 127.0.0.1 -n 3 >nul

echo.
echo Opening browser: http://localhost:5173
start http://localhost:5173

echo.
echo ============================================
echo   ALL 3 SERVICES LAUNCHED!
echo   Backend: http://localhost:8001
echo   UI:      http://localhost:5173
echo.
echo   Login with:
echo     Username: admin
echo     Password: admin123
echo ============================================
echo.
