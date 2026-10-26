# ISAZI Agile Studio — Windows 11 helper. Run from extracted project folder.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
  Write-Host 'Creating Python virtual environment...' -ForegroundColor Cyan
  py -3 -m venv .venv
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Write-Host 'Installing dependencies (first run needs internet access)...' -ForegroundColor Cyan
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Checking database and admin setup...' -ForegroundColor Green
& $python app.py init
if ($LASTEXITCODE -ne 0) { throw 'Admin initialization failed.' }
Write-Host 'Starting local app: http://127.0.0.1:5000' -ForegroundColor Green
& $python app.py serve
