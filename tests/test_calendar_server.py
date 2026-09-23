from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from servers.calendar_server import mcp

TODAY = date.today()
FREE_START = (TODAY + timedelta(days=60)).isoformat()
FREE_END = (TODAY + timedelta(days=65)).isoformat()
BUSY_START = (TODAY + timedelta(days=10)).isoformat()
BUSY_END = (TODAY + timedelta(days=11)).isoformat()


async def test_exposes_tools_resources_and_prompts() -> None:
    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        resources = {str(resource.uri) for resource in await client.list_resources()}
        prompts = {prompt.name for prompt in await client.list_prompts()}

    assert {"list_events", "check_availability", "create_event", "delete_event"} <= tools
    assert {"calendar://config", "calendar://events"} <= resources
    assert "holiday_brief" in prompts


async def test_seeded_range_reports_a_conflict() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "check_availability", {"start_date": BUSY_START, "end_date": BUSY_END}
        )

    assert result.data["available"] is False
    assert result.data["conflicts"][0]["title"] == "Quarterly planning offsite"


async def test_free_range_is_available() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "check_availability", {"start_date": FREE_START, "end_date": FREE_END}
        )

    assert result.data["available"] is True
    assert result.data["conflicts"] == []


async def test_create_event_blocks_the_range_and_then_reports_it_busy() -> None:
    start = (TODAY + timedelta(days=120)).isoformat()
    end = (TODAY + timedelta(days=125)).isoformat()

    async with Client(mcp) as client:
        created = await client.call_tool(
            "create_event",
            {
                "title": "Holiday: Barcelona",
                "start_date": start,
                "end_date": end,
                "notes": "Booking FL-000001",
            },
        )
        availability = await client.call_tool(
            "check_availability", {"start_date": start, "end_date": end}
        )
        listed = await client.call_tool("list_events", {"start_date": start, "end_date": end})

    assert created.data["event_id"].startswith("EVT-")
    assert availability.data["available"] is False
    assert created.data["event_id"] in {event["event_id"] for event in listed.data["events"]}


def _answering(add_anyway: bool) -> tuple[Client, list[str]]:
    """A client that answers the clash question with add_anyway, recording what it was asked."""
    asked: list[str] = []

    async def handler(message: str, response_type: type, params: object, context: object):
        asked.append(message)
        return {"add_anyway": add_anyway}

    return Client(mcp, elicitation_handler=handler), asked


async def test_clash_asks_the_user_and_adds_the_event_when_confirmed() -> None:
    client, asked = _answering(True)
    async with client:
        created = await client.call_tool(
            "create_event",
            {"title": "Holiday: Paris", "start_date": BUSY_START, "end_date": BUSY_END},
        )
        await client.call_tool("delete_event", {"event_id": created.data["event_id"]})

    assert created.data["created"] is True
    assert len(asked) == 1
    assert "Quarterly planning offsite" in asked[0]


async def test_clash_declined_by_the_user_creates_nothing() -> None:
    client, asked = _answering(False)
    async with client:
        before = await client.call_tool(
            "list_events", {"start_date": BUSY_START, "end_date": BUSY_END}
        )
        result = await client.call_tool(
            "create_event",
            {"title": "Holiday: Paris", "start_date": BUSY_START, "end_date": BUSY_END},
        )
        after = await client.call_tool(
            "list_events", {"start_date": BUSY_START, "end_date": BUSY_END}
        )

    assert asked
    assert result.data["created"] is False
    assert result.data["conflicts"][0]["title"] == "Quarterly planning offsite"
    assert after.data["total_found"] == before.data["total_found"]


async def test_no_question_when_the_range_is_free() -> None:
    start = (TODAY + timedelta(days=200)).isoformat()
    client, asked = _answering(False)
    async with client:
        created = await client.call_tool(
            "create_event", {"title": "Holiday: Rome", "start_date": start, "end_date": start}
        )
        await client.call_tool("delete_event", {"event_id": created.data["event_id"]})

    assert asked == []
    assert created.data["created"] is True


async def test_create_event_refuses_a_clash_unless_allowed() -> None:
    # A client that cannot answer questions gets the old error instead.
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="Quarterly planning offsite"):
            await client.call_tool(
                "create_event",
                {"title": "Holiday: Paris", "start_date": BUSY_START, "end_date": BUSY_END},
            )

        forced = await client.call_tool(
            "create_event",
            {
                "title": "Holiday: Paris",
                "start_date": BUSY_START,
                "end_date": BUSY_END,
                "allow_conflict": True,
            },
        )
        await client.call_tool("delete_event", {"event_id": forced.data["event_id"]})


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"start_date": "next tuesday", "end_date": FREE_END}, "ISO date"),
        ({"start_date": FREE_END, "end_date": FREE_START}, "on or after"),
    ],
)
async def test_range_validation(arguments: dict, message: str) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match=message):
            await client.call_tool("check_availability", arguments)


async def test_delete_event_rejects_unknown_id() -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="No event found"):
            await client.call_tool("delete_event", {"event_id": "EVT-999999"})


async def test_config_resource_and_holiday_brief_prompt_render() -> None:
    async with Client(mcp) as client:
        config = await client.read_resource("calendar://config")
        prompt = await client.get_prompt(
            "holiday_brief",
            {"destination": "Barcelona", "depart_date": FREE_START, "return_date": FREE_END},
        )

    assert "Europe/London" in config[0].text
    assert "check_availability" in prompt.messages[0].content.text
