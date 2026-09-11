from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from servers.flight_server import mcp

DEPART = (date.today() + timedelta(days=21)).isoformat()


async def test_exposes_tools_resources_and_prompts() -> None:
    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        resources = {str(resource.uri) for resource in await client.list_resources()}
        prompts = {prompt.name for prompt in await client.list_prompts()}

    assert {"search_flights", "get_flight", "book_flight", "get_booking"} <= tools
    assert {"flights://airports", "flights://policy"} <= resources
    assert "plan_trip" in prompts


async def test_search_returns_cheapest_first_for_a_valid_route() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_flights",
            {"origin": "lhr", "destination": "BCN", "depart_date": DEPART},
        )

    flights = result.data["flights"]
    assert flights
    assert [f["price_gbp"] for f in flights] == sorted(f["price_gbp"] for f in flights)
    assert all(f["origin"] == "LHR" and f["destination"] == "BCN" for f in flights)


async def test_search_results_are_stable_across_calls() -> None:
    async with Client(mcp) as client:
        first = await client.call_tool(
            "search_flights", {"origin": "LHR", "destination": "CDG", "depart_date": DEPART}
        )
        second = await client.call_tool(
            "search_flights", {"origin": "LHR", "destination": "CDG", "depart_date": DEPART}
        )

    assert [f["flight_id"] for f in first.data["flights"]] == [
        f["flight_id"] for f in second.data["flights"]
    ]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"origin": "XXX", "destination": "BCN", "depart_date": DEPART}, "IATA"),
        ({"origin": "LHR", "destination": "LHR", "depart_date": DEPART}, "different airports"),
        ({"origin": "LHR", "destination": "BCN", "depart_date": "14/10/2026"}, "ISO date"),
        (
            {"origin": "LHR", "destination": "BCN", "depart_date": "2020-01-01"},
            "must be in the future",
        ),
        (
            {"origin": "LHR", "destination": "BCN", "depart_date": DEPART, "passengers": 0},
            "passengers must be between",
        ),
    ],
)
async def test_search_rejects_invalid_input(arguments: dict, message: str) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match=message):
            await client.call_tool("search_flights", arguments)


async def test_book_flight_returns_reference_and_reduces_seats() -> None:
    async with Client(mcp) as client:
        search = await client.call_tool(
            "search_flights", {"origin": "LHR", "destination": "DXB", "depart_date": DEPART}
        )
        flight = search.data["flights"][0]
        seats_before = flight["seats_available"]

        booking = await client.call_tool(
            "book_flight",
            {"flight_id": flight["flight_id"], "passenger_name": "Jane Doe", "passengers": 2},
        )
        after = await client.call_tool("get_flight", {"flight_id": flight["flight_id"]})
        fetched = await client.call_tool(
            "get_booking", {"booking_reference": booking.data["booking_reference"]}
        )

    assert booking.data["booking_reference"].startswith("FL-")
    assert booking.data["total_price_gbp"] == round(flight["price_gbp"] * 2, 2)
    assert after.data["seats_available"] == seats_before - 2
    assert fetched.data == booking.data


async def test_unknown_identifiers_are_rejected() -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="BA123-LHRBCN-20261014"):
            await client.call_tool("get_flight", {"flight_id": "nonsense"})
        with pytest.raises(ToolError, match="No booking found"):
            await client.call_tool("get_booking", {"booking_reference": "FL-999999"})


async def test_policy_resource_and_plan_trip_prompt_render() -> None:
    async with Client(mcp) as client:
        policy = await client.read_resource("flights://policy")
        prompt = await client.get_prompt(
            "plan_trip", {"destination": "BCN", "depart_date": DEPART, "nights": "5"}
        )

    assert "23kg checked bag" in policy[0].text
    assert "search_flights" in prompt.messages[0].content.text
