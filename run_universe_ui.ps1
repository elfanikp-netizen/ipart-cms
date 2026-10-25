$ErrorActionPreference = "Stop"
$frontend = Join-Path $PSScriptRoot "universe-site\frontend"
Set-Location $frontend

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