from __future__ import annotations

import asyncio
from io import StringIO
from urllib.error import HTTPError, URLError

import pytest
from fastmcp.exceptions import ToolError

import server


def _mock_json_response(payload: str):
    return StringIO(payload)


def test_search_products_rejects_blank_query() -> None:
    with pytest.raises(ToolError, match="non-empty"):
        server.search_products("   ")


@pytest.mark.parametrize("limit", [0, 51])
def test_search_products_rejects_out_of_range_limit(limit: int) -> None:
    with pytest.raises(ToolError, match="limit must be between"):
        server.search_products("phone", limit=limit)


def test_search_products_rejects_negative_skip() -> None:
    with pytest.raises(ToolError, match="skip must be zero or greater"):
        server.search_products("phone", skip=-1)


def test_get_product_rejects_non_positive_id() -> None:
    with pytest.raises(ToolError, match="positive integer"):
        server.get_product(0)


def test_search_products_sends_encoded_request_and_returns_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, *, timeout: int):
        captured["url"] = request.full_url
        captured["accept"] = request.get_header("Accept")
        captured["user_agent"] = request.get_header("User-agent")
        captured["timeout"] = timeout
        return _mock_json_response('{"products":[{"id":1,"title":"Phone"}],"total":1}')

    monkeypatch.setattr(server, "urlopen", fake_urlopen)

    result = server.search_products("  phone & case  ", limit=1, skip=2)

    assert result == {"products": [{"id": 1, "title": "Phone"}], "total": 1}
    assert captured == {
        "url": (
            "https://dummyjson.com/products/search?"
            "q=phone+%26+case&limit=1&skip=2&"
            "select=id%2Ctitle%2Cdescription%2Ccategory%2Cprice%2C"
            "discountPercentage%2Crating%2Cstock%2Cbrand%2Cthumbnail"
        ),
        "accept": "application/json",
        "user_agent": "dummyjson-product-catalog-mcp/1.0",
        "timeout": 10,
    }


def test_get_product_fetches_requested_id(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url: str | None = None

    def fake_urlopen(request, *, timeout: int):
        nonlocal captured_url
        captured_url = request.full_url
        assert timeout == server.REQUEST_TIMEOUT_SECONDS
        return _mock_json_response('{"id":42,"title":"Product"}')

    monkeypatch.setattr(server, "urlopen", fake_urlopen)

    assert server.get_product(42) == {"id": 42, "title": "Product"}
    assert captured_url == "https://dummyjson.com/products/42?"


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            HTTPError("https://dummyjson.com/products/999", 404, "Not Found", None, None),
            "requested product was not found",
        ),
        (
            HTTPError("https://dummyjson.com/products", 503, "Unavailable", None, None),
            "DummyJSON returned HTTP 503",
        ),
        (URLError("offline"), "Could not reach DummyJSON"),
        (TimeoutError(), "did not respond within 10 seconds"),
    ],
)
def test_network_errors_are_returned_as_tool_errors(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    def fake_urlopen(request, *, timeout: int):
        raise error

    monkeypatch.setattr(server, "urlopen", fake_urlopen)

    with pytest.raises(ToolError, match=message):
        server.get_product(1)


def test_invalid_json_is_returned_as_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server,
        "urlopen",
        lambda request, *, timeout: _mock_json_response("not-json"),
    )

    with pytest.raises(ToolError, match="invalid JSON"):
        server.get_product(1)


@pytest.mark.parametrize("payload", ["[]", '"product"'])
def test_non_object_response_is_returned_as_tool_error(
    monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    monkeypatch.setattr(
        server,
        "urlopen",
        lambda request, *, timeout: _mock_json_response(payload),
    )

    with pytest.raises(ToolError, match="unexpected response format"):
        server.get_product(1)


def test_health_check_returns_ok() -> None:
    response = asyncio.run(server.health_check(None))

    assert response.status_code == 200
    assert response.body == b'{"status":"ok"}'
