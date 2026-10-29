param([switch]$ClientDemo)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$previousDemoFlag = $env:ISAZI_CLIENT_DEMO
try {
    $env:ISAZI_CLIENT_DEMO = "0"
    Write-Host "Resetting the owner for the unified Isazi store."
    Write-Host "Enter and confirm your new password privately (at least 16 characters)."
    & "$PSScriptRoot\CREATE_OWNER.ps1"
    Write-Host "Owner password saved. Start START_WINDOWS.ps1 and open http://127.0.0.1:5000/owner/login"
} finally {
    $env:ISAZI_CLIENT_DEMO = $previousDemoFlag
}
