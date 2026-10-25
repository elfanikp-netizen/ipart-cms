$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\backend

if (-not (Test-Path ".venv")) {
    $python = $null
    foreach ($candidate in @("python", "py")) {
        try {
            $null = Get-Command $candidate -ErrorAction Stop
            $python = $candidate
            break
        } catch { continue }
    }
    if (-not $python) { throw "Python was not found. Install Python 3.10+ first." }
    & $python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
