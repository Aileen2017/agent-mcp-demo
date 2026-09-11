"""CLI entrypoint: python -m agent.main "book me a holiday ..."."""

from __future__ import annotations

import asyncio
import sys

from agent.graph import run_agent

DEFAULT_REQUEST = (
    "Find me a flight from London to Barcelona in three weeks for 5 nights, "
    "book the cheapest option for Jane Doe, and put the holiday in my calendar."
)


def _describe(message: object) -> str:
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        return "  -> " + ", ".join(call["name"] for call in tool_calls)
    name = getattr(message, "name", None)
    content = getattr(message, "content", "")
    if name:
        return f"  <- {name}: {str(content)[:300]}"
    return str(content)


async def main() -> int:
    request = " ".join(sys.argv[1:]).strip() or DEFAULT_REQUEST
    print(f"Request: {request}\n")

    try:
        result = await run_agent(request)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    messages = result["messages"]
    for message in messages[1:-1]:
        line = _describe(message).strip()
        if line:
            print(line)

    print(f"\n{messages[-1].content}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
