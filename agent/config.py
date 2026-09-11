"""Connection, model, and HTTP API settings for the holiday-planning agent."""

from __future__ import annotations

import os

FLIGHT_SERVER_URL = os.getenv("FLIGHT_MCP_URL", "http://127.0.0.1:3001/mcp")
CALENDAR_SERVER_URL = os.getenv("CALENDAR_MCP_URL", "http://127.0.0.1:3002/mcp")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Set AGENT_MODEL=mock to run the scripted stand-in instead of Ollama.
AGENT_MODEL = os.getenv("AGENT_MODEL", "ollama").strip().lower()

API_HOST = os.getenv("AGENT_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("AGENT_API_PORT", "8000"))
API_KEY = os.getenv("AGENT_API_KEY", "").strip()

# Never "*": these endpoints are authenticated and reach tools that mutate state.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("AGENT_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

MAX_REQUEST_CHARS = int(os.getenv("AGENT_MAX_REQUEST_CHARS", "2000"))
MAX_BODY_BYTES = int(os.getenv("AGENT_MAX_BODY_BYTES", str(16 * 1024)))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "120"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("AGENT_RATE_LIMIT_PER_MINUTE", "10"))

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def is_loopback(host: str) -> bool:
    return host in LOOPBACK_HOSTS
