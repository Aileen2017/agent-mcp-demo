# DummyJSON Product Catalog MCP Server

A read-only, remote streamable-HTTP MCP server that gives Claude two product-catalog tools backed by [DummyJSON Products](https://dummyjson.com/docs/products):

- `search_products`: Search sample catalog products by keyword with bounded pagination.
- `get_product`: Retrieve the complete record for a product ID.

DummyJSON is public sample data. This project does not use OAuth or require credentials.

## Run locally

Create and install into a project virtual environment:

```powershell
C:\Users\ailee\.local\bin\python3.14.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

The MCP endpoint is `http://localhost:3000/mcp`; the health check is `http://localhost:3000/health`.

## Test with MCP Inspector

With the server running:

```powershell
npx @modelcontextprotocol/inspector --cli http://localhost:3000/mcp --transport http --method tools/list
npx @modelcontextprotocol/inspector --cli http://localhost:3000/mcp --transport http --method tools/call --tool-name search_products --tool-arg query=phone
```

## Connect Claude after deployment

Deploy this app to an HTTPS-capable Python host, then add its `/mcp` URL under **Settings → Connectors → Add custom connector** in Claude. Before publicly sharing the connector, test the deployed endpoint with the MCP Inspector and Claude.

## Pull request automation

After committing [`.github/workflows/open-pull-request.yml`](.github/workflows/open-pull-request.yml)
to `main`, enable **Settings → Actions → General → Workflow permissions → Allow GitHub
Actions to create and approve pull requests** in the GitHub repository.

Each successful CI run triggered by a push to a branch other than `main` then creates one
open pull request into `main`. The workflow skips stale CI runs and branches that already
have an open pull request.

## Holiday-planning demo: two MCP servers and a LangGraph agent

A second, self-contained demo lives alongside the DummyJSON server. It runs two mock MCP
servers and a LangGraph agent that uses both to find a flight, book it, and block the dates
out in a calendar.

| Component | Path | Port | Provides |
| --- | --- | --- | --- |
| Flight search | [servers/flight_server.py](servers/flight_server.py) | 3001 | `search_flights`, `get_flight`, `book_flight`, `get_booking`; `flights://airports`, `flights://policy`, `flights://bookings/{ref}`; `plan_trip` prompt |
| Personal calendar | [servers/calendar_server.py](servers/calendar_server.py) | 3002 | `list_events`, `check_availability`, `create_event`, `delete_event`; `calendar://config`, `calendar://events`, `calendar://events/{day}`; `holiday_brief` prompt |
| Agent | [agent/](agent/) | - | Loads tools from both servers and merges their resources and prompts into its system prompt |

All flight and calendar data is mock data generated in memory. Flight schedules are derived
deterministically from the route and date, so results are stable across restarts; bookings
and calendar events reset when a server restarts.

### Prerequisites

Install [Ollama](https://ollama.com) and pull a tool-calling model:

```powershell
ollama pull qwen3:8b
```

Override the defaults with `OLLAMA_MODEL` and `OLLAMA_BASE_URL` if needed.

### Run without Ollama (mock model)

Set `AGENT_MODEL=mock` to swap `ChatOllama` for the scripted model in
[agent/mock_model.py](agent/mock_model.py). It replays the same
search, check availability, create event, book sequence, deriving each call's
arguments from the previous tool's result instead of from an LLM. Useful for
exercising the MCP wiring end to end with no model installed.

```powershell
$env:AGENT_MODEL = "mock"
.\run_demo.ps1
```

It parses the route, date, number of nights, and passenger name out of the request,
so `"Fly from London to Paris in 2 weeks for 3 nights for John Smith"` works too.
Remove the variable (`Remove-Item Env:AGENT_MODEL`) to go back to Ollama.

### Run the demo

```powershell
.\run_demo.ps1
.\run_demo.ps1 "Book me four nights in Paris next month and put it in my calendar"
```

The script starts both servers, waits for `/health` on each, runs the agent, and shuts the
servers down afterwards. To run the pieces by hand:

```powershell
.\.venv\Scripts\python.exe servers\flight_server.py
.\.venv\Scripts\python.exe servers\calendar_server.py
.\.venv\Scripts\python.exe -m agent.main "Find me a flight to Barcelona in three weeks"
```

### Inspect the servers

```powershell
npx @modelcontextprotocol/inspector --cli http://localhost:3001/mcp --transport http --method tools/list
npx @modelcontextprotocol/inspector --cli http://localhost:3001/mcp --transport http --method resources/list
npx @modelcontextprotocol/inspector --cli http://localhost:3002/mcp --transport http --method prompts/list
```

### Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests connect to the FastMCP servers in-process, so no ports and no network access are
required and the Ollama model is never called.

### A note on prompts and resources

LangChain's `MCPAdapter` wraps MCP **tools** only. The agent therefore reads each server's
resources and prompts directly through a `fastmcp.Client` in
[agent/context.py](agent/context.py) and folds them into the system prompt.

### Call the agent over HTTP

[agent/api.py](agent/api.py) exposes the agent as a small Starlette service so a web
frontend can drive it. It is stateless: each request builds its own agent and its own
independent MCP connections (via `ClientGroup`), so concurrent requests never share a
session or leak state into one another.

Start the two MCP servers, then the API:

```powershell
$env:AGENT_API_KEY = "choose-a-secret"   # required unless bound to loopback
.\.venv\Scripts\python.exe servers\flight_server.py   # in its own terminal
.\.venv\Scripts\python.exe servers\calendar_server.py # in its own terminal
.\.venv\Scripts\python.exe -m agent.api               # serves on 127.0.0.1:8000
```

| Endpoint | Method | Returns |
| --- | --- | --- |
| `/health` | GET | `{"status":"ok"}` (no key required) |
| `/chat` | POST | one JSON answer: `{status, answer, steps, booking_reference, event_id, thread_id, question}` |
| `/chat/stream` | POST | `text/event-stream` with `step`, `token`, `input_required`, `done`, and `error` events |
| `/chat/resume` | POST | answers a paused run: body `{"thread_id": "...", "confirm": true}`; same response as `/chat` |
| `/chat/resume/stream` | POST | the same, streamed like `/chat/stream` |

```powershell
$body = '{"request":"Book me 5 nights in Barcelona in three weeks and add it to my calendar"}'
curl -H "X-API-Key: choose-a-secret" -H "Content-Type: application/json" -d $body http://127.0.0.1:8000/chat
curl -N -H "X-API-Key: choose-a-secret" -H "Content-Type: application/json" -d $body http://127.0.0.1:8000/chat/stream
```

#### Calendar clashes

If the holiday overlaps an existing calendar event, `create_event` on the calendar server
asks the user whether to add it anyway, using MCP elicitation (the 2026-07-28
input-required flow). The agent pauses: the response has `"status": "needs_input"`, a
`question.message`, and a `thread_id`. Resume with `confirm: true` to add the event and
book the flight, or `confirm: false` to cancel; nothing is booked on a cancel, because
the calendar step runs before `book_flight`.

```powershell
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType 'application/json' -Body $body
$r.question.message
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat/resume -ContentType 'application/json' `
  -Body (@{ thread_id = $r.thread_id; confirm = $true } | ConvertTo-Json)
```

The CLI (`python -m agent.main`) asks `Continue? [y/N]` in the terminal instead. Paused
runs are kept in memory, so restarting the API forgets them. MCP clients that can't
answer questions (older protocol versions, or no elicitation support) get the previous
behaviour: a `ToolError` telling them to retry with `allow_conflict=true`.

Basic hardening is built in: an API key (`X-API-Key`, constant-time compared), a per-IP
in-memory rate limit, a request-body size cap, an input-length cap, a per-request timeout,
a strict CORS allowlist, and generic error responses that carry a correlation id while the
detail stays in the server log. Configure it with these environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENT_API_KEY` | _(empty)_ | Required on `/chat*`. If empty and bound to loopback, the API runs unauthenticated with a warning; if empty and bound to a non-loopback host, the API refuses to start. |
| `AGENT_API_HOST` / `AGENT_API_PORT` | `127.0.0.1` / `8000` | Bind address. |
| `AGENT_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS allowlist (never `*`). |
| `AGENT_RATE_LIMIT_PER_MINUTE` | `10` | Requests per client IP per minute. |
| `AGENT_MAX_REQUEST_CHARS` | `2000` | Max characters in the `request` field. |
| `AGENT_REQUEST_TIMEOUT_SECONDS` | `120` | Per-request agent timeout. |

The rate limit is per process; a multi-worker deployment would need a shared store. These
endpoints reach tools that mutate state (`book_flight`, `create_event`), and the data is
all mock data — treat the tool-side `ToolError` validation as the real defense, since LLM
output is untrusted.


