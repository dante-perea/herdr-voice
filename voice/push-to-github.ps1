# Create/push dante-perea/herdr-voice once GitHub auth for that account works.
# Usage:  .\voice\push-to-github.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Checking gh auth..."
gh auth status
gh api user --jq .login

$origin = "https://github.com/dante-perea/herdr-voice.git"
git remote remove origin 2>$null
git remote add origin $origin
git remote add upstream https://github.com/ogulcancelik/herdr.git 2>$null

# Create empty repo if missing (user/org must match authenticated account ownership)
$exists = $true
try {
  gh api "repos/dante-perea/herdr-voice" --jq .full_name | Out-Null
} catch {
  $exists = $false
}

if (-not $exists) {
  Write-Host "Creating dante-perea/herdr-voice..."
  gh repo create dante-perea/herdr-voice --public --description "herdr fork with Grok Voice Think Fast 2.0 control" --source=. --remote=origin --push
} else {
  Write-Host "Pushing master to origin..."
  git push -u origin master
}

Write-Host "Done. Remote:"
git remote -v
git log origin/master -1 --oneline
