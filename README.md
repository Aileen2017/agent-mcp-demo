# Holiday-planning agent: two MCP servers and a LangGraph agent

This demo runs two mock MCP servers and a LangGraph agent that uses both of them to find a
flight, book it, and block the dates out in a calendar.

| Component | Path | Port | Provides |
| --- | --- | --- | --- |
| Flight search | [servers/flight_server.py](servers/flight_server.py) | 3001 | `search_flights`, `get_flight`, `book_flight`, `get_booking`; `flights://airports`, `flights://policy`, `flights://bookings/{ref}`; `plan_trip` prompt |
| Personal calendar | [servers/calendar_server.py](servers/calendar_server.py) | 3002 | `list_events`, `check_availability`, `create_event`, `delete_event`; `calendar://config`, `calendar://events`, `calendar://events/{day}`; `holiday_brief` prompt |
| Agent | [agent/](agent/) | 8000 (API) | Loads tools from both servers and merges their resources and prompts into its system prompt |

All flight and calendar data is mock data held in memory. Flight schedules are derived
deterministically from the route and date, so results stay the same across restarts.
Bookings and calendar events reset when a server restarts.

## Setup

Create a virtual environment in the repo root and install the requirements:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Choose a model

`AGENT_MODEL` selects the model:

| `AGENT_MODEL` | Model | Settings |
| --- | --- | --- |
| `ollama` (default) | Local model through Ollama | `OLLAMA_MODEL` (default `qwen3:8b`), `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`) |
| `bedrock` | Claude on Amazon Bedrock | `BEDROCK_MODEL_ID`, `AWS_REGION` (default `eu-west-2`) |
| `mock` | Scripted stand-in in [agent/mock_model.py](agent/mock_model.py) | None |

To use Ollama, install [Ollama](https://ollama.com) and pull a model that can call tools:

```powershell
ollama pull qwen3:8b
```

The mock model needs no LLM. It runs the same steps each time (search, book, check
availability, create the event) and works out each call's arguments from the previous
tool's result. It reads the route, date, number of nights, and passenger name from the
request, so a request like `"Fly from London to Paris in 2 weeks for 3 nights for John Smith"` works.
Use it to test the MCP wiring end to end.

## Run the demo

```powershell
.\scripts\run_demo.ps1
.\scripts\run_demo.ps1 "Book me four nights in Paris next month and put it in my calendar"
.\scripts\run_demo.ps1 -Api    # serve the HTTP API instead of the CLI
```

The script starts both servers and waits for `/health` on each. It then runs the agent
CLI, or the HTTP API if you pass `-Api`, and stops the servers when it exits. You can
run it from any folder.

> [!NOTE]
> [scripts/run_demo.ps1](scripts/run_demo.ps1) currently sets `AGENT_MODEL=mock` itself.
> To use Ollama or Bedrock, start the pieces by hand as shown below.

To run each piece in its own terminal from the repo root:

```powershell
.\.venv\Scripts\python.exe servers\flight_server.py
.\.venv\Scripts\python.exe servers\calendar_server.py
.\.venv\Scripts\python.exe -m agent.main "Find me a flight to Barcelona in three weeks"
```

The agent finds the servers through `FLIGHT_MCP_URL` and `CALENDAR_MCP_URL`. Their
defaults are `http://127.0.0.1:3001/mcp` and `http://127.0.0.1:3002/mcp`.

## Inspect the servers

Use the MCP Inspector:

```powershell
npx @modelcontextprotocol/inspector --cli http://localhost:3001/mcp --transport http --method tools/list
npx @modelcontextprotocol/inspector --cli http://localhost:3001/mcp --transport http --method resources/list
npx @modelcontextprotocol/inspector --cli http://localhost:3002/mcp --transport http --method prompts/list
```

To see the raw HTTP exchange, use [scripts/call_calendar.ps1](scripts/call_calendar.ps1).
It calls the calendar server directly over streamable HTTP, handling the session steps:
initialize, then the request, then closing the session.

```powershell
.\scripts\call_calendar.ps1 -Method tools/list
.\scripts\call_calendar.ps1 -Tool check_availability -Arguments @{ start_date = '2026-10-01'; end_date = '2026-10-05' }
```

## Call the agent over HTTP

[agent/api.py](agent/api.py) serves the agent as a small Starlette app so a web frontend
can call it. It is stateless. Each request builds its own agent and opens its own MCP
connections (via `ClientGroup`), so concurrent requests never share a session or state.

With both MCP servers running:

```powershell
$env:AGENT_API_KEY = "choose-a-secret"      # required unless bound to loopback
.\.venv\Scripts\python.exe -m agent.api     # serves on 127.0.0.1:8000
```

| Endpoint | Method | Returns |
| --- | --- | --- |
| `/health` | GET | `{"status":"ok"}` (no key required) |
| `/chat` | POST | One JSON answer: `{answer, steps, booking_reference, event_id}` |
| `/chat/stream` | POST | `text/event-stream` with `step`, `token`, `done`, and `error` events |

```powershell
$key  = "choose-a-secret"
$body = '{"request":"Fly from London to Paris in 2 weeks for 3 nights for John Smith"}'

$body = '{"request":"Book me 5 nights in Barcelona in three weeks and add it to my calendar"}'
curl -H "X-API-Key: choose-a-secret" -H "Content-Type: application/json" -d $body http://127.0.0.1:8000/chat
curl -N -H "X-API-Key: choose-a-secret" -H "Content-Type: application/json" -d $body http://127.0.0.1:8000/chat/stream

### Security

The API has basic protections built in:

- An API key in the `X-API-Key` header, compared in constant time.
- A per-IP rate limit, kept in memory.
- Limits on request body size and input length.
- A timeout on each request.
- A strict CORS allowlist.
- Generic error responses. Each carries a correlation ID, and the details go to the server log.

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENT_API_KEY` | _(empty)_ | Required on `/chat*`. If empty and bound to loopback, the API runs without a key and logs a warning. If empty and bound to any other host, the API refuses to start. |
| `AGENT_API_HOST` / `AGENT_API_PORT` | `127.0.0.1` / `8000` | Bind address. |
| `AGENT_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS allowlist (never `*`). |
| `AGENT_RATE_LIMIT_PER_MINUTE` | `10` | Requests per client IP per minute. |
| `AGENT_MAX_REQUEST_CHARS` | `2000` | Maximum characters in the `request` field. |
| `AGENT_MAX_BODY_BYTES` | `16384` | Maximum request body size. |
| `AGENT_REQUEST_TIMEOUT_SECONDS` | `120` | Time limit for each request. |

Each process keeps its own rate-limit counts, so running several workers would need a shared
store. These endpoints can call tools that change state (`book_flight`, `create_event`).
LLM output is untrusted, so the real protection is the `ToolError` validation inside the tools.

## How prompts and resources reach the agent

LangChain's `MCPAdapter` loads MCP **tools** only. [agent/context.py](agent/context.py)
therefore reads each server's resources and prompts through a `fastmcp.Client` and adds
them to the system prompt.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests run the FastMCP servers in the same process. They don't need open ports or
network access, and they never call a real model.

## Deployment

The [Dockerfile](Dockerfile) builds a single image for all three services; the start
command is set for each service at deploy time. Terraform for AWS (ECR, networking, ECS
behind an ALB) is in [infra/](infra/), and the GitHub Actions workflows in
[.github/workflows/](.github/workflows/) provision the infrastructure and build and deploy
the image.
