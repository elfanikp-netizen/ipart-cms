$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "universe-site\backend"
Set-Location $backend

$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    } else {
        throw "Python 3 was not found. Install Python and retry."
    }
}

if (-not (Test-Path (Join-Path $backend ".venv\Scripts\uvicorn.exe"))) {
    & $python -m pip install -r requirements.txt
}

& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8002