# DummyJSON Product Catalog MCP Server

A read-only, remote streamable-HTTP MCP server that gives Claude two product-catalog tools backed by [DummyJSON Products](https://dummyjson.com/docs/products):

- `search_products`: Search sample catalog products by keyword with bounded pagination.
- `get_product`: Retrieve the complete record for a product ID.

DummyJSON is public sample data. This project does not use OAuth or require credentials.

## Run locally

Create and install into a project virtual environment:

```powershell
C:\Users\ailee\.local\bin\python3.14.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

The MCP endpoint is `http://localhost:3000/mcp`; the health check is `http://localhost:3000/health`.

## Test with MCP Inspector

With the server running:

```powershell
npx @modelcontextprotocol/inspector --cli http://localhost:3000/mcp --transport http --method tools/list
npx @modelcontextprotocol/inspector --cli http://localhost:3000/mcp --transport http --method tools/call --tool-name search_products --tool-arg query=phone
```

## Connect Claude after deployment

Deploy this app to an HTTPS-capable Python host, then add its `/mcp` URL under **Settings → Connectors → Add custom connector** in Claude. Before publicly sharing the connector, test the deployed endpoint with the MCP Inspector and Claude.
