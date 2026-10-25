$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\frontend

# Ensure Node is available. Prefer system Node; fall back to the portable one.
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    $portable = "C:\ELFANI\tools\node"
    if (Test-Path "$portable\npm.cmd") {
        $env:PATH = "$portable;$env:PATH"
    } else {
        throw "Node.js not found. Install Node, or place portable Node at $portable"
    }
}

if (-not (Test-Path "node_modules")) {
    npm install
}
npm run dev
