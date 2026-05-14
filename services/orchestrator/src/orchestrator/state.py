"""Canonical LangGraph state shape for orchestrator graphs.

Per [STREAM-E-DESIGN § 2.3](../../../../docs/streams/STREAM-E-DESIGN.md),
fields are added incrementally across the Stream E sub-PRs:

- **E.1 (this PR)**: ``messages`` (LangGraph reducer-style append)
- E.6: ``step_count``, ``max_steps`` for ReAct loop guard
- E.11: ``provider_chain``, ``current_provider_idx`` for LLM fallback routing
- E.15: ``cancellation_token`` (runtime-only, ``__skip_checkpoint__``)

Tenant binding (``tenant_id`` / ``session_id`` / ``run_id``) is passed via
the ``config["configurable"]`` channel (LangGraph idiom) and does not live
on ``AgentState`` — graphs read it from ``RunnableConfig`` so the same
state shape works for any tenant.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State threaded through every orchestrator LangGraph node.

    The ``messages`` field uses LangGraph's ``add_messages`` reducer so
    that any node returning ``{"messages": [...]}`` appends to (rather
    than overwriting) the conversation history.
    """

    messages: Annotated[list[BaseMessage], add_messages]
