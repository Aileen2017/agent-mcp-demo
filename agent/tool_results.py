"""Normalizes MCP tool results, which arrive as JSON text or content-block lists."""

from __future__ import annotations

import json
from typing import Any


def parse_tool_content(content: Any) -> dict[str, Any]:
    """Return a tool result as a dict, unwrapping MCP content-block lists."""
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return parse_tool_content(json.loads(content))
        except json.JSONDecodeError:
            return {}
    if isinstance(content, list):
        for item in content:
            nested = item.get("text") if isinstance(item, dict) and "text" in item else item
            parsed = parse_tool_content(nested)
            if parsed:
                return parsed
    return {}


def base_tool_name(name: str | None) -> str:
    """Strip the MCP server prefix, e.g. flights_search_flights -> search_flights."""
    if not name:
        return ""
    known = (
        "search_flights",
        "get_flight",
        "book_flight",
        "get_booking",
        "list_events",
        "check_availability",
        "create_event",
        "delete_event",
    )
    for candidate in known:
        if name.endswith(candidate):
            return candidate
    return name
