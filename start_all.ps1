$ErrorActionPreference = "Stop"

$manifestPath = Join-Path $PSScriptRoot ".portal-apps-processes.json"
$services = @(
    @{ Name = "Portal API"; Port = 8001; Script = "run_portal_api.ps1" },
    @{ Name = "Scraper API"; Port = 8000; Script = "scrapper-site\run_api.ps1" },
    @{ Name = "Universe API"; Port = 8002; Script = "run_universe_api.ps1" },
    @{ Name = "Scraper UI"; Port = 5173; Script = "scrapper-site\run_ui.ps1" },
    @{ Name = "Portal UI"; Port = 5174; Script = "run_portal.ps1" },
    @{ Name = "Universe UI"; Port = 5175; Script = "run_universe_ui.ps1" }
)

$powerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$started = @()

foreach ($service in $services) {
    $launcher = Join-Path $PSScriptRoot $service.Script
    if (-not (Test-Path $launcher)) {
        throw "Launcher not found for $($service.Name): $launcher"
    }

    $listener = Get-NetTCPConnection -State Listen -LocalPort $service.Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        Write-Host "$($service.Name) already has a listener on port $($service.Port); skipping."
        continue
    }

    $process = Start-Process -FilePath $powerShell `
        -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$launcher`"") `
        -WorkingDirectory $PSScriptRoot `
        -PassThru
    $started += [PSCustomObject]@{
        Name = $service.Name
        Port = $service.Port
        ProcessId = $process.Id
    }
    ConvertTo-Json -InputObject $started -Depth 3 | Set-Content -Path $manifestPath -Encoding UTF8
    Write-Host "Started $($service.Name) in a new window (port $($service.Port), PID $($process.Id))."
}

if ($started.Count -eq 0) {
    Write-Host "No new service windows were started."
} else {
    Write-Host "All available services have been launched. Open http://localhost:5174 when ready."
}