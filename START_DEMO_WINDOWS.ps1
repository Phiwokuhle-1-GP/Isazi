$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "Starting the unified Isazi store with simulated payments."
& "$PSScriptRoot\START_WINDOWS.ps1"
