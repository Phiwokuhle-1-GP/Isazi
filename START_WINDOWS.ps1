param([switch]$ClientDemo, [switch]$LivePayments)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3 -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
Write-Host "Isazi Herbal Shop v2.6.5 - connected store, full shop, accounts and owner operations"
Write-Host "Testimonials: http://127.0.0.1:5000/#testimonials"
Write-Host "Version check: http://127.0.0.1:5000/health"
Write-Host "Store: http://127.0.0.1:5000"
$previousPaymentFlag = $env:DEMO_PAYMENTS_ENABLED
$previousDemoFlag = $env:ISAZI_CLIENT_DEMO
try {
    $env:DEMO_PAYMENTS_ENABLED = if ($LivePayments) { "0" } else { "1" }
    $env:ISAZI_CLIENT_DEMO = "0"
    & ".venv\Scripts\python.exe" app.py
    if ($LASTEXITCODE -ne 0) { throw "The store stopped with an error." }
} finally {
    $env:DEMO_PAYMENTS_ENABLED = $previousPaymentFlag
    $env:ISAZI_CLIENT_DEMO = $previousDemoFlag
}
