Set-Location (Join-Path $PSScriptRoot "apps\desktop")

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  FORM 141 DESKTOP FRONTEND (PORT 5173)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

npm run dev
