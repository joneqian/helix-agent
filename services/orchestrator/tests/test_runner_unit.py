"""Unit tests for :class:`orchestrator.runner.GraphRunner`.

In-memory checkpointer is enough to prove the wiring contract — Postgres
round-trip is covered separately in ``test_runner_integration.py``.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from helix_agent.runtime.checkpointer import make_checkpointer
from orchestrator import AgentState, GraphRunner


def _build_echo_graph() -> StateGraph[AgentState, None, AgentState, AgentState]:
    """Trivial graph: one node that appends a fixed AI response."""

    def respond(state: AgentState) -> dict[str, list[BaseMessage]]:
        return {"messages": [AIMessage(content="ok")]}

    graph: StateGraph[AgentState, None, AgentState, AgentState] = StateGraph(AgentState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph


@pytest.mark.asyncio
async def test_compile_attaches_checkpointer() -> None:
    """``GraphRunner.compile`` must hand the saver to ``StateGraph.compile``.

    Verified by running the compiled graph once and reading back the
    saved state via ``aget_state`` on the same compiled instance.
    """
    async with make_checkpointer("memory") as cp:
        runner = GraphRunner(checkpointer=cp)
        assert runner.checkpointer is cp

        compiled = runner.compile(_build_echo_graph())
        cfg: RunnableConfig = {"configurable": {"thread_id": "t-unit-1"}}
        await compiled.ainvoke({"messages": [HumanMessage(content="hi")]}, config=cfg)

        snapshot = await compiled.aget_state(cfg)
        contents = [m.content for m in snapshot.values["messages"]]
        assert contents == ["hi", "ok"]


@pytest.mark.asyncio
async def test_checkpoint_visible_across_runner_instances() -> None:
    """Two ``GraphRunner`` instances sharing one saver see each other's state.

    This is the smallest meaningful "restart" simulation possible without
    Postgres: a new ``GraphRunner`` re-compiles the same graph against
    the same saver and must observe the prior run's state.
    """
    async with make_checkpointer("memory") as cp:
        cfg: RunnableConfig = {"configurable": {"thread_id": "t-unit-2"}}

        runner_a = GraphRunner(checkpointer=cp)
        compiled_a = runner_a.compile(_build_echo_graph())
        await compiled_a.ainvoke({"messages": [HumanMessage(content="hi")]}, config=cfg)

        runner_b = GraphRunner(checkpointer=cp)
        compiled_b = runner_b.compile(_build_echo_graph())
        snapshot = await compiled_b.aget_state(cfg)
        contents = [m.content for m in snapshot.values["messages"]]
        assert contents == ["hi", "ok"]


@pytest.mark.asyncio
async def test_thread_isolation() -> None:
    """Different ``thread_id`` values must not see each other's state."""
    async with make_checkpointer("memory") as cp:
        runner = GraphRunner(checkpointer=cp)
        compiled = runner.compile(_build_echo_graph())

        cfg_a: RunnableConfig = {"configurable": {"thread_id": "t-a"}}
        await compiled.ainvoke({"messages": [HumanMessage(content="thread-a")]}, config=cfg_a)

        cfg_b: RunnableConfig = {"configurable": {"thread_id": "t-b"}}
        snapshot_b = await compiled.aget_state(cfg_b)
        assert snapshot_b.values == {}, "fresh thread_id must see empty state"
