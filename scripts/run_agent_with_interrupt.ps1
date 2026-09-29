<#
.SYNOPSIS
    Sends a request to the agent API and, whenever the run pauses with a question
    (status "needs_input"), asks you at the console before resuming it.
    Asks whether to target the local server or the AWS deployment unless -BaseUrl is given.
#>

[CmdletBinding()]
param(
    [string] $Request = 'Fly from London to Barcelona in 3 weeks for 5 nights for Jane Doe',
    [string] $BaseUrl
)
$ErrorActionPreference = 'Stop'

$LocalUrl = 'http://127.0.0.1:8000'
$AwsUrl = 'http://mcp-demo-dev-alb-100218274.eu-west-2.elb.amazonaws.com'
$AwsSecretId = 'mcp-demo-dev-agent-api-key'
$AwsRegion = 'eu-west-2'

if (-not $BaseUrl) {
    Write-Host 'Select the agent API to use:'
    Write-Host "  1) Local  ($LocalUrl)"
    Write-Host "  2) AWS    ($AwsUrl)"
    do {
        $choice = (Read-Host 'Enter 1 or 2 [1]').Trim()
        if (-not $choice) { $choice = '1' }
    } until ($choice -in @('1', '2'))
    $BaseUrl = if ($choice -eq '1') { $LocalUrl } else { $AwsUrl }
}
Write-Host "Using $BaseUrl" -ForegroundColor Cyan

$apiKey = $env:AGENT_API_KEY
if (-not $apiKey -and $BaseUrl -eq $AwsUrl) {
    Write-Host "Fetching API key from AWS Secrets Manager ($AwsSecretId)..." -ForegroundColor Cyan
    $apiKey = aws secretsmanager get-secret-value --secret-id $AwsSecretId --region $AwsRegion `
        --query SecretString --output text
    if ($LASTEXITCODE -ne 0 -or -not $apiKey) { throw "Could not read secret $AwsSecretId." }
    $apiKey = $apiKey.Trim()
}

$headers = @{}
if ($apiKey) { $headers['X-API-Key'] = $apiKey }

function Invoke-Agent([string] $Path, [hashtable] $Body) {
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$Path" -Headers $headers `
        -ContentType 'application/json' -Body ($Body | ConvertTo-Json)
}

# The API caps 'request' at 2000 characters; keep the carried-over answer well under that.
$MaxAnswerChars = 1200

$text = $Request
while ($true) {
    $r = Invoke-Agent '/chat' @{ request = $text }

    while ($r.status -eq 'needs_input') {
        Write-Host "`n$($r.question.message)" -ForegroundColor Yellow
        $reply = Read-Host 'Continue? [y/N]'
        $confirm = $reply.Trim().ToLower() -in @('y', 'yes')
        $r = Invoke-Agent '/chat/resume' @{ thread_id = $r.thread_id; confirm = $confirm }
    }

    Write-Host "`n$($r.answer)"
    if ($r.booking_reference) { Write-Host "Booking reference: $($r.booking_reference)" }
    if ($r.event_id) { Write-Host "Calendar event: $($r.event_id)" }

    # A finished run can still end with a question in its answer; let the user reply to it.
    $followUp = (Read-Host "`nYour reply (Enter to quit)").Trim()
    if (-not $followUp) { break }

    # /chat starts a fresh thread each time, so send the conversation so far with the reply.
    $answer = "$($r.answer)"
    if ($answer.Length -gt $MaxAnswerChars) { $answer = $answer.Substring(0, $MaxAnswerChars) + '...' }
    $text = "Original request: $Request`n`nYour previous reply: $answer`n`nMy answer: $followUp"
}
