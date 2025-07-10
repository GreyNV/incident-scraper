$ErrorActionPreference = 'Stop'
# Change to repository root (directory above this script)
$RepoRoot = Resolve-Path "C:\Users\AndriiRybak\incident-scraper\"
Set-Location $RepoRoot

python fetch_incidents.py
