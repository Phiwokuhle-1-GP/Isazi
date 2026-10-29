param([string]$TargetPath = "")
$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
if (-not (Select-String -LiteralPath (Join-Path $source "templates\home.html") -SimpleMatch "category-shortcuts" -Quiet)) {
    throw "This package does not contain the category strip fix. Download Isazi_Herbal_Shop_V2_6_11_Mobile_About_Footer.zip."
}
if ([string]::IsNullOrWhiteSpace($TargetPath)) {
    $TargetPath = Join-Path $env:USERPROFILE "Downloads\Isazi_Flask_Store\Isazi_Herbal_Shop_V2"
}
if (-not (Test-Path -LiteralPath (Join-Path $TargetPath "app.py"))) {
    throw "Existing app not found at $TargetPath. Run again with -TargetPath followed by your existing Isazi_Herbal_Shop_V2 folder."
}
$target = (Resolve-Path -LiteralPath $TargetPath).Path
$source = (Resolve-Path -LiteralPath $source).Path
if ($source -ne $target) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $target "_update_backups\before-v2.6.11-$stamp"
    $allowed = @("app.py", "performance.py", "video_processing.py", "VIDEO_UPLOADS.md", "optimize_assets.py", "asset_manifest.json", "client_demo.py", "START_DEMO_WINDOWS.ps1", "CLIENT_DEMO_GUIDE.md", "PRODUCTION_HANDOFF.md", "PERFORMANCE_NOTES.md", "PUSH_GITHUB_WINDOWS.ps1", "RELEASE_FILES.json", "ecosystem.py", "payment_gateway.py", "ECOSYSTEM_SETUP.md", "requirements.txt", "README.md", "DEMO_ASSETS.md", "Procfile", "render_start.sh", "wsgi.py", "render.yaml", "START_WINDOWS.ps1", "CREATE_OWNER.ps1", "RESET_OWNER_WINDOWS.ps1", "APPLY_UPDATE.ps1", ".gitignore", ".env.example")
    $files = @(Get-ChildItem -LiteralPath $source -File | Where-Object { $_.Name -in $allowed })
    foreach ($folder in @("templates", "static", "tests")) {
        $folderPath = Join-Path $source $folder
        if (Test-Path -LiteralPath $folderPath) {
            $files += @(Get-ChildItem -LiteralPath $folderPath -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc' })
        }
    }
    # Back up only code files being replaced. Never copy, reset or overwrite runtime data.
    foreach ($file in $files) {
        if ($file.Extension -eq '.zip') { continue }
        $relative = $file.FullName.Substring($source.Length).TrimStart([char[]]@('\','/'))
        $existing = Join-Path $target $relative
        if (Test-Path -LiteralPath $existing) {
            $saved = Join-Path $backup $relative
            New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
            Copy-Item -LiteralPath $existing -Destination $saved -Force
        }
    }
    foreach ($file in $files) {
        if ($file.Extension -eq '.zip') { continue }
        $relative = $file.FullName.Substring($source.Length).TrimStart([char[]]@('\','/'))
        $destination = Join-Path $target $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }
    Write-Host "Previous code backed up to $backup"
}
if (-not (Select-String -LiteralPath (Join-Path $target "app.py") -SimpleMatch "APP_VERSION = '2.6.11'" -Quiet)) {
    throw "Version verification failed. The target was not updated to v2.6.11."
}
foreach ($relative in @("app.py", "client_demo.py", "START_DEMO_WINDOWS.ps1", "templates\base.html", "templates\home.html", "static\css\ecosystem.css", "static\css\mobile.css", "static\images\dr-ntuli-original.png", "static\images\dr-ntuli-hero-enhanced.png", "static\images\hero-landscape-composite.webp", "static\images\dr-ntuli-left-original-v2.png", "static\images\story-video-placeholder.png", "static\images\hero-natural-meadow.webp", "static\images\testimony-audio-cover-1.png", "static\images\testimony-audio-cover-2.png", "static\images\testimony-audio-cover-3.png", "static\images\testimony-audio-cover-4.png")) {
    $expected = (Get-FileHash -LiteralPath (Join-Path $source $relative) -Algorithm SHA256).Hash
    $actual = (Get-FileHash -LiteralPath (Join-Path $target $relative) -Algorithm SHA256).Hash
    if ($actual -ne $expected) { throw "Update verification failed for $relative in $target" }
}
if (-not (Select-String -LiteralPath (Join-Path $target "templates\home.html") -SimpleMatch "category-shortcuts" -Quiet)) { throw "Category strip template is missing." }
Write-Host "Hero photograph and category strip files verified."
Write-Host "Installed Isazi v2.6.11 in $target"
Write-Host "Owner account, database, product stock, orders and uploaded media were preserved."
Write-Host "Stop the previous Flask process with Ctrl+C before starting this updated app."
Write-Host "Normal store: powershell -ExecutionPolicy Bypass -File `"$target\START_WINDOWS.ps1`""
Write-Host "Client presentation: powershell -ExecutionPolicy Bypass -File `"$target\START_DEMO_WINDOWS.ps1`""
Write-Host "Open http://127.0.0.1:5000/health - version must be 2.6.11. Then open the homepage and press Ctrl+F5."
