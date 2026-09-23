<#
.SYNOPSIS
    Starts the flight and calendar MCP servers, then runs the holiday-planning agent
    CLI, or (-Api) the HTTP API that receives REST/SSE calls.
#>

[CmdletBinding()]
param(
    [switch] $Api,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Request
)
$env:AGENT_MODEL = "mock"
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Create it and install requirements.txt first."
}

$servers = @(
    @{ Name = 'flights'; Script = 'servers/flight_server.py'; Port = 3001 },
    @{ Name = 'calendar'; Script = 'servers/calendar_server.py'; Port = 3002 }
)

foreach ($server in $servers) {
    if (Get-NetTCPConnection -LocalPort $server.Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $($server.Port) is already in use. Stop the existing $($server.Name) server first."
    }
}

$processes = @()
try {
    foreach ($server in $servers) {
        Write-Host "Starting $($server.Name) on port $($server.Port)..."
        $processes += Start-Process -FilePath $python -ArgumentList $server.Script `
            -WorkingDirectory $PSScriptRoot -PassThru -NoNewWindow
    }

    foreach ($server in $servers) {
        $url = "http://127.0.0.1:$($server.Port)/health"
        $ready = $false
        foreach ($attempt in 1..30) {
            try {
                Invoke-RestMethod -Uri $url -TimeoutSec 2 | Out-Null
                $ready = $true
                break
            }
            catch {
                Start-Sleep -Milliseconds 500
            }
        }
        if (-not $ready) { throw "$($server.Name) did not become healthy at $url." }
        Write-Host "$($server.Name) is healthy."
    }

    if ($Api) {
        Write-Host "Starting the agent API on http://127.0.0.1:8000 (Ctrl+C to stop)..."
        & $python -m agent.api
    }
    else {
        & $python -m agent.main @Request
    }
}
finally {
    foreach ($process in $processes) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
