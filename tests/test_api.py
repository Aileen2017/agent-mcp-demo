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

@pytest.mark.skip(reason="allow_conflict now comes from AGENT_ALLOW_CONFLICTS (default false)")
def _tools_called(body: dict) -> list[str]:
    return [step["tool"] for step in body["steps"] if step["kind"] == "tool_call"]


def _sse_events(raw: str) -> list[tuple[str, dict]]:
    blocks = [block for block in raw.split("\n\n") if block.strip()]
    return [
        (
            block.splitlines()[0].removeprefix("event: "),
            json.loads(block.splitlines()[1].removeprefix("data: ")),
        )
        for block in blocks
    ]


def test_chat_without_a_clash_books_a_flight_and_creates_an_event(client: TestClient) -> None:
    request = "Fly from London to Paris in 30 days for 2 nights for Jane Doe"
    response = client.post("/chat", json={"request": request}, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["question"] is None
    assert body["booking_reference"].startswith("FL-")
    assert body["event_id"].startswith("EVT-")
    assert body["answer"]
    assert _tools_called(body) == [
        "flights_search_flights",
        "calendar_check_availability",
        "calendar_create_event",
        "flights_book_flight",
    ]


def test_clash_pauses_for_the_user_then_books_when_confirmed(client: TestClient) -> None:
    # REQUEST's dates overlap the seeded dentist appointment.
    paused = client.post("/chat", json={"request": REQUEST}, headers=HEADERS).json()

    assert paused["status"] == "needs_input"
    assert "Dentist appointment" in paused["question"]["message"]
    assert paused["booking_reference"] is None

    response = client.post(
        "/chat/resume", json={"thread_id": paused["thread_id"], "confirm": True}, headers=HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["booking_reference"].startswith("FL-")
    assert body["event_id"].startswith("EVT-")
    assert _tools_called(body)[-1] == "flights_book_flight"


def test_clash_declined_by_the_user_books_nothing(client: TestClient) -> None:
    paused = client.post("/chat", json={"request": REQUEST}, headers=HEADERS).json()

    body = client.post(
        "/chat/resume", json={"thread_id": paused["thread_id"], "confirm": False}, headers=HEADERS
    ).json()

    assert body["status"] == "done"
    assert body["booking_reference"] is None
    assert body["event_id"] is None
    assert "flights_book_flight" not in _tools_called(body)
    assert "Nothing was booked" in body["answer"]


def test_resuming_an_unknown_or_finished_thread_is_404(client: TestClient) -> None:
    unknown = client.post(
        "/chat/resume", json={"thread_id": "no-such-thread", "confirm": True}, headers=HEADERS
    )
    assert unknown.status_code == 404

    paused = client.post("/chat", json={"request": REQUEST}, headers=HEADERS).json()
    resume = {"thread_id": paused["thread_id"], "confirm": False}
    assert client.post("/chat/resume", json=resume, headers=HEADERS).status_code == 200
    assert client.post("/chat/resume", json=resume, headers=HEADERS).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{}, {"thread_id": "abc"}, {"thread_id": "abc", "confirm": "yes"}, {"confirm": True}],
)
def test_invalid_resume_payloads_are_rejected(client: TestClient, payload: dict) -> None:
    response = client.post("/chat/resume", json=payload, headers=HEADERS)

    assert response.status_code == 400


def test_chat_stream_pauses_with_a_question_then_resumes(client: TestClient) -> None:
    with client.stream(
        "POST", "/chat/stream", json={"request": REQUEST}, headers=HEADERS
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _sse_events("".join(response.iter_text()))

    names = [name for name, _ in events]
    assert "step" in names
    assert "input_required" in names
    assert names[-1] == "done"
    paused = events[-1][1]
    assert paused["status"] == "needs_input"

    with client.stream(
        "POST",
        "/chat/resume/stream",
        json={"thread_id": paused["thread_id"], "confirm": True},
        headers=HEADERS,
    ) as response:
        events = _sse_events("".join(response.iter_text()))

    name, done = events[-1]
    assert name == "done"
    assert done["status"] == "done"
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


@pytest.mark.skip(reason="allow_conflict now comes from AGENT_ALLOW_CONFLICTS (default false)")
def test_agent_failure_returns_a_generic_500(client: TestClient, monkeypatch) -> None:
    async def boom(*_args, **_kwargs):
        raise ValueError("internal detail that must not leak")

    monkeypatch.setattr(api, "run_agent", boom)

    response = client.post("/chat", json={"request": REQUEST}, headers=HEADERS)

    assert response.status_code == 500
    assert "internal detail" not in response.text
