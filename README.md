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
search, book, check availability, create event sequence, deriving each call's
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

