"""Unit tests for :class:`FindToolsTool` — Stream TE-6 (tool RAG meta-tool)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest

from orchestrator import (
    FindToolsTool,
    ToolContext,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)


@dataclass
class _DummyTool:
    spec: ToolSpec

    async def call(self, args: Mapping[str, Any], *, ctx: ToolContext) -> ToolResult:
        del ctx
        return ToolResult(content=f"called with {dict(args)}")


def _deferred(name: str, description: str) -> _DummyTool:
    return _DummyTool(spec=ToolSpec(name=name, description=description))


def _registry_with_deferred() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_deferred("active", "an active tool"))
    registry.register(_deferred("github_issue", "create a github issue"), deferred=True)
    registry.register(_deferred("github_pr", "open a github pull request"), deferred=True)
    return registry


def test_spec_has_query_parameter() -> None:
    tool = FindToolsTool(registry=ToolRegistry())
    spec = tool.spec
    assert spec.name == "find_tools"
    assert spec.parameters["required"] == ["query"]
    assert "query" in spec.parameters["properties"]
    assert spec.is_read_only is False


@pytest.mark.asyncio
async def test_call_returns_matches_and_promotes() -> None:
    tool = FindToolsTool(registry=_registry_with_deferred())
    result = await tool.call({"query": "github"}, ctx=ToolContext())
    assert "github_issue" in result.content
    assert "github_pr" in result.content
    assert result.state_updates["promoted_tools"] == ["github_issue", "github_pr"]


@pytest.mark.asyncio
async def test_call_empty_query_raises() -> None:
    tool = FindToolsTool(registry=_registry_with_deferred())
    with pytest.raises(ValueError, match="non-empty"):
        await tool.call({"query": "   "}, ctx=ToolContext())
    with pytest.raises(ValueError, match="non-empty"):
        await tool.call({}, ctx=ToolContext())


@pytest.mark.asyncio
async def test_call_no_match_returns_placeholder_and_empty_promotion() -> None:
    tool = FindToolsTool(registry=_registry_with_deferred())
    result = await tool.call({"query": "nonexistent-tool"}, ctx=ToolContext())
    assert result.content == "(no matching tools found)"
    assert result.state_updates["promoted_tools"] == []


@pytest.mark.asyncio
async def test_call_select_syntax() -> None:
    tool = FindToolsTool(registry=_registry_with_deferred())
    result = await tool.call({"query": "select:github_pr"}, ctx=ToolContext())
    assert result.state_updates["promoted_tools"] == ["github_pr"]
