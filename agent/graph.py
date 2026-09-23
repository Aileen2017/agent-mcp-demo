"""Assembles and runs the LangGraph agent over both MCP servers."""

from __future__ import annotations

import uuid
import warnings
from typing import Any, AsyncIterator

from langgraph.graph.state import CompiledStateGraph

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

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

# Holds paused runs so a later call can resume them by thread id. In memory only:
# a restart forgets every paused run.
_checkpointer = InMemorySaver()


class UnknownThread(LookupError):
    """No paused run exists for the given thread id."""


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


async def build_agent(target: Any = None, system_prompt: str | None = None) -> CompiledStateGraph:
    """Discover tools from both MCP servers and return a ready-to-invoke agent."""
    from langchain.agents import create_agent
    from langchain.mcp import MCPAdapter

    model = _build_model()
    prompt = system_prompt if system_prompt is not None else await get_system_prompt()

    async with MCPAdapter(target if target is not None else build_client_group()) as adapter:
        tools = await adapter.list_tools()
        return create_agent(model, tools, system_prompt=prompt, checkpointer=_checkpointer)


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _question(interrupts: Any) -> dict[str, Any] | None:
    """Turn a pending MCP elicitation interrupt into a question for the user."""
    for pending in interrupts or ():
        value = getattr(pending, "value", None)
        if isinstance(value, dict) and value.get("type") == "mcp_elicitation":
            return {
                "tool": value["tool_name"],
                "message": "\n".join(request["message"] for request in value["requests"]),
            }
    return None


def _answer(requests: list[dict[str, Any]], confirmed: bool) -> dict[str, Any]:
    """Resume value answering every yes/no question in one elicitation round."""
    responses: dict[str, Any] = {}
    for request in requests:
        if not confirmed:
            responses[request["key"]] = {"action": "decline"}
            continue
        properties = request.get("requested_schema", {}).get("properties", {})
        content = {
            name: True for name, schema in properties.items() if schema.get("type") == "boolean"
        }
        responses[request["key"]] = {"action": "accept", "content": content}
    return {"responses": responses}


async def _resume_command(agent: Any, thread_id: str, confirmed: bool) -> Command:
    state = await agent.aget_state(_config(thread_id))
    for pending in state.interrupts:
        value = pending.value
        if isinstance(value, dict) and value.get("type") == "mcp_elicitation":
            return Command(resume=_answer(value["requests"], confirmed))
    raise UnknownThread(f"No paused run is waiting for an answer on thread {thread_id}.")


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


def _outcome(
    messages: list[Any], thread_id: str, question: dict[str, Any] | None
) -> dict[str, Any]:
    """Summary plus whether the run finished or is paused waiting on the user."""
    return {
        **_summarize(messages),
        "status": "needs_input" if question else "done",
        "thread_id": thread_id,
        "question": question,
    }


async def run_agent(request: str, target: Any = None) -> dict[str, Any]:
    """Run one holiday-planning request until it finishes or needs the user to decide.

    A result with status "needs_input" carries a question; answer it with resume_agent.
    """
    agent = await build_agent(target)
    thread_id = str(uuid.uuid4())
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": request}]}, _config(thread_id)
    )
    return _outcome(result["messages"], thread_id, _question(result.get("__interrupt__")))


async def resume_agent(thread_id: str, confirmed: bool, target: Any = None) -> dict[str, Any]:
    """Answer a paused run's question (yes/no) and let it carry on."""
    agent = await build_agent(target)
    command = await _resume_command(agent, thread_id, confirmed)
    result = await agent.ainvoke(command, _config(thread_id))
    return _outcome(result["messages"], thread_id, _question(result.get("__interrupt__")))


async def stream_agent(
    request: str | None,
    target: Any = None,
    *,
    thread_id: str | None = None,
    confirmed: bool | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield normalized events as the agent works, ending with a `done` event.

    Pass thread_id and confirmed instead of a request to resume a paused run.
    If the run pauses for a question, the `done` event has status "needs_input".
    """
    agent = await build_agent(target)
    if thread_id is not None and confirmed is not None:
        run_input: Any = await _resume_command(agent, thread_id, confirmed)
        state = await agent.aget_state(_config(thread_id))
        messages: list[Any] = list(state.values.get("messages", []))
    else:
        thread_id = str(uuid.uuid4())
        run_input = {"messages": [{"role": "user", "content": request}]}
        messages = []
    question: dict[str, Any] | None = None

    async for chunk in agent.astream(
        run_input,
        _config(thread_id),
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
            if node == "__interrupt__":
                question = _question(update)
                if question:
                    yield {"event": "input_required", "data": question}
                continue
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

    yield {"event": "done", "data": _outcome(messages, thread_id, question)}
