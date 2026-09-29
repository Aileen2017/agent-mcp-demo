"""HTTP API in front of the holiday-planning agent.

POST /chat        -> one JSON answer
POST /chat/stream -> server-sent events as the agent works
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from typing import Any, AsyncIterator

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from agent.config import (
    ALLOWED_ORIGINS,
    API_HOST,
    API_KEY,
    API_PORT,
    MAX_BODY_BYTES,
    MAX_REQUEST_CHARS,
    RATE_LIMIT_PER_MINUTE,
    REQUEST_TIMEOUT_SECONDS,
    is_loopback,
)
from agent.deps import get_system_prompt
from agent.graph import run_agent, stream_agent

logger = logging.getLogger("agent.api")

_recent_calls: dict[str, deque[float]] = defaultdict(deque)


class RequestRejected(Exception):
    """A guard refused the request before the agent ran."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    calls = _recent_calls[ip]
    while calls and now - calls[0] > 60:
        calls.popleft()
    if len(calls) >= RATE_LIMIT_PER_MINUTE:
        raise RequestRejected(429, "Rate limit exceeded. Try again in a minute.")
    calls.append(now)


def _check_api_key(request: Request) -> None:
    if not API_KEY:
        return
    provided = request.headers.get("x-api-key", "")
    if not secrets.compare_digest(provided, API_KEY):
        raise RequestRejected(401, "Missing or invalid API key.")


async def _read_request_text(request: Request) -> str:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise RequestRejected(413, f"Request body must be under {MAX_BODY_BYTES} bytes.")

    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError as error:
        raise RequestRejected(400, "Body must be valid JSON.") from error
    if not isinstance(payload, dict):
        raise RequestRejected(400, "Body must be a JSON object.")

    text = payload.get("request")
    if not isinstance(text, str) or not text.strip():
        raise RequestRejected(400, "Field 'request' is required and must be a non-empty string.")
    if len(text) > MAX_REQUEST_CHARS:
        raise RequestRejected(400, f"Field 'request' must be under {MAX_REQUEST_CHARS} characters.")

    return text.strip()


async def _guard(request: Request) -> str:
    _check_api_key(request)
    _check_rate_limit(_client_ip(request))
    return await _read_request_text(request)


def _error(status: int, message: str, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        {"error": message, "correlation_id": correlation_id},
        status_code=status,
        headers={"X-Correlation-Id": correlation_id},
    )


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def chat(request: Request) -> Response:
    correlation_id = str(uuid.uuid4())
    try:
        text = await _guard(request)
    except RequestRejected as rejected:
        return _error(rejected.status, rejected.message, correlation_id)

    try:
        result = await asyncio.wait_for(run_agent(text), timeout=REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Agent run timed out", extra={"correlation_id": correlation_id})
        return _error(504, "The agent took too long to respond.", correlation_id)
    except Exception:
        logger.exception("Agent run failed", extra={"correlation_id": correlation_id})
        return _error(500, "The agent failed to complete this request.", correlation_id)

    return JSONResponse(result, headers={"X-Correlation-Id": correlation_id})


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def chat_stream(request: Request) -> Response:
    correlation_id = str(uuid.uuid4())
    try:
        text = await _guard(request)
    except RequestRejected as rejected:
        return _error(rejected.status, rejected.message, correlation_id)

    async def events() -> AsyncIterator[str]:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async for event in stream_agent(text):
                    yield _sse(event["event"], event["data"])
        except asyncio.TimeoutError:
            logger.warning("Agent stream timed out", extra={"correlation_id": correlation_id})
            yield _sse("error", {"error": "The agent took too long to respond."})
        except Exception:
            logger.exception("Agent stream failed", extra={"correlation_id": correlation_id})
            yield _sse("error", {"error": "The agent failed to complete this request."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Correlation-Id": correlation_id,
        },
    )


@contextlib.asynccontextmanager
async def _lifespan(_: Starlette) -> AsyncIterator[None]:
    try:
        await get_system_prompt()
    except RuntimeError as error:
        logger.warning("Could not preload the system prompt: %s", error)
    yield


def create_app() -> Starlette:
    if not API_KEY and not is_loopback(API_HOST):
        raise RuntimeError(
            f"AGENT_API_KEY must be set when binding to {API_HOST}. "
            "This endpoint reaches tools that create bookings and calendar events."
        )
    if not API_KEY:
        logger.warning("AGENT_API_KEY is not set; the API is unauthenticated on %s.", API_HOST)

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/chat", chat, methods=["POST"]),
            Route("/chat/stream", chat_stream, methods=["POST"]),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=ALLOWED_ORIGINS,
                allow_methods=["POST", "GET"],
                allow_headers=["Content-Type", "X-API-Key"],
            )
        ],
        lifespan=_lifespan,
    )


app = create_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=API_HOST, port=API_PORT)
