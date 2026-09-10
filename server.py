"""Read-only MCP connector for the DummyJSON product catalog."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

API_BASE_URL = "https://dummyjson.com"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RESULTS = 50

mcp = FastMCP(
    name="dummyjson-product-catalog",
    instructions=(
        "Use search_products to find product IDs before calling get_product. "
        "All catalog data is sample data supplied by DummyJSON."
    ),
)


def _get_json(path: str, query: dict[str, str | int]) -> dict[str, Any]:
    url = f"{API_BASE_URL}{path}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "dummyjson-product-catalog-mcp/1.0",
        },
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            raise ToolError("The requested product was not found.") from error
        raise ToolError(
            f"DummyJSON returned HTTP {error.code}. Please retry shortly."
        ) from error
    except URLError as error:
        raise ToolError(
            "Could not reach DummyJSON. Check the server's internet connection and retry."
        ) from error
    except TimeoutError as error:
        raise ToolError("DummyJSON did not respond within 10 seconds. Please retry.") from error
    except json.JSONDecodeError as error:
        raise ToolError("DummyJSON returned an invalid JSON response. Please retry.") from error

    if not isinstance(payload, dict):
        raise ToolError("DummyJSON returned an unexpected response format.")

    return payload


@mcp.tool(
    annotations={
        "title": "Search DummyJSON products",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
def search_products(query: str, limit: int = 10, skip: int = 0) -> dict[str, Any]:
    """Search sample products by keyword, returning IDs and catalog details for matching items."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ToolError("Provide a non-empty product search query.")
    if not 1 <= limit <= MAX_RESULTS:
        raise ToolError(f"limit must be between 1 and {MAX_RESULTS}.")
    if skip < 0:
        raise ToolError("skip must be zero or greater.")

    return _get_json(
        "/products/search",
        {
            "q": normalized_query,
            "limit": limit,
            "skip": skip,
            "select": "id,title,description,category,price,discountPercentage,rating,stock,brand,thumbnail",
        },
    )


@mcp.tool(
    annotations={
        "title": "Get a DummyJSON product",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
def get_product(product_id: int) -> dict[str, Any]:
    """Fetch the complete sample catalog record for one product ID returned by search_products."""
    if product_id < 1:
        raise ToolError("product_id must be a positive integer.")

    return _get_json(f"/products/{product_id}", {})


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: StarletteRequest) -> JSONResponse:
    """Return service health without exposing MCP details."""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=3000)
