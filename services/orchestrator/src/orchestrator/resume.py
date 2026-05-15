"""Resume sanitisation — orphan tool-call repair (Stream E.15).

When cancellation interrupts the narrow window between an ``AIMessage``
emitting ``tool_calls`` and the tools node dispatching them, the
checkpoint is left with an ``AIMessage`` whose tool calls have **no**
matching ``ToolMessage``. Resuming such a thread feeds the LLM an
invalid message list — most providers reject an assistant turn with
``tool_calls`` that has no tool results — and the run cannot continue.

:func:`sanitize_dangling_tool_calls` computes one placeholder
``ToolMessage`` per unanswered tool call so the list becomes valid
again. Per [STREAM-E-DESIGN § 1.1 E.15](../../../../../docs/streams/STREAM-E-DESIGN.md)
the repair is a plain function + a thin :class:`GraphRunner` method —
**not** a middleware (the scenario is rare enough under M0's single
agent + ``max_steps`` cap that a dedicated chain entry is overkill).
Modelled after deer-flow's ``dangling_tool_call_middleware.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

#: Body of an injected placeholder. ``status="error"`` so the LLM reads
#: it as "this tool did not run" and reasons about a retry / different
#: approach rather than treating empty output as a real result.
PLACEHOLDER_CONTENT = "[cancelled before dispatch]"


def sanitize_dangling_tool_calls(
    messages: Sequence[BaseMessage],
) -> list[ToolMessage]:
    """Return placeholder ``ToolMessage``s for every unanswered tool call.

    A tool call is "answered" when some :class:`ToolMessage` in
    ``messages`` carries a matching ``tool_call_id``. Every tool call
    id that appears on an :class:`AIMessage` but is never answered gets
    one placeholder, in first-seen order. Duplicate ids yield a single
    placeholder. An already-valid history yields an empty list.
    """
    answered: set[str] = {
        m.tool_call_id for m in messages if isinstance(m, ToolMessage) and m.tool_call_id
    }
    placeholders: list[ToolMessage] = []
    emitted: set[str] = set()
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for tool_call in getattr(message, "tool_calls", None) or []:
            tc_id = str(tool_call.get("id") or "")
            if not tc_id or tc_id in answered or tc_id in emitted:
                continue
            emitted.add(tc_id)
            placeholders.append(
                ToolMessage(
                    content=PLACEHOLDER_CONTENT,
                    tool_call_id=tc_id,
                    status="error",
                )
            )
    return placeholders
