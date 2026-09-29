<#

A single POST isn't enough for an MCP server over HTTP. The script does it in three steps:

initialize: the server replies with an Mcp-Session-Id header.
notifications/initialized, then your request (such as tools/call), both sent with that session id. The reply may come back as JSON or as an event stream (data: {...} lines); the script handles both.
DELETE to close the session.

.SYNOPSIS
    Calls one tool on the calendar MCP server (port 3002) over raw streamable HTTP.

.EXAMPLE
    .\call_calendar.ps1
    .\call_calendar.ps1 -Tool check_availability -Arguments @{ start_date = '2026-10-01'; end_date = '2026-10-05' }
    .\call_calendar.ps1 -Tool create_event -Arguments @{ title = 'Holiday: Paris'; start_date = '2026-10-07'; end_date = '2026-10-10' }
    .\call_calendar.ps1 -Tool delete_event -Arguments @{ event_id = 'EVT-000004' }
    .\call_calendar.ps1 -Method tools/list
    .\call_calendar.ps1 -Method resources/read -Params @{ uri = 'calendar://config' }
#>
[CmdletBinding()]
param(
    [string] $Tool = 'list_events',
    [hashtable] $Arguments,
    [string] $Method = 'tools/call',
    [hashtable] $Params,
    [string] $Url = 'http://127.0.0.1:3002/mcp'
)

$ErrorActionPreference = 'Stop'

if (-not $Arguments) {
    $today = Get-Date
    $Arguments = @{
        start_date = $today.ToString('yyyy-MM-dd')
        end_date   = $today.AddDays(60).ToString('yyyy-MM-dd')
    }
}
if (-not $Params) {
    $Params = if ($Method -eq 'tools/call') { @{ name = $Tool; arguments = $Arguments } } else { @{} }
}

$headers = @{ Accept = 'application/json, text/event-stream' }

function Send-Mcp([hashtable] $Body) {
    $response = Invoke-WebRequest -Method Post -Uri $Url -Headers $headers `
        -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Depth 10 -Compress)
    # The server answers either with plain JSON or with a single SSE "data:" line.
    $text = $response.Content
    if ($response.Headers['Content-Type'] -match 'event-stream') {
        $text = ($text -split "`n" | Where-Object { $_ -like 'data:*' } | Select-Object -Last 1).Substring(5)
    }
    return @{ Response = $response; Json = if ($text) { $text | ConvertFrom-Json } }
}

# 1. Handshake: initialize returns the session id every later request must carry.
$init = Send-Mcp @{
    jsonrpc = '2.0'; id = 1; method = 'initialize'
    params  = @{
        protocolVersion = '2025-06-18'
        capabilities    = @{}
        clientInfo      = @{ name = 'call_calendar.ps1'; version = '1.0' }
    }
}
$sessionId = $init.Response.Headers['Mcp-Session-Id'] | Select-Object -First 1
if ($sessionId) { $headers['Mcp-Session-Id'] = $sessionId }
$headers['MCP-Protocol-Version'] = $init.Json.result.protocolVersion
Write-Host "Connected to $($init.Json.result.serverInfo.name) (session $sessionId)"

Send-Mcp @{ jsonrpc = '2.0'; method = 'notifications/initialized' } | Out-Null

# 2. The actual request.
Write-Host "-> $Method $($Params | ConvertTo-Json -Depth 10 -Compress)" -ForegroundColor Red
$result = (Send-Mcp @{ jsonrpc = '2.0'; id = 2; method = $Method; params = $Params }).Json

if ($result.error) {
    Write-Host "JSON-RPC error: $($result.error.message)" -ForegroundColor Red
}
elseif ($result.result.isError) {
    Write-Host "Tool error: $($result.result.content[0].text)" -ForegroundColor Red
}
elseif ($result.result.structuredContent) {
    $result.result.structuredContent | ConvertTo-Json -Depth 10
}
else {
    $result.result | ConvertTo-Json -Depth 10
}

# 3. Close the session so the server doesn't keep it around.
if ($sessionId) {
    try { Invoke-WebRequest -Method Delete -Uri $Url -Headers $headers | Out-Null } catch { }
}
