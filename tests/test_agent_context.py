from __future__ import annotations

from datetime import date

import pytest

from agent.context import build_system_prompt
from servers.calendar_server import mcp as calendar_mcp
from servers.flight_server import mcp as flight_mcp


async def test_system_prompt_merges_resources_and_prompts_from_both_servers() -> None:
    prompt = await build_system_prompt(flight_target=flight_mcp, calendar_target=calendar_mcp)

    assert "flights_search_flights" in prompt
    assert "calendar_create_event" in prompt
    assert "23kg checked bag" in prompt
    assert "Europe/London" in prompt
    assert "LHR" in prompt
    assert date.today().isoformat() in prompt
    assert "Never invent a booking reference" in prompt


async def test_unreachable_server_raises_an_actionable_error() -> None:
    with pytest.raises(RuntimeError, match="flight_server.py"):
        await build_system_prompt(
            flight_target="http://127.0.0.1:59999/mcp", calendar_target=calendar_mcp
        )

    with pytest.raises(RuntimeError, match="calendar_server.py"):
        await build_system_prompt(
            flight_target=flight_mcp, calendar_target="http://127.0.0.1:59999/mcp"
        )
