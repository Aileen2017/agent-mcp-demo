"""Connection and model settings for the holiday-planning agent."""

from __future__ import annotations

import os
from typing import Any

FLIGHT_SERVER_URL = os.getenv("FLIGHT_MCP_URL", "http://127.0.0.1:3001/mcp")
CALENDAR_SERVER_URL = os.getenv("CALENDAR_MCP_URL", "http://127.0.0.1:3002/mcp")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Set AGENT_MODEL=mock to run the scripted stand-in instead of Ollama.
AGENT_MODEL = os.getenv("AGENT_MODEL", "ollama").strip().lower()

# MCPAdapter prefixes every tool with its server key, e.g. flights_search_flights.
MCP_CONFIG: dict[str, Any] = {
    "mcpServers": {
        "flights": {"url": FLIGHT_SERVER_URL},
        "calendar": {"url": CALENDAR_SERVER_URL},
    }
}
