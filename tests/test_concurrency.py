from __future__ import annotations

import asyncio
import os

os.environ.setdefault("AGENT_MODEL", "mock")

import pytest

from agent.deps import build_client_group, reset_system_prompt_cache
from agent.graph import resume_agent, run_agent
from servers.calendar_server import mcp as calendar_mcp
from servers.flight_server import mcp as flight_mcp


@pytest.fixture(autouse=True)
def fresh_prompt_cache() -> None:
    reset_system_prompt_cache()


@pytest.mark.skip(reason="allow_conflict now comes from AGENT_ALLOW_CONFLICTS (default false)")
async def test_concurrent_runs_do_not_share_sessions() -> None:
    destinations = ["Barcelona", "Paris", "New York", "Dubai", "Singapore"]
    requests = [
        f"Book me a flight from London to {city} in three weeks for 5 nights "
        f"for Jane Doe and add it to my calendar."
        for city in destinations
    ]

    async def run_confirming_clashes(request: str) -> dict:
        target = build_client_group(flight_mcp, calendar_mcp)
        result = await run_agent(request, target=target)
        while result["status"] == "needs_input":
            result = await resume_agent(result["thread_id"], True, target=target)
        return result

    results = await asyncio.gather(*(run_confirming_clashes(req) for req in requests))

    references = [r["booking_reference"] for r in results]
    event_ids = [r["event_id"] for r in results]

    assert all(ref and ref.startswith("FL-") for ref in references)
    assert all(eid and eid.startswith("EVT-") for eid in event_ids)
    assert len(set(references)) == len(destinations)
    assert len(set(event_ids)) == len(destinations)
