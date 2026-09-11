"""Assembles the LangGraph agent from both MCP servers."""

from __future__ import annotations

import warnings
from typing import Any

from agent.config import AGENT_MODEL, MCP_CONFIG, OLLAMA_BASE_URL, OLLAMA_MODEL
from agent.context import build_system_prompt
from agent.mock_model import MockToolCallingModel

# langchain.mcp is beta and warns on import; the warning is not actionable here.
warnings.filterwarnings("ignore", message=r".*`langchain\.mcp` is in beta.*")


def _build_model() -> Any:
    if AGENT_MODEL == "mock":
        return MockToolCallingModel()

    from langchain_ollama import ChatOllama

    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)


async def build_agent(mcp_config: dict[str, Any] | None = None) -> Any:
    """Discover tools from both MCP servers and return a ready-to-invoke agent."""
    from langchain.agents import create_agent
    from langchain.mcp import MCPAdapter

    model = _build_model()
    system_prompt = await build_system_prompt()

    async with MCPAdapter(mcp_config or MCP_CONFIG) as adapter:
        tools = await adapter.list_tools()
        return create_agent(model, tools, system_prompt=system_prompt)


async def run_agent(request: str) -> dict[str, Any]:
    """Run one holiday-planning request end to end."""
    agent = await build_agent()
    return await agent.ainvoke({"messages": [{"role": "user", "content": request}]})
