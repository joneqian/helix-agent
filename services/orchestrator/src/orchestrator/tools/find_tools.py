"""``find_tools`` — the tool-RAG meta-tool (Stream TE-6).

Treats Context Bloat: tools registered as *deferred* (see
:meth:`ToolRegistry.register`) are kept out of every turn's LLM ``tools``
list. The model discovers and loads them on demand by calling
``find_tools(query)``; the matches are written to the run's
``promoted_tools`` channel (via :attr:`ToolResult.state_updates`) so the
next ``agent_node`` adds their specs to the bind, after which they are
directly callable.

Promotion lives on the LangGraph ``AgentState`` channel — per-thread and
checkpointed — so it never mutates the agent-lifetime-cached registry
(per-run isolation). This module is the dormant mechanism only: no tool is
deferred by default, so with the stock registry ``find_tools`` simply finds
nothing. Auto-deferral of large tool surfaces (e.g. MCP over a threshold)
is Stream TE-6b.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from orchestrator.tools.registry import ToolContext, ToolRegistry, ToolResult, ToolSpec


@dataclass
class FindToolsTool:
    """Retrieves currently-unloaded (deferred) tools by query — ``find_tools``.

    Stream TE-6 — holds a reference to the same :class:`ToolRegistry` the
    graph dispatches from. :meth:`call` searches the deferred set and writes
    the matched names to ``promoted_tools`` so the next turn binds them.
    """

    registry: ToolRegistry

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="find_tools",
            description=(
                "Search for and load tools that are not currently available to "
                "you, then they become directly callable on your next step. Use "
                "this when you need a capability you don't see in your tool list "
                "(e.g. a specific integration). The 'query' supports three forms: "
                "'select:name1,name2' loads tools by exact name; '+keyword extra "
                "words' requires 'keyword' and filters by the remaining words; "
                "any other text is matched as a substring or regular expression "
                "against tool names and descriptions. The result lists the loaded "
                "tools; call them directly afterwards — do not call find_tools "
                "again for the same tool."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What you're looking for: 'select:a,b', '+keyword ...', "
                            "or a substring/regex over tool names and descriptions."
                        ),
                    },
                },
                "required": ["query"],
            },
            # Conservative: promotes state + we keep it on the serial path so
            # the promoted_tools write is applied before any dependent call.
            is_read_only=False,
        )

    async def call(self, args: Mapping[str, Any], *, ctx: ToolContext) -> ToolResult:
        del ctx  # find_tools needs no tenant/run binding — it reads the registry.
        raw = args.get("query")
        if not isinstance(raw, str) or not raw.strip():
            msg = "find_tools requires a non-empty 'query' string"
            raise ValueError(msg)

        matches = self.registry.search(raw)
        names = [spec.name for spec in matches]
        if not matches:
            content = "(no matching tools found)"
        else:
            listing = "\n".join(f"- {spec.name}: {spec.description}" for spec in matches)
            content = f"Loaded the following tools — you can call them directly now:\n{listing}"
        return ToolResult(content=content, state_updates={"promoted_tools": names})
