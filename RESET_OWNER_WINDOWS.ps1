param([switch]$ClientDemo)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$previousDemoFlag = $env:ISAZI_CLIENT_DEMO
try {
    if ($ClientDemo) {
        $env:ISAZI_CLIENT_DEMO = "1"
        Write-Host "Resetting the CLIENT DEMO owner only. Normal store owner is unchanged."
    } else {
        $env:ISAZI_CLIENT_DEMO = "0"
        Write-Host "Resetting the NORMAL STORE owner only. Demo owner is unchanged."
    }
    Write-Host "Enter and confirm your new password privately (at least 16 characters)."
    & "$PSScriptRoot\CREATE_OWNER.ps1"
    Write-Host "Owner password saved. Sign in at http://127.0.0.1:5000/owner/login"
    if ($ClientDemo) { Write-Host "Start START_DEMO_WINDOWS.ps1 to use this owner." }
    else { Write-Host "Start START_WINDOWS.ps1 to use this owner." }
} finally {
    $env:ISAZI_CLIENT_DEMO = $previousDemoFlag
}
