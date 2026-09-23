$body = '{"request":"Fly from London to Barcelona in 3 weeks for 5 nights for Jane Doe"}'
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType 'application/json' -Body $body
$r.status            # needs_input
$r.question.message  # ...clashes with: Dentist appointment... Add it anyway?
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat/resume -ContentType 'application/json' `
  -Body (@{ thread_id = $r.thread_id; confirm = $true } | ConvertTo-Json)
