$ErrorActionPreference = "Continue"

$manifestPath = Join-Path $PSScriptRoot ".portal-apps-processes.json"
$ports = @(8001, 8000, 8002, 5173, 5174, 5175)
$processIds = [System.Collections.Generic.HashSet[int]]::new()

if (Test-Path $manifestPath) {
    try {
        $tracked = @(Get-Content -Path $manifestPath -Raw | ConvertFrom-Json)
        foreach ($entry in $tracked) {
            if ($entry.ProcessId) {
                $launcherProcess = Get-CimInstance Win32_Process `
                    -Filter "ProcessId = $([int]$entry.ProcessId)" `
                    -ErrorAction SilentlyContinue
                if ($launcherProcess.CommandLine -and
                    $launcherProcess.CommandLine.IndexOf($PSScriptRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
                    $launcherProcess.CommandLine -match "(?i)-File") {
                    $null = $processIds.Add([int]$entry.ProcessId)
                }
            }
        }
    } catch {
        Write-Warning "Could not read the previous start manifest; checking app ports instead."
    }
}

foreach ($port in $ports) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        if ($listener.OwningProcess -gt 0) {
            $null = $processIds.Add([int]$listener.OwningProcess)
        }
    }
}

$taskkill = Join-Path $env:WINDIR "System32\taskkill.exe"
foreach ($processId in $processIds) {
    & $taskkill /F /T /PID $processId 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Stopped process tree $processId."
    }
}

Remove-Item -Path $manifestPath -Force -ErrorAction SilentlyContinue
if ($processIds.Count -eq 0) {
    Write-Host "No tracked service processes or listeners were found."
} else {
    Write-Host "Stop request sent for $($processIds.Count) process tree(s)."
}