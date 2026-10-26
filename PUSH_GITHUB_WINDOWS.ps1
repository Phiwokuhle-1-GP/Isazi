param(
  [Parameter(Mandatory=$true)]
  [string]$RepoUrl
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($RepoUrl -notmatch '^https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+(\.git)?$') {
    throw 'Use a new GitHub repository HTTPS URL, e.g. https://github.com/YOUR_USER/isazi-herbal-shop-portal.git'
}
if (Test-Path '.git') {
    throw 'This folder already has a Git repository. Inspect it manually instead of recreating or force pushing.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git for Windows is not installed or not on your PATH.'
}
Write-Host 'Preparing a new Git repository; local database and .env are ignored.'
git init -b main
if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
git add .
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
$ignored = git status --short --ignored
if ($ignored -match '!! instance[\\/]isazi.sqlite3' -or $ignored -match '!! .env') {
    Write-Host 'Local SQLite and/or .env files are excluded by .gitignore.'
}
git commit -m 'Prepare Isazi client portal V4.2 for secure Render deployment'
if ($LASTEXITCODE -ne 0) { throw 'Git commit failed. Set git user.name and user.email if requested.' }
git remote add origin $RepoUrl
if ($LASTEXITCODE -ne 0) { throw 'Adding remote failed' }
Write-Host 'Pushing to GitHub using the normal Git credentials prompt...'
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'GitHub push failed. Check repository URL, permissions and authentication.' }
Write-Host 'Source pushed successfully. In Render select New > Blueprint and connect this repository.'
