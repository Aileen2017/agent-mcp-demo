from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

import agent.api as api
from agent.deps import set_default_targets
from servers.calendar_server import mcp as calendar_mcp
from servers.flight_server import mcp as flight_mcp

REQUEST = (
    "Find a flight from London to Barcelona in three weeks for 5 nights, "
    "book the cheapest for Jane Doe, and add it to my calendar."
)
HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture(autouse=True)
def in_memory_servers() -> None:
    set_default_targets(flight_mcp, calendar_mcp)
    api._recent_calls.clear()


@pytest.fixture
def client() -> TestClient:
    with TestClient(api.app) as test_client:
        yield test_client


def test_health_needs_no_api_key(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_books_a_flight_and_creates_an_event(client: TestClient) -> None:
    response = client.post("/chat", json={"request": REQUEST}, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["booking_reference"].startswith("FL-")
    assert body["event_id"].startswith("EVT-")
    assert body["answer"]
    tools = [step["tool"] for step in body["steps"] if step["kind"] == "tool_call"]
    assert tools == [
        "flights_search_flights",
        "flights_book_flight",
        "calendar_check_availability",
        "calendar_create_event",
    ]


def test_chat_stream_emits_steps_then_done(client: TestClient) -> None:
    with client.stream(
        "POST", "/chat/stream", json={"request": REQUEST}, headers=HEADERS
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = "".join(response.iter_text())

    events = [block for block in raw.split("\n\n") if block.strip()]
    names = [block.splitlines()[0].removeprefix("event: ") for block in events]
    assert "step" in names
    assert names[-1] == "done"

    done = json.loads(events[-1].splitlines()[1].removeprefix("data: "))
    assert done["booking_reference"].startswith("FL-")
    assert done["event_id"].startswith("EVT-")


def test_missing_api_key_is_rejected(client: TestClient) -> None:
    response = client.post("/chat", json={"request": REQUEST})

    assert response.status_code == 401
    assert "correlation_id" in response.json()


def test_wrong_api_key_is_rejected(client: TestClient) -> None:
    response = client.post("/chat", json={"request": REQUEST}, headers={"X-API-Key": "nope"})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload, status",
    [
        ({}, 400),
        ({"request": ""}, 400),
        ({"request": "   "}, 400),
        ({"request": 42}, 400),
        ({"request": "x" * 5000}, 400),
    ],
)
def test_invalid_payloads_are_rejected(client: TestClient, payload: dict, status: int) -> None:
    response = client.post("/chat", json=payload, headers=HEADERS)

    assert response.status_code == status


def test_malformed_json_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/chat",
        content=b"{not json",
        headers={**HEADERS, "Content-Type": "application/json"},
    )

    assert response.status_code == 400


def test_oversized_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/chat",
        content=json.dumps({"request": "x" * 50_000}).encode(),
        headers={**HEADERS, "Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_rate_limit_returns_429(client: TestClient) -> None:
    statuses = [
        client.post("/chat", json={"request": "hello"}, headers=HEADERS).status_code
        for _ in range(7)
    ]

    assert 429 in statuses


def test_cors_allows_the_configured_origin_only(client: TestClient) -> None:
    allowed = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    blocked = client.options(
        "/chat",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_agent_failure_returns_a_generic_500(client: TestClient, monkeypatch) -> None:
    async def boom(*_args, **_kwargs):
        raise ValueError("internal detail that must not leak")

    monkeypatch.setattr(api, "run_agent", boom)

    response = client.post("/chat", json={"request": REQUEST}, headers=HEADERS)

    assert response.status_code == 500
    assert "internal detail" not in response.text
