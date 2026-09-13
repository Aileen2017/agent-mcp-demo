"""Mock personal calendar MCP server (streamable HTTP, port 3002)."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

SERVER_HOST = os.getenv("MCP_HOST", "127.0.0.1")
SERVER_PORT = 3002
MAX_RANGE_DAYS = 365

CALENDAR_CONFIG: dict[str, Any] = {
    "owner": "Jane Doe",
    "timezone": "Europe/London",
    "working_hours": "09:00-17:30",
    "working_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "annual_leave_days_remaining": 18,
    "notice_required_days": 14,
}

_EVENTS: dict[str, dict[str, Any]] = {}


def _seed_events() -> None:
    today = date.today()
    seeds = [
        ("Quarterly planning offsite", 10, 11, "Offsite in the London office."),
        ("Dentist appointment", 24, 24, "Half-day, morning only."),
        ("Annual leave: family visit", 45, 48, "Already approved."),
    ]
    for index, (title, start_offset, end_offset, notes) in enumerate(seeds, start=1):
        event_id = f"EVT-{index:06d}"
        _EVENTS[event_id] = {
            "event_id": event_id,
            "title": title,
            "start_date": (today + timedelta(days=start_offset)).isoformat(),
            "end_date": (today + timedelta(days=end_offset)).isoformat(),
            "all_day": True,
            "notes": notes,
        }


_seed_events()

mcp = FastMCP(
    name="personal-calendar",
    instructions=(
        "Read calendar://config before scheduling anything. Use check_availability to "
        "detect clashes, then create_event to block out the dates. All data is mock data "
        "held in memory and reset when the server restarts."
    ),
)


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise ToolError(f"{field} must be an ISO date such as 2026-10-14.") from error


def _parse_range(start_date: str, end_date: str) -> tuple[date, date]:
    start = _parse_iso_date(start_date, "start_date")
    end = _parse_iso_date(end_date, "end_date")
    if end < start:
        raise ToolError("end_date must be on or after start_date.")
    if (end - start).days > MAX_RANGE_DAYS:
        raise ToolError(f"The date range must not exceed {MAX_RANGE_DAYS} days.")
    return start, end


def _overlapping(start: date, end: date) -> list[dict[str, Any]]:
    matches = [
        event
        for event in _EVENTS.values()
        if date.fromisoformat(event["start_date"]) <= end
        and date.fromisoformat(event["end_date"]) >= start
    ]
    matches.sort(key=lambda event: event["start_date"])
    return matches


@mcp.tool(
    annotations={
        "title": "List calendar events",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
def list_events(start_date: str, end_date: str) -> dict[str, Any]:
    """List every event overlapping an inclusive ISO date range."""
    start, end = _parse_range(start_date, end_date)
    events = _overlapping(start, end)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_found": len(events),
        "events": events,
    }


@mcp.tool(
    annotations={
        "title": "Check calendar availability",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
def check_availability(start_date: str, end_date: str) -> dict[str, Any]:
    """Report whether an inclusive ISO date range is free, listing any clashing events."""
    start, end = _parse_range(start_date, end_date)
    conflicts = _overlapping(start, end)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "available": not conflicts,
        "conflicts": conflicts,
    }


@mcp.tool(
    annotations={
        "title": "Create a calendar event",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def create_event(
    title: str,
    start_date: str,
    end_date: str,
    notes: str | None = None,
    all_day: bool = True,
    allow_conflict: bool = False,
) -> dict[str, Any]:
    """Block out dates in the calendar and return the new event id."""
    clean_title = title.strip()
    if not clean_title:
        raise ToolError("title must not be empty.")

    start, end = _parse_range(start_date, end_date)
    conflicts = _overlapping(start, end)
    if conflicts and not allow_conflict:
        clashing = ", ".join(event["title"] for event in conflicts)
        raise ToolError(
            f"The range clashes with: {clashing}. Retry with allow_conflict=true to book anyway."
        )

    event_id = f"EVT-{len(_EVENTS) + 1:06d}"
    event = {
        "event_id": event_id,
        "title": clean_title,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "all_day": all_day,
        "notes": notes,
    }
    _EVENTS[event_id] = event
    return event


@mcp.tool(
    annotations={
        "title": "Delete a calendar event",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    }
)
def delete_event(event_id: str) -> dict[str, Any]:
    """Remove an event from the calendar by its id."""
    event = _EVENTS.pop(event_id.strip().upper(), None)
    if event is None:
        raise ToolError(f"No event found with id {event_id}.")
    return {"deleted": event}


@mcp.resource(
    "calendar://config",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def config() -> dict[str, Any]:
    """Owner, timezone, working hours, and remaining annual leave."""
    return CALENDAR_CONFIG


@mcp.resource(
    "calendar://events",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def all_events() -> list[dict[str, Any]]:
    """Every event currently held in the calendar."""
    return sorted(_EVENTS.values(), key=lambda event: event["start_date"])


@mcp.resource(
    "calendar://events/{day}",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def events_on_day(day: str) -> list[dict[str, Any]]:
    """Every event covering one ISO date."""
    try:
        target = date.fromisoformat(day.strip())
    except ValueError as error:
        raise ResourceError("The day segment must be an ISO date such as 2026-10-14.") from error
    return _overlapping(target, target)


@mcp.prompt
def holiday_brief(destination: str, depart_date: str, return_date: str) -> str:
    """Guidance for turning a booked trip into a calendar entry.

    Args:
        destination: Where the traveller is going.
        depart_date: ISO outbound date.
        return_date: ISO date the traveller gets back.
    """
    return (
        f"Block out a holiday to {destination} from {depart_date} to {return_date}.\n"
        "1. Call check_availability for the full range before creating anything.\n"
        "2. If conflicts are reported, name them and ask whether to proceed rather than "
        "silently setting allow_conflict.\n"
        "3. Call create_event with a title of the form 'Holiday: <destination>' and put "
        "the flight booking reference in notes.\n"
        "4. Report the returned event id verbatim; never invent one."
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: StarletteRequest) -> JSONResponse:
    """Return service health without exposing MCP details."""
    return JSONResponse({"status": "ok", "server": "personal-calendar"})


if __name__ == "__main__":
    mcp.run(transport="http", host=SERVER_HOST, port=SERVER_PORT)
