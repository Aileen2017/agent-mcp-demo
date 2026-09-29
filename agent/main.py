"""CLI entrypoint: python -m agent.main "book me a holiday ..."."""

from __future__ import annotations

import asyncio
import sys

from agent.graph import run_agent

DEFAULT_REQUEST = (
    "Find me a flight from London to Barcelona in three weeks for 5 nights, "
    "book the cheapest option for Jane Doe, and put the holiday in my calendar."
)


def _describe(step: dict) -> str:
    if step["kind"] == "tool_call":
        return f"  -> {step['tool']} {step['args']}"
    return f"  <- {step['tool']}: {str(step['result'])[:300]}"


async def main() -> int:
    request = " ".join(sys.argv[1:]).strip() or DEFAULT_REQUEST
    print(f"Request: {request}\n")

    try:
        result = await run_agent(request)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    for step in result["steps"]:
        print(_describe(step))

    print(f"\n{result['answer']}")
    if result["booking_reference"]:
        print(f"Booking reference: {result['booking_reference']}")
    if result["event_id"]:
        print(f"Calendar event: {result['event_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
