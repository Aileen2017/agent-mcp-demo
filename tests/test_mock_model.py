from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.mock_model import HolidayRequest, MockToolCallingModel, _parse_result

TOOL_NAMES = [
    "flights_search_flights",
    "flights_book_flight",
    "calendar_check_availability",
    "calendar_create_event",
]


def _model() -> MockToolCallingModel:
    return MockToolCallingModel().bind_tools(
        [type("Tool", (), {"name": name})() for name in TOOL_NAMES]
    )


def _tool_message(name: str, payload: dict) -> ToolMessage:
    return ToolMessage(content=json.dumps(payload), name=name, tool_call_id=f"call-{name}")


FLIGHT = {
    "flight_id": "BA123-LHRBCN-20261002",
    "carrier": "British Airways",
    "departs_at": "2026-10-02T07:15",
    "price_gbp": 129.99,
}
BOOKING = {
    "booking_reference": "FL-000001",
    "flight_id": FLIGHT["flight_id"],
    "total_price_gbp": 129.99,
}


def test_parse_result_unwraps_mcp_content_blocks() -> None:
    payload = {"flights": [FLIGHT]}

    assert _parse_result(payload) == payload
    assert _parse_result(json.dumps(payload)) == payload
    assert _parse_result([payload]) == payload
    assert _parse_result(json.dumps([payload])) == payload
    assert _parse_result([{"type": "text", "text": json.dumps(payload)}]) == payload
    assert _parse_result("not json") == {}


def test_request_parsing_reads_route_dates_nights_and_passenger() -> None:
    request = HolidayRequest(
        "Find me a flight from London to Barcelona in three weeks for 5 nights, "
        "book the cheapest option for Jane Doe"
    )

    assert request.origin == "LHR"
    assert request.destination == "BCN"
    assert request.nights == 5
    assert request.passenger == "Jane Doe"


def test_request_parsing_handles_explicit_date_and_day_offsets() -> None:
    assert HolidayRequest("fly to Paris on 2026-12-01").depart_date == "2026-12-01"
    assert HolidayRequest("fly to Paris in 10 days").depart == date.today() + timedelta(days=10)
    assert HolidayRequest("fly to Paris in 2 weeks").depart == date.today() + timedelta(weeks=2)


def test_first_turn_searches_flights() -> None:
    reply = _model().invoke([HumanMessage("Book me 3 nights in Paris in 2 weeks")])

    call = reply.tool_calls[0]
    assert call["name"] == "flights_search_flights"
    assert call["args"]["destination"] == "CDG"
    assert call["args"]["depart_date"] == (date.today() + timedelta(weeks=2)).isoformat()


def test_full_sequence_checks_then_schedules_then_books() -> None:
    model = _model()
    messages = [HumanMessage("Fly from London to Barcelona in 3 weeks for 5 nights")]

    messages += [AIMessage(""), _tool_message("flights_search_flights", {"flights": [FLIGHT]})]
    check = model.invoke(messages)
    assert check.tool_calls[0]["name"] == "calendar_check_availability"

    messages += [
        AIMessage(""),
        _tool_message("calendar_check_availability", {"available": True, "conflicts": []}),
    ]
    create = model.invoke(messages)
    args = create.tool_calls[0]["args"]
    assert create.tool_calls[0]["name"] == "calendar_create_event"
    assert args["title"] == "Holiday: BCN"
    assert FLIGHT["flight_id"] in args["notes"]
    assert args["allow_conflict"] is False

    messages += [
        AIMessage(""),
        _tool_message("calendar_create_event", {"event_id": "EVT-000004", "created": True}),
    ]
    book = model.invoke(messages)
    assert book.tool_calls[0]["name"] == "flights_book_flight"
    assert book.tool_calls[0]["args"]["flight_id"] == FLIGHT["flight_id"]

    messages += [AIMessage(""), _tool_message("flights_book_flight", BOOKING)]
    final = model.invoke(messages)
    assert final.tool_calls == []
    assert "FL-000001" in final.content
    assert "EVT-000004" in final.content


def _clashing_history() -> list:
    return [
        HumanMessage("Fly from London to Barcelona in 3 weeks for 5 nights"),
        AIMessage(""),
        _tool_message("flights_search_flights", {"flights": [FLIGHT]}),
        AIMessage(""),
        _tool_message(
            "calendar_check_availability",
            {"available": False, "conflicts": [{"title": "Quarterly planning offsite"}]},
        ),
    ]


def test_conflicting_dates_are_never_forced() -> None:
    create = _model().invoke(_clashing_history())

    assert create.tool_calls[0]["name"] == "calendar_create_event"
    assert create.tool_calls[0]["args"]["allow_conflict"] is False


def test_confirmed_clash_books_and_reports_the_conflict() -> None:
    model = _model()
    messages = _clashing_history() + [
        AIMessage(""),
        _tool_message("calendar_create_event", {"event_id": "EVT-000005", "created": True}),
    ]
    assert model.invoke(messages).tool_calls[0]["name"] == "flights_book_flight"

    messages += [AIMessage(""), _tool_message("flights_book_flight", BOOKING)]
    assert "Quarterly planning offsite" in model.invoke(messages).content


def test_declined_clash_stops_without_booking() -> None:
    messages = _clashing_history() + [
        AIMessage(""),
        _tool_message("calendar_create_event", {"created": False, "reason": "declined"}),
    ]

    reply = _model().invoke(messages)
    assert reply.tool_calls == []
    assert "Nothing was booked" in reply.content


def test_empty_search_results_stop_without_booking() -> None:
    model = _model()
    messages = [
        HumanMessage("Fly from London to Barcelona in 3 weeks"),
        AIMessage(""),
        _tool_message("flights_search_flights", {"flights": []}),
    ]

    reply = model.invoke(messages)
    assert reply.tool_calls == []
    assert "Nothing was booked" in reply.content
