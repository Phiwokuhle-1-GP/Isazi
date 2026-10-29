$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3 -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& ".venv\Scripts\python.exe" -m flask --app app create-owner
if ($LASTEXITCODE -ne 0) { throw "Owner creation did not complete." }
