"""Mock flight search and booking MCP server (streamable HTTP, port 3001)."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

SERVER_PORT = 3001
MAX_RESULTS = 20
MAX_PASSENGERS = 9
BOOKING_HORIZON_DAYS = 365

AIRPORTS: dict[str, str] = {
    "LHR": "London Heathrow, United Kingdom",
    "JFK": "New York JFK, United States",
    "CDG": "Paris Charles de Gaulle, France",
    "BCN": "Barcelona El Prat, Spain",
    "DXB": "Dubai International, United Arab Emirates",
    "SIN": "Singapore Changi, Singapore",
}

CARRIERS: list[tuple[str, str]] = [
    ("BA", "British Airways"),
    ("AF", "Air France"),
    ("EK", "Emirates"),
]

FARE_POLICY = """\
Fare and baggage policy (sample data)
- Every fare includes one 23kg checked bag and one cabin bag.
- Economy fares are changeable up to 24 hours before departure for a 60 GBP fee.
- Bookings are held for 30 minutes before seats are released back to inventory.
- Cancellations made within 24 hours of booking are refunded in full.
- Prices are quoted per passenger in GBP and already include taxes.
"""

_BOOKINGS: dict[str, dict[str, Any]] = {}
_SEATS_TAKEN: dict[str, int] = {}

mcp = FastMCP(
    name="flight-search",
    instructions=(
        "Search sample flight inventory with search_flights, confirm the chosen option "
        "with get_flight, then reserve seats with book_flight. Always show the traveller "
        "the fare and departure time before booking. All data is mock data."
    ),
)


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise ToolError(f"{field} must be an ISO date such as 2026-10-14.") from error


def _validate_airport(code: str, field: str) -> str:
    normalized = code.strip().upper()
    if normalized not in AIRPORTS:
        known = ", ".join(sorted(AIRPORTS))
        raise ToolError(f"{field} must be one of the supported IATA codes: {known}.")
    return normalized


def _flight_id(carrier: str, number: int, origin: str, destination: str, day: date) -> str:
    return f"{carrier}{number}-{origin}{destination}-{day:%Y%m%d}"


def _flights_for(origin: str, destination: str, day: date) -> list[dict[str, Any]]:
    """Deterministically derive the day's schedule so results are stable across restarts."""
    rng = random.Random(f"{origin}{destination}{day.isoformat()}")
    flights: list[dict[str, Any]] = []

    for slot, departure_hour in enumerate((7, 13, 19)):
        carrier_code, carrier_name = CARRIERS[(slot + len(origin)) % len(CARRIERS)]
        number = 100 + rng.randrange(0, 800)
        duration_minutes = 90 + rng.randrange(0, 14) * 45
        departs = datetime.combine(day, time(hour=departure_hour, minute=rng.choice((0, 15, 30, 45))))
        flight_id = _flight_id(carrier_code, number, origin, destination, day)
        capacity = 120 + rng.randrange(0, 8) * 10

        flights.append(
            {
                "flight_id": flight_id,
                "carrier": carrier_name,
                "origin": origin,
                "origin_name": AIRPORTS[origin],
                "destination": destination,
                "destination_name": AIRPORTS[destination],
                "departs_at": departs.isoformat(timespec="minutes"),
                "arrives_at": (departs + timedelta(minutes=duration_minutes)).isoformat(timespec="minutes"),
                "duration_minutes": duration_minutes,
                "cabin": "economy",
                "price_gbp": round(79 + rng.random() * 420, 2),
                "seats_available": max(0, capacity - _SEATS_TAKEN.get(flight_id, 0)),
            }
        )

    return flights


def _lookup_flight(flight_id: str) -> dict[str, Any]:
    parts = flight_id.strip().split("-")
    if len(parts) != 3 or len(parts[1]) != 6:
        raise ToolError("flight_id must look like BA123-LHRBCN-20261014.")

    origin, destination = parts[1][:3], parts[1][3:]
    try:
        day = datetime.strptime(parts[2], "%Y%m%d").date()
    except ValueError as error:
        raise ToolError("flight_id must look like BA123-LHRBCN-20261014.") from error

    for flight in _flights_for(origin, destination, day):
        if flight["flight_id"] == flight_id.strip():
            return flight

    raise ToolError(f"No flight found with id {flight_id}.")


@mcp.tool(
    annotations={
        "title": "Search flights",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
def search_flights(
    origin: str,
    destination: str,
    depart_date: str,
    passengers: int = 1,
    max_results: int = 5,
) -> dict[str, Any]:
    """Find bookable flights on a route and date, cheapest first, for a given party size."""
    origin_code = _validate_airport(origin, "origin")
    destination_code = _validate_airport(destination, "destination")
    if origin_code == destination_code:
        raise ToolError("origin and destination must be different airports.")
    if not 1 <= passengers <= MAX_PASSENGERS:
        raise ToolError(f"passengers must be between 1 and {MAX_PASSENGERS}.")
    if not 1 <= max_results <= MAX_RESULTS:
        raise ToolError(f"max_results must be between 1 and {MAX_RESULTS}.")

    day = _parse_iso_date(depart_date, "depart_date")
    today = date.today()
    if day <= today:
        raise ToolError("depart_date must be in the future.")
    if day > today + timedelta(days=BOOKING_HORIZON_DAYS):
        raise ToolError(f"depart_date must be within {BOOKING_HORIZON_DAYS} days from today.")

    matches = [f for f in _flights_for(origin_code, destination_code, day) if f["seats_available"] >= passengers]
    matches.sort(key=lambda flight: flight["price_gbp"])

    return {
        "origin": origin_code,
        "destination": destination_code,
        "depart_date": day.isoformat(),
        "passengers": passengers,
        "total_found": len(matches),
        "flights": matches[:max_results],
    }


@mcp.tool(
    annotations={
        "title": "Get a flight",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
def get_flight(flight_id: str) -> dict[str, Any]:
    """Fetch the full record for one flight id returned by search_flights."""
    return _lookup_flight(flight_id)


@mcp.tool(
    annotations={
        "title": "Book a flight",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def book_flight(flight_id: str, passenger_name: str, passengers: int = 1) -> dict[str, Any]:
    """Reserve seats on a flight and return a booking reference plus the total fare."""
    name = passenger_name.strip()
    if not name:
        raise ToolError("passenger_name must not be empty.")
    if not 1 <= passengers <= MAX_PASSENGERS:
        raise ToolError(f"passengers must be between 1 and {MAX_PASSENGERS}.")

    flight = _lookup_flight(flight_id)
    if flight["seats_available"] < passengers:
        raise ToolError(
            f"Only {flight['seats_available']} seats remain on {flight['flight_id']}."
        )

    _SEATS_TAKEN[flight["flight_id"]] = _SEATS_TAKEN.get(flight["flight_id"], 0) + passengers
    reference = f"FL-{len(_BOOKINGS) + 1:06d}"
    booking = {
        "booking_reference": reference,
        "passenger_name": name,
        "passengers": passengers,
        "flight_id": flight["flight_id"],
        "carrier": flight["carrier"],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "departs_at": flight["departs_at"],
        "arrives_at": flight["arrives_at"],
        "total_price_gbp": round(flight["price_gbp"] * passengers, 2),
        "status": "confirmed",
    }
    _BOOKINGS[reference] = booking
    return booking


@mcp.tool(
    annotations={
        "title": "Get a booking",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
def get_booking(booking_reference: str) -> dict[str, Any]:
    """Retrieve a confirmed booking by the reference returned from book_flight."""
    booking = _BOOKINGS.get(booking_reference.strip().upper())
    if booking is None:
        raise ToolError(f"No booking found with reference {booking_reference}.")
    return booking


@mcp.resource(
    "flights://airports",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def airports() -> dict[str, str]:
    """IATA codes this server can search, mapped to their airport names."""
    return AIRPORTS


@mcp.resource(
    "flights://policy",
    mime_type="text/plain",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def policy() -> str:
    """Fare, baggage, and cancellation rules the agent must quote before booking."""
    return FARE_POLICY


@mcp.resource(
    "flights://bookings/{booking_reference}",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def booking_resource(booking_reference: str) -> dict[str, Any]:
    """One confirmed booking, addressable by its reference."""
    booking = _BOOKINGS.get(booking_reference.strip().upper())
    if booking is None:
        raise ResourceError(f"No booking found with reference {booking_reference}.")
    return booking


@mcp.prompt
def plan_trip(destination: str, depart_date: str, nights: str) -> str:
    """Guidance for turning a holiday request into a booked flight.

    Args:
        destination: IATA code or city the traveller wants to reach.
        depart_date: ISO outbound date, for example 2026-10-14.
        nights: How many nights the traveller intends to stay.
    """
    return (
        f"Plan a {nights}-night trip to {destination} departing {depart_date}.\n"
        "1. Call search_flights for the outbound date and present at most three options "
        "with carrier, departure time, and price.\n"
        "2. Call book_flight on the option the traveller accepts, or on the cheapest "
        "option when they have delegated the choice.\n"
        "3. Report the booking reference verbatim; never invent one.\n"
        "4. Quote the relevant line from flights://policy when the traveller asks about "
        "baggage, changes, or cancellation."
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: StarletteRequest) -> JSONResponse:
    """Return service health without exposing MCP details."""
    return JSONResponse({"status": "ok", "server": "flight-search"})


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=SERVER_PORT)
