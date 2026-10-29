param([string]$CheckoutPath = (Join-Path $env:USERPROFILE "Downloads\Isazi_Git_2611"))
$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
$repoUrl = "https://github.com/Phiwokuhle-1-GP/Isazi.git"
$manifest = Get-Content -LiteralPath (Join-Path $source "RELEASE_FILES.json") -Raw | ConvertFrom-Json
function Invoke-Git {
    param([string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git command failed. No force push was attempted. Resolve the error above, then rerun." }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Install Git for Windows, reopen PowerShell, and run this script again." }
foreach ($file in $manifest) {
    $full = [IO.Path]::GetFullPath((Join-Path $source $file.path))
    if (-not $full.StartsWith($source + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Invalid release path." }
    if ((Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash -ne $file.sha256) { throw "Release verification failed for $($file.path). Extract a fresh copy of the package." }
}
if (-not (Test-Path -LiteralPath $CheckoutPath)) {
    Invoke-Git -GitArgs @("clone", $repoUrl, $CheckoutPath)
}
$checkout = (Resolve-Path -LiteralPath $CheckoutPath).Path
if (-not (Test-Path -LiteralPath (Join-Path $checkout ".git"))) { throw "Checkout folder is not a Git repository. Use a new -CheckoutPath." }
if ($checkout -eq $source) { throw "Run this from the extracted update package, using a separate Git checkout folder." }
Set-Location $checkout
$origin = (& git remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $origin -notin @($repoUrl, "https://github.com/Phiwokuhle-1-GP/Isazi", "git@github.com:Phiwokuhle-1-GP/Isazi.git")) { throw "This checkout does not point to Phiwokuhle-1-GP/Isazi." }
$dirty = & git status --porcelain
if ($LASTEXITCODE -ne 0 -or $dirty) { throw "The publishing checkout has local changes. Preserve or commit them first, or choose a new -CheckoutPath." }
Invoke-Git -GitArgs @("checkout", "main")
Invoke-Git -GitArgs @("pull", "--ff-only", "origin", "main")
$oldHead = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Cannot identify the existing repository head." }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupBranch = "backup/before-store-v2.6.11-$stamp"
Invoke-Git -GitArgs @("branch", $backupBranch, $oldHead)
Write-Host "Publishing backup branch first. GitHub may ask you to sign in."
Invoke-Git -GitArgs @("push", "origin", $backupBranch)
# Only a clean, separate clone is replaced. Installed databases/uploads are untouched.
Invoke-Git -GitArgs @("rm", "-r", "--ignore-unmatch", "--", ".")
foreach ($file in $manifest) {
    $destination = Join-Path $checkout $file.path
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $file.path) -Destination $destination -Force
}
Copy-Item -LiteralPath (Join-Path $source "RELEASE_FILES.json") -Destination (Join-Path $checkout "RELEASE_FILES.json") -Force
Invoke-Git -GitArgs @("add", "--all")
Invoke-Git -GitArgs @("update-index", "--chmod=+x", "render_start.sh")
& git diff --cached --quiet
$diffStatus = $LASTEXITCODE
if ($diffStatus -gt 1) { throw "Unable to inspect staged changes." }
if ($diffStatus -eq 1) {
    $configuredName = & git config user.name
    $configuredEmail = & git config user.email
    if ([string]::IsNullOrWhiteSpace($configuredName) -or [string]::IsNullOrWhiteSpace($configuredEmail)) {
        $authorName = Read-Host "Name for this repository's Git commits"
        $authorEmail = Read-Host "GitHub verified or noreply email for commits"
        if ([string]::IsNullOrWhiteSpace($authorName) -or [string]::IsNullOrWhiteSpace($authorEmail)) { throw "Commit name and email are required." }
        Invoke-Git -GitArgs @("config", "user.name", $authorName)
        Invoke-Git -GitArgs @("config", "user.email", $authorEmail)
    }
    Invoke-Git -GitArgs @("commit", "-m", "V2.6.11: start mobile homepage with About Dr Ntuli and tidy footer")
} else { Write-Host "Repository already contains this release." }
Invoke-Git -GitArgs @("push", "origin", "main")
$newHead = (& git rev-parse HEAD).Trim()
$remoteLine = & git ls-remote origin refs/heads/main
if ($LASTEXITCODE -ne 0 -or ($remoteLine -split '\s+')[0] -ne $newHead) { throw "Remote verification failed. Check GitHub before deploying." }
Write-Host "Verified GitHub main: $newHead"
Write-Host "Previous version retained on $backupBranch"
Write-Host "Latest local Git checkout: $checkout"
Write-Host "Repository: https://github.com/Phiwokuhle-1-GP/Isazi"
Write-Host "A Render auto-deploy may start if enabled. Check its logs and /health separately."
