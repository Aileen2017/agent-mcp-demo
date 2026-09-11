"""Shared MCP connections and the cached system prompt for the agent."""

from __future__ import annotations

from typing import Any

from fastmcp.client import Client
from fastmcp.client.group import ClientGroup

from agent.config import CALENDAR_SERVER_URL, FLIGHT_SERVER_URL
from agent.context import build_system_prompt

_system_prompt: str | None = None
_default_targets: tuple[Any, Any] | None = None


def set_default_targets(flight_target: Any, calendar_target: Any) -> None:
    """Override the MCP endpoints process-wide; used by tests for in-memory servers."""
    global _default_targets
    _default_targets = (flight_target, calendar_target)
    reset_system_prompt_cache()


def _resolve(flight_target: Any, calendar_target: Any) -> tuple[Any, Any]:
    if flight_target is None and calendar_target is None and _default_targets is not None:
        return _default_targets
    return (
        flight_target if flight_target is not None else FLIGHT_SERVER_URL,
        calendar_target if calendar_target is not None else CALENDAR_SERVER_URL,
    )


def build_client_group(
    flight_target: Any = None,
    calendar_target: Any = None,
) -> ClientGroup:
    """One independent client per server, so concurrent runs never share a session."""
    flight, calendar = _resolve(flight_target, calendar_target)
    return ClientGroup({"flights": Client(flight), "calendar": Client(calendar)})


async def get_system_prompt(
    flight_target: Any = None,
    calendar_target: Any = None,
) -> str:
    """Build the system prompt once; its resources and prompts are static config."""
    global _system_prompt
    if _system_prompt is None:
        flight, calendar = _resolve(flight_target, calendar_target)
        _system_prompt = await build_system_prompt(flight, calendar)
    return _system_prompt


def reset_system_prompt_cache() -> None:
    global _system_prompt
    _system_prompt = None
