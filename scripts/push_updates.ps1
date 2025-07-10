$ErrorActionPreference = 'Stop'
# Change to repository root
$RepoRoot = Resolve-Path "C:\Users\AndriiRybak\incident-scraper\"
Set-Location $RepoRoot

# Stage updated incident file
git add incidents.json

# Check if there is anything to commit
$changes = git status --porcelain
if ($changes) {
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    git commit -m "Update incidents $timestamp"
    git push
}
