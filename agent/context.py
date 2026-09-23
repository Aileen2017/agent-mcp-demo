"""Builds the agent system prompt from MCP resources and prompts.

MCPAdapter only wraps MCP tools, so resources and prompts are read directly through
a FastMCP client and folded into the system prompt here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastmcp import Client

from agent.config import CALENDAR_SERVER_URL, FLIGHT_SERVER_URL

TOOL_CONTRACT = """\
You are a travel assistant with two MCP servers: flight search and a personal calendar.

Follow this order and never skip a step:
1. calendar_check_availability - check the full holiday range, outbound to return date.
2. calendar_create_event - block out the range, putting the booking reference in notes.
3. flights_search_flights - find options for the requested route and outbound date.
4. Present at most three options with carrier, departure time, and price.
5. flights_book_flight - reserve the chosen option and capture the booking reference.


Rules:
- Resolve city names to the IATA codes listed in the airports resource below.
- Never invent a booking reference or an event id. Only report values a tool returned.
- If a tool returns an error, report it and stop rather than guessing.
- Finish by stating the booking reference and the calendar event id.
"""


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    for attribute in ("text", "content", "value"):
        nested = getattr(value, attribute, None)
        if nested is not None and nested is not value:
            return _as_text(nested)
    if isinstance(value, (list, tuple)):
        return "\n".join(_as_text(item) for item in value)
    return str(value)


async def _read_resource(client: Client, uri: str) -> str:
    return _as_text(await client.read_resource(uri))


async def _render_prompt(client: Client, name: str, arguments: dict[str, str]) -> str:
    result = await client.get_prompt(name, arguments)
    return _as_text(getattr(result, "messages", result))


async def _flight_context(target: Any) -> str:
    async with Client(target) as client:
        airports = await _read_resource(client, "flights://airports")
        policy = await _read_resource(client, "flights://policy")
        guidance = await _render_prompt(
            client,
            "plan_trip",
            {
                "destination": "<destination>",
                "depart_date": "<depart_date>",
                "nights": "<nights>",
            },
        )
    return f"Supported airports (IATA -> name):\n{airports}\n\n{policy}\n{guidance}"


async def _calendar_context(target: Any) -> str:
    async with Client(target) as client:
        config = await _read_resource(client, "calendar://config")
        guidance = await _render_prompt(
            client,
            "holiday_brief",
            {
                "destination": "<destination>",
                "depart_date": "<depart_date>",
                "return_date": "<return_date>",
            },
        )
    return f"Calendar owner configuration:\n{config}\n\n{guidance}"


async def build_system_prompt(
    flight_target: Any = None,
    calendar_target: Any = None,
) -> str:
    """Assemble the system prompt, reading live resources and prompts from both servers.

    Pass FastMCP server instances as targets to build the prompt in-process for tests.
    """
    flight_target = flight_target or FLIGHT_SERVER_URL
    calendar_target = calendar_target or CALENDAR_SERVER_URL

    try:
        flights = await _flight_context(flight_target)
    except Exception as error:
        raise RuntimeError(
            f"Could not reach the flight MCP server at {flight_target}. "
            "Start it with: python servers/flight_server.py"
        ) from error

    try:
        calendar = await _calendar_context(calendar_target)
    except Exception as error:
        raise RuntimeError(
            f"Could not reach the calendar MCP server at {calendar_target}. "
            "Start it with: python servers/calendar_server.py"
        ) from error

    return (
        f"{TOOL_CONTRACT}\n"
        f"Today's date is {date.today().isoformat()}.\n\n"
        f"{flights}\n\n{calendar}"
    )
