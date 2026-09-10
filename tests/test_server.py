from __future__ import annotations

import asyncio

import pytest
from fastmcp.exceptions import ToolError

import server


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


def test_health_check_returns_ok() -> None:
    response = asyncio.run(server.health_check(None))

    assert response.status_code == 200
    assert response.body == b'{"status":"ok"}'
