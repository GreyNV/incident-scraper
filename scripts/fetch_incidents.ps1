$ErrorActionPreference = 'Stop'
# Change to repository root (directory above this script)
$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $RepoRoot

python fetch_incidents.py
