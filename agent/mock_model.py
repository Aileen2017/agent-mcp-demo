"""Scripted stand-in for a tool-calling chat model, for testing without Ollama.

It drives the same tool sequence the real agent is instructed to follow, deriving
each call's arguments from the previous tool's result rather than from an LLM.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agent.tool_results import base_tool_name as _base_name
from agent.tool_results import parse_tool_content as _parse_result
from agent.config import ALLOW_CONFLICTS

CITY_CODES: dict[str, str] = {
    "london": "LHR",
    "heathrow": "LHR",
    "new york": "JFK",
    "jfk": "JFK",
    "paris": "CDG",
    "barcelona": "BCN",
    "dubai": "DXB",
    "singapore": "SIN",
}

DEFAULT_ORIGIN = "LHR"
DEFAULT_DESTINATION = "BCN"
DEFAULT_LEAD_DAYS = 21
DEFAULT_NIGHTS = 5
DEFAULT_PASSENGER = "Jane Doe"


class HolidayRequest:
    """The few facts the scripted model needs, pulled out of the user's message."""

    def __init__(self, text: str) -> None:
        lowered = text.lower()
        self.origin, self.destination = self._route(lowered)
        self.depart = self._depart_date(lowered)
        self.nights = self._nights(lowered)
        self.passenger = self._passenger(text)

    @property
    def depart_date(self) -> str:
        return self.depart.isoformat()

    @property
    def return_date(self) -> str:
        return (self.depart + timedelta(days=self.nights)).isoformat()

    @staticmethod
    def _route(text: str) -> tuple[str, str]:
        pair = re.search(r"from\s+([a-z ]+?)\s+to\s+([a-z ]+?)\b", text)
        if pair:
            origin = CITY_CODES.get(pair.group(1).strip(), DEFAULT_ORIGIN)
            destination = CITY_CODES.get(pair.group(2).strip(), DEFAULT_DESTINATION)
            return origin, destination

        mentioned = [code for city, code in CITY_CODES.items() if city in text]
        destination = mentioned[0] if mentioned else DEFAULT_DESTINATION
        origin = DEFAULT_ORIGIN if destination != DEFAULT_ORIGIN else "CDG"
        return origin, destination

    @staticmethod
    def _depart_date(text: str) -> date:
        explicit = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if explicit:
            return date.fromisoformat(explicit.group(0))
        weeks = re.search(r"in\s+(\d+)\s*weeks?", text)
        if weeks:
            return date.today() + timedelta(weeks=int(weeks.group(1)))
        days = re.search(r"in\s+(\d+)\s*days?", text)
        if days:
            return date.today() + timedelta(days=int(days.group(1)))
        if "next month" in text:
            return date.today() + timedelta(days=30)
        return date.today() + timedelta(days=DEFAULT_LEAD_DAYS)

    @staticmethod
    def _nights(text: str) -> int:
        nights = re.search(r"(\d+)\s*nights?", text)
        return int(nights.group(1)) if nights else DEFAULT_NIGHTS

    @staticmethod
    def _passenger(text: str) -> str:
        name = re.search(r"for ([A-Z][a-z]+(?: [A-Z][a-z]+)?)", text)
        return name.group(1) if name else DEFAULT_PASSENGER


class MockToolCallingModel(BaseChatModel):
    """Replays a fixed search -> book -> check -> schedule sequence."""

    tool_names: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "mock-holiday-planner"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> MockToolCallingModel:
        names = [getattr(tool, "name", str(tool)) for tool in tools]
        return self.model_copy(update={"tool_names": names})

    def _tool(self, base: str) -> str:
        for name in self.tool_names:
            if _base_name(name) == base:
                return name
        return base

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        request = HolidayRequest(
            next(
                (str(m.content) for m in messages if isinstance(m, HumanMessage)),
                "",
            )
        )
        results = {
            _base_name(m.name): _parse_result(m.content)
            for m in messages
            if isinstance(m, ToolMessage)
        }

        if "search_flights" not in results:
            return self._call(
                "search_flights",
                {
                    "origin": request.origin,
                    "destination": request.destination,
                    "depart_date": request.depart_date,
                    "passengers": 1,
                },
            )

        flights = results["search_flights"].get("flights") or []
        if not flights:
            return AIMessage(
                content=(
                    f"No flights available from {request.origin} to {request.destination} "
                    f"on {request.depart_date}. Nothing was booked."
                )
            )

        cheapest = flights[0]
        if "book_flight" not in results:
            return self._call(
                "book_flight",
                {
                    "flight_id": cheapest["flight_id"],
                    "passenger_name": request.passenger,
                    "passengers": 1,
                },
            )

        booking = results["book_flight"]
        if "check_availability" not in results:
            return self._call(
                "check_availability",
                {"start_date": request.depart_date, "end_date": request.return_date},
            )

        availability = results["check_availability"]
        if "create_event" not in results:
            return self._call(
                "create_event",
                {
                    "title": f"Holiday: {request.destination}",
                    "start_date": request.depart_date,
                    "end_date": request.return_date,
                    "notes": f"Flight booking {booking.get('booking_reference')}",
                    "allow_conflict": ALLOW_CONFLICTS,
                },
            )

        event = results["create_event"]
        conflicts = availability.get("conflicts") or []
        clash_note = (
            f" Note: this clashes with {', '.join(c['title'] for c in conflicts)}."
            if conflicts
            else ""
        )
        return AIMessage(
            content=(
                f"Booked {cheapest['carrier']} {booking.get('flight_id')} from "
                f"{request.origin} to {request.destination} departing "
                f"{cheapest['departs_at']} for "
                f"GBP {booking.get('total_price_gbp')}.\n"
                f"Booking reference: {booking.get('booking_reference')}\n"
                f"Calendar event: {event.get('event_id')} "
                f"({request.depart_date} to {request.return_date}).{clash_note}"
            )
        )

    def _call(self, base: str, args: dict[str, Any]) -> AIMessage:
        name = self._tool(base)
        return AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": f"mock-{base}"}],
        )
