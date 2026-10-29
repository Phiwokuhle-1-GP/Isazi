$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$previousDemoFlag = $env:ISAZI_CLIENT_DEMO
try {
    $env:ISAZI_CLIENT_DEMO = "1"
    Write-Host "ISAZI CLIENT DEMO - sample stock, sample customer accounts and simulated payments"
    Write-Host "Separate demo data: $PSScriptRoot\instance-client-demo"
    Write-Host "No payment provider or email server is contacted."
    & "$PSScriptRoot\START_WINDOWS.ps1" -ClientDemo
} finally {
    $env:ISAZI_CLIENT_DEMO = $previousDemoFlag
}
