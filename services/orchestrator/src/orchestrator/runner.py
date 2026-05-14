"""LangGraph execution surface — the orchestrator's only graph entrypoint.

Per [STREAM-E-DESIGN § 4.1](../../../../docs/streams/STREAM-E-DESIGN.md),
``GraphRunner`` centralises the wiring between a user-supplied
:class:`langgraph.graph.StateGraph` and the shared checkpointer so that
every compiled graph in the service writes to the same durable store.

The current sub-PR (E.1) exposes only ``checkpointer`` — later sub-PRs
extend ``__init__`` with the middleware chain (E.2), audit logger (E.5),
LLM router (E.11) and tool registry (E.7+). Callers must pass keyword
arguments so future widening is non-breaking.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


class GraphRunner:
    """Compile orchestrator state graphs against a shared checkpointer.

    Constructed once per service process (or per FastAPI lifespan) with
    a saver produced by
    :func:`helix_agent.runtime.checkpointer.make_checkpointer`. Every
    ``compile`` call attaches the same saver so all graph runs in the
    service share one durable checkpoint store.
    """

    def __init__(self, *, checkpointer: BaseCheckpointSaver[Any]) -> None:
        self._checkpointer = checkpointer

    @property
    def checkpointer(self) -> BaseCheckpointSaver[Any]:
        return self._checkpointer

    def compile(
        self,
        graph: StateGraph[Any, Any, Any, Any],
    ) -> CompiledStateGraph[Any, Any, Any, Any]:
        """Compile ``graph`` with the configured checkpointer.

        Equivalent to ``graph.compile(checkpointer=self.checkpointer)``,
        but routing through ``GraphRunner`` keeps the checkpointer wiring
        in a single place — later sub-PRs (E.2+) inject middleware and
        cancellation plumbing here too, so callers don't need to know
        the evolving set of compile-time hooks.
        """
        compiled: CompiledStateGraph[Any, Any, Any, Any] = graph.compile(
            checkpointer=self._checkpointer,
        )
        logger.debug(
            "orchestrator.graph.compiled checkpointer=%s",
            type(self._checkpointer).__name__,
        )
        return compiled
