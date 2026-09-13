"""Assembles and runs the LangGraph agent over both MCP servers."""

from __future__ import annotations

import warnings
from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from agent.config import (
    AGENT_MODEL,
    AWS_REGION,
    BEDROCK_MODEL_ID,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)
from agent.deps import build_client_group, get_system_prompt
from agent.mock_model import MockToolCallingModel
from agent.tool_results import parse_tool_content

# langchain.mcp is beta and warns on import; the warning is not actionable here.
warnings.filterwarnings("ignore", message=r".*`langchain\.mcp` is in beta.*")


def _build_model() -> Any:
    if AGENT_MODEL == "mock":
        return MockToolCallingModel()

    if AGENT_MODEL == "bedrock":
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(
            model=BEDROCK_MODEL_ID, region_name=AWS_REGION, temperature=0
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)


async def build_agent(target: Any = None, system_prompt: str | None = None) -> Any:
    """Discover tools from both MCP servers and return a ready-to-invoke agent."""
    from langchain.agents import create_agent
    from langchain.mcp import MCPAdapter

    model = _build_model()
    prompt = system_prompt if system_prompt is not None else await get_system_prompt()

    async with MCPAdapter(target if target is not None else build_client_group()) as adapter:
        tools = await adapter.list_tools()
        return create_agent(model, tools, system_prompt=prompt)


def _summarize(messages: list[Any]) -> dict[str, Any]:
    """Pull the final answer plus any identifiers the tools returned."""
    steps: list[dict[str, Any]] = []
    booking_reference: str | None = None
    event_id: str | None = None

    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            steps.append({"kind": "tool_call", "tool": call["name"], "args": call["args"]})
        if isinstance(message, ToolMessage):
            result = parse_tool_content(message.content)
            steps.append({"kind": "tool_result", "tool": message.name, "result": result})
            booking_reference = result.get("booking_reference") or booking_reference
            event_id = result.get("event_id") or event_id

    answer = ""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.text:
            answer = message.text
            break

    return {
        "answer": answer,
        "steps": steps,
        "booking_reference": booking_reference,
        "event_id": event_id,
    }


async def run_agent(request: str, target: Any = None) -> dict[str, Any]:
    """Run one holiday-planning request end to end and summarize the result."""
    agent = await build_agent(target)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": request}]})
    return _summarize(result["messages"])


async def stream_agent(request: str, target: Any = None) -> AsyncIterator[dict[str, Any]]:
    """Yield normalized events as the agent works, ending with a `done` event."""
    agent = await build_agent(target)
    messages: list[Any] = []

    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": request}]},
        stream_mode=["updates", "messages"],
        version="v2",
    ):
        if chunk["type"] == "messages":
            token, _ = chunk["data"]
            if isinstance(token, AIMessageChunk) and token.text:
                yield {"event": "token", "data": {"text": token.text}}
            continue

        if chunk["type"] != "updates":
            continue

        for node, update in chunk["data"].items():
            if node not in ("model", "tools"):
                continue
            for message in update.get("messages", []):
                messages.append(message)
                for call in getattr(message, "tool_calls", None) or []:
                    yield {
                        "event": "step",
                        "data": {"kind": "tool_call", "tool": call["name"], "args": call["args"]},
                    }
                if isinstance(message, ToolMessage):
                    yield {
                        "event": "step",
                        "data": {
                            "kind": "tool_result",
                            "tool": message.name,
                            "result": parse_tool_content(message.content),
                        },
                    }

    yield {"event": "done", "data": _summarize(messages)}
