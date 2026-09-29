<#
.SYNOPSIS
    Sends a request to the agent API and, whenever the run pauses with a question
    (status "needs_input"), asks you at the console before resuming it.
#>

[CmdletBinding()]
param(
    [string] $Request = 'Fly from London to Barcelona in 3 weeks for 5 nights for Jane Doe',
    [string] $BaseUrl = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'

$headers = @{}
if ($env:AGENT_API_KEY) { $headers['X-API-Key'] = $env:AGENT_API_KEY }

function Invoke-Agent([string] $Path, [hashtable] $Body) {
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$Path" -Headers $headers `
        -ContentType 'application/json' -Body ($Body | ConvertTo-Json)
}

$r = Invoke-Agent '/chat' @{ request = $Request }

while ($r.status -eq 'needs_input') {
    Write-Host "`n$($r.question.message)" -ForegroundColor Yellow
    $reply = Read-Host 'Continue? [y/N]'
    $confirm = $reply.Trim().ToLower() -in @('y', 'yes')
    $r = Invoke-Agent '/chat/resume' @{ thread_id = $r.thread_id; confirm = $confirm }
}

Write-Host "`n$($r.answer)"
if ($r.booking_reference) { Write-Host "Booking reference: $($r.booking_reference)" }
if ($r.event_id) { Write-Host "Calendar event: $($r.event_id)" }
