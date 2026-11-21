"""Lambda deployment pieces: SigV4 signing for MCP calls and the per-function ASGI apps."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import httpx2
import pytest
from fastmcp.client.transports import StreamableHttpTransport

import agent.aws_auth as aws_auth
from agent.aws_auth import SigV4Auth, make_mcp_client

# lambda/lambda_handlers.py is a deployment entry module, not part of a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))


@pytest.fixture
def fake_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-example")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)


def _sign(url: str, body: bytes) -> httpx2.Request:
    request = httpx2.Request(
        "POST",
        url,
        content=body,
        headers={"Content-Type": "application/json"},
    )
    flow = SigV4Auth(region="eu-west-2").auth_flow(request)
    signed = next(flow)
    with pytest.raises(StopIteration):
        next(flow)
    return signed


def test_sigv4_auth_signs_request_for_lambda(fake_aws_credentials: None) -> None:
    url = "https://abc123.lambda-url.eu-west-2.on.aws/mcp"
    signed = _sign(url, b'{"jsonrpc":"2.0"}')

    authorization = signed.headers["authorization"]
    assert authorization.startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
    assert "/eu-west-2/lambda/aws4_request" in authorization
    assert "x-amz-date" in signed.headers


def test_make_mcp_client_plain_when_iam_auth_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aws_auth, "MCP_IAM_AUTH", False)
    client = make_mcp_client("http://127.0.0.1:3001/mcp")

    assert isinstance(client.transport, StreamableHttpTransport)
    assert client.transport.auth is None


def test_make_mcp_client_signs_when_iam_auth_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aws_auth, "MCP_IAM_AUTH", True)
    client = make_mcp_client("https://abc123.lambda-url.eu-west-2.on.aws/mcp")

    assert isinstance(client.transport, StreamableHttpTransport)
    assert isinstance(client.transport.auth, SigV4Auth)


@pytest.mark.parametrize(
    "app_name, server",
    [("flights_app", "flight-search"), ("calendar_app", "personal-calendar")],
)
def test_mcp_lambda_app_serves_health(app_name: str, server: str) -> None:
    from lambda_handlers import calendar_app, flights_app

    app = {"flights_app": flights_app, "calendar_app": calendar_app}[app_name]

    async def fetch() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://lambda") as client:
            return await client.get("/health")

    response = asyncio.run(fetch())
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "server": server}
