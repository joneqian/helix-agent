"""Unit tests for J.4 sub-agent delegation — scaffold + ``SubAgentTool``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from helix_agent.protocol import SubAgentSpec
from helix_agent.runtime.cancellation import (
    CANCELLATION_TOKEN_KEY,
    CancellationToken,
    RunCancelledError,
)
from orchestrator import GraphRunner, ToolRegistry, build_react_graph
from orchestrator.agent_factory import BuiltAgent
from orchestrator.errors import MaxStepsExceededError
from orchestrator.tools import (
    MAX_SUBAGENT_DEPTH,
    ChildAgentBuilder,
    SubAgentTool,
    Tool,
    ToolBlockedError,
    ToolContext,
    ToolEnv,
)

_SUB = SubAgentSpec(
    name="researcher",
    agent_ref="deep-researcher@1.0.0",
    description="Delegates deep research subtasks.",
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeGraph:
    """Fake compiled child graph — records each ``ainvoke`` and returns or
    raises a scripted outcome."""

    result: dict[str, Any] | None = None
    raises: BaseException | None = None
    calls: list[tuple[Any, Any]] = field(default_factory=list)

    async def ainvoke(self, state: Any, config: Any) -> Any:
        self.calls.append((state, config))
        if self.raises is not None:
            raise self.raises
        return self.result


@dataclass
class _RecordingBuilder:
    """Conforms to :class:`ChildAgentBuilder`; records its keyword args and
    returns a scripted :class:`BuiltAgent` (or raises)."""

    built: BuiltAgent | None = None
    raises: BaseException | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def __call__(
        self,
        *,
        tenant_id: UUID,
        name: str,
        version: str,
        depth: int,
    ) -> BuiltAgent:
        self.calls.append(
            {"tenant_id": tenant_id, "name": name, "version": version, "depth": depth}
        )
        if self.raises is not None:
            raise self.raises
        if self.built is None:
            raise RuntimeError("test misconfigured: _RecordingBuilder has no BuiltAgent")
        return self.built


def _built(
    graph: _FakeGraph, *, system_prompt: str = "child prompt", max_steps: int = 5
) -> BuiltAgent:
    return BuiltAgent(graph=graph, system_prompt=system_prompt, max_steps=max_steps)  # type: ignore[arg-type]


def _ctx(*, tenant_id: UUID | None = None, **kw: Any) -> ToolContext:
    return ToolContext(
        tenant_id=uuid4() if tenant_id is None else tenant_id,
        cancellation_token=CancellationToken(),
        **kw,
    )


# ---------------------------------------------------------------------------
# Scaffold — ChildAgentBuilder protocol + depth cap
# ---------------------------------------------------------------------------


def test_max_subagent_depth_is_3() -> None:
    assert MAX_SUBAGENT_DEPTH == 3


def test_child_agent_builder_protocol_accepts_conforming_callable() -> None:
    # runtime_checkable — a class with an async __call__ satisfies the
    # Protocol, so the control-plane's injected callback type-checks.
    assert isinstance(_RecordingBuilder(), ChildAgentBuilder)


def test_child_agent_builder_protocol_rejects_non_callable() -> None:
    assert not isinstance(object(), ChildAgentBuilder)


def test_tool_env_child_agent_builder_defaults_none() -> None:
    # An empty ToolEnv has no sub-agent builder — a manifest declaring
    # subagents against it raises AgentFactoryError (wired in J.4 PR4).
    assert ToolEnv().child_agent_builder is None


def test_tool_env_carries_child_agent_builder() -> None:
    builder = _RecordingBuilder()
    assert ToolEnv(child_agent_builder=builder).child_agent_builder is builder


# ---------------------------------------------------------------------------
# SubAgentTool.spec
# ---------------------------------------------------------------------------


def test_subagent_tool_satisfies_tool_protocol() -> None:
    tool = SubAgentTool(subagent=_SUB, builder=_RecordingBuilder(), child_depth=1)
    assert isinstance(tool, Tool)


def test_spec_exposes_subagent_name_and_task_param() -> None:
    spec = SubAgentTool(subagent=_SUB, builder=_RecordingBuilder(), child_depth=1).spec
    assert spec.name == "researcher"
    assert spec.description == _SUB.description
    assert spec.parameters["required"] == ["task"]
    assert "task" in spec.parameters["properties"]


# ---------------------------------------------------------------------------
# SubAgentTool.call — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_returns_child_final_answer() -> None:
    graph = _FakeGraph(
        result={"messages": [HumanMessage(content="task"), AIMessage(content="delegated answer")]}
    )
    builder = _RecordingBuilder(built=_built(graph))
    tool = SubAgentTool(subagent=_SUB, builder=builder, child_depth=2)
    ctx = _ctx()

    result = await tool.call({"task": "do research"}, ctx=ctx)

    assert result.content == "delegated answer"
    assert result.meta["subagent"] == "researcher"
    # agent_ref resolved + child depth handed to the builder verbatim.
    assert builder.calls == [
        {"tenant_id": ctx.tenant_id, "name": "deep-researcher", "version": "1.0.0", "depth": 2}
    ]


@pytest.mark.asyncio
async def test_call_seeds_child_input_with_prompt_and_task() -> None:
    graph = _FakeGraph(result={"messages": [AIMessage(content="ok")]})
    tool = SubAgentTool(
        subagent=_SUB, builder=_RecordingBuilder(built=_built(graph, max_steps=7)), child_depth=1
    )

    await tool.call({"task": "  summarise the doc  "}, ctx=_ctx())

    state, _config = graph.calls[0]
    assert isinstance(state["messages"][0], SystemMessage)
    assert state["messages"][0].content == "child prompt"
    assert isinstance(state["messages"][1], HumanMessage)
    assert state["messages"][1].content == "summarise the doc"  # trimmed
    assert state["step_count"] == 0
    assert state["max_steps"] == 7


@pytest.mark.asyncio
async def test_child_run_shares_parent_cancellation_token() -> None:
    graph = _FakeGraph(result={"messages": [AIMessage(content="ok")]})
    tool = SubAgentTool(
        subagent=_SUB, builder=_RecordingBuilder(built=_built(graph)), child_depth=1
    )
    token = CancellationToken()
    tenant = uuid4()
    user = uuid4()

    await tool.call(
        {"task": "x"},
        ctx=ToolContext(tenant_id=tenant, user_id=user, cancellation_token=token),
    )

    _state, config = graph.calls[0]
    configurable = config["configurable"]
    # Parent token shared verbatim — a parent cancel reaches the child.
    assert configurable[CANCELLATION_TOKEN_KEY] is token
    assert configurable["tenant_id"] == str(tenant)
    assert configurable["user_id"] == str(user)
    # Fresh child thread / run — delegation is one-shot.
    assert configurable["thread_id"] != configurable["run_id"]


# ---------------------------------------------------------------------------
# SubAgentTool.call — guards + error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_requires_tenant_binding() -> None:
    tool = SubAgentTool(subagent=_SUB, builder=_RecordingBuilder(), child_depth=1)
    ctx = ToolContext(tenant_id=None, cancellation_token=CancellationToken())
    with pytest.raises(ToolBlockedError, match="tenant binding"):
        await tool.call({"task": "x"}, ctx=ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_args", [{}, {"task": ""}, {"task": "   "}, {"task": 123}])
async def test_call_rejects_missing_task(bad_args: dict[str, Any]) -> None:
    tool = SubAgentTool(subagent=_SUB, builder=_RecordingBuilder(), child_depth=1)
    with pytest.raises(ValueError, match="non-empty 'task'"):
        await tool.call(bad_args, ctx=_ctx())


@pytest.mark.asyncio
async def test_builder_error_propagates() -> None:
    # An unresolvable agent_ref (deleted / not found) is left to propagate
    # — the parent's tools node turns it into a ToolMessage error.
    builder = _RecordingBuilder(raises=KeyError("agent_ref not found"))
    tool = SubAgentTool(subagent=_SUB, builder=builder, child_depth=1)
    with pytest.raises(KeyError):
        await tool.call({"task": "x"}, ctx=_ctx())


@pytest.mark.asyncio
async def test_child_max_steps_returns_partial_note() -> None:
    graph = _FakeGraph(raises=MaxStepsExceededError(step_count=5, max_steps=5))
    tool = SubAgentTool(
        subagent=_SUB, builder=_RecordingBuilder(built=_built(graph)), child_depth=1
    )

    result = await tool.call({"task": "x"}, ctx=_ctx())

    # Out-of-steps is a partial result, not a tool failure.
    assert result.meta["subagent_max_steps"] is True
    assert "step limit" in result.content


@pytest.mark.asyncio
async def test_child_cancellation_propagates() -> None:
    # A cancel tears the whole run down — it must NOT be swallowed into a
    # normal ToolResult the way max_steps is.
    graph = _FakeGraph(raises=RunCancelledError("run cancelled"))
    tool = SubAgentTool(
        subagent=_SUB, builder=_RecordingBuilder(built=_built(graph)), child_depth=1
    )
    with pytest.raises(RunCancelledError):
        await tool.call({"task": "x"}, ctx=_ctx())


@pytest.mark.asyncio
async def test_child_with_no_ai_message_returns_empty_note() -> None:
    graph = _FakeGraph(result={"messages": [HumanMessage(content="task")]})
    tool = SubAgentTool(
        subagent=_SUB, builder=_RecordingBuilder(built=_built(graph)), child_depth=1
    )

    result = await tool.call({"task": "x"}, ctx=_ctx())

    assert result.meta["subagent_empty"] is True
    assert "no answer" in result.content


@pytest.mark.asyncio
async def test_call_picks_last_ai_message() -> None:
    messages: list[BaseMessage] = [
        AIMessage(content="first thought"),
        HumanMessage(content="tool result"),
        AIMessage(content="final answer"),
    ]
    graph = _FakeGraph(result={"messages": messages})
    tool = SubAgentTool(
        subagent=_SUB, builder=_RecordingBuilder(built=_built(graph)), child_depth=1
    )

    result = await tool.call({"task": "x"}, ctx=_ctx())

    assert result.content == "final answer"


# ---------------------------------------------------------------------------
# End-to-end — a parent agent delegates to a child through the real graph
# ---------------------------------------------------------------------------


async def _child_llm(*, messages: Any, tools: Any) -> AIMessage:
    """Child agent's LLM — echoes the delegated task, no tool calls."""
    del tools
    human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    task = human.content if human is not None else "?"
    return AIMessage(content=f"CHILD HANDLED: {task}", id="child-ai")


class _ParentLLM:
    """Parent agent's LLM — delegates on the first step, then finishes."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *, messages: Any, tools: Any) -> AIMessage:
        del messages, tools
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                id="parent-ai-1",
                tool_calls=[
                    {"name": "researcher", "args": {"task": "investigate X"}, "id": "tc-1"}
                ],
            )
        return AIMessage(content="PARENT DONE", id="parent-ai-2")


@pytest.mark.asyncio
async def test_parent_delegates_to_child_through_real_graph() -> None:
    # Build a real child agent graph over a fake LLM.
    child_graph = GraphRunner(checkpointer=InMemorySaver()).compile(
        build_react_graph(llm_caller=_child_llm, tool_registry=ToolRegistry())
    )
    child = BuiltAgent(graph=child_graph, system_prompt="child prompt", max_steps=5)

    # Parent registry carries one SubAgentTool resolving to that child.
    registry = ToolRegistry()
    registry.register(
        SubAgentTool(subagent=_SUB, builder=_RecordingBuilder(built=child), child_depth=1)
    )
    parent_graph = GraphRunner(checkpointer=InMemorySaver()).compile(
        build_react_graph(llm_caller=_ParentLLM(), tool_registry=registry)
    )

    result = await parent_graph.ainvoke(
        {"messages": [HumanMessage(content="delegate this")], "step_count": 0, "max_steps": 5},
        {"configurable": {"thread_id": str(uuid4()), "tenant_id": str(uuid4())}},
    )

    messages = result["messages"]
    # The child's answer flowed back as the SubAgentTool's ToolMessage.
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].content == "CHILD HANDLED: investigate X"
    # The parent then reasoned over it and finished.
    assert isinstance(messages[-1], AIMessage)
    assert messages[-1].content == "PARENT DONE"
