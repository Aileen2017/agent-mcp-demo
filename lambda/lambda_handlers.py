"""ASGI entry points for the three Lambda functions.

The image is shared by all three functions. Each function's image command picks one app:

    flights_app   -> flight MCP server   (POST /mcp, GET /health)
    calendar_app  -> calendar MCP server (POST /mcp, GET /health)
    agent_app     -> holiday agent API   (POST /chat, POST /chat/stream, GET /health)

The Lambda Web Adapter (copied into the image) forwards Function URL requests to these apps
on AWS_LWA_PORT, so the servers keep their normal ASGI behaviour.
"""

from __future__ import annotations

from agent.api import app as agent_app
from servers.calendar_server import mcp as calendar_mcp
from servers.flight_server import mcp as flight_mcp

# Stateless: a Lambda request can land on any warm container, so the MCP session id held in
# memory by the default stateful transport would not be found on the next request.
flights_app = flight_mcp.http_app(path="/mcp", stateless_http=True, json_response=True)
calendar_app = calendar_mcp.http_app(path="/mcp", stateless_http=True, json_response=True)

__all__ = ["agent_app", "calendar_app", "flights_app"]
