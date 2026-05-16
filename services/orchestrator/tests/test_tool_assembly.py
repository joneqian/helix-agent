"""Unit tests for :func:`build_tool_registry` — manifest ``tools:`` → registry."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import pytest

from helix_agent.protocol import BuiltinToolSpec, HTTPToolSpec, MCPToolSpec
from orchestrator import AgentFactoryError
from orchestrator.tools import (
    HTTPTool,
    MCPServerPool,
    MCPToolDef,
    RecordingMCPClient,
    RecordingTavilyClient,
    ToolEnv,
    WebSearchTool,
    build_tool_registry,
)


async def _allowlist(_tenant: UUID | None) -> Sequence[str]:
    return ["https://api.github.com/*"]


async def _seeded_pool() -> MCPServerPool:
    pool = MCPServerPool()
    client = RecordingMCPClient(
        tools=(
            MCPToolDef(name="read_pr", description="read a PR", input_schema={}),
            MCPToolDef(name="post_comment", description="comment", input_schema={}),
        )
    )
    await pool.add("gitlab", client)
    return pool


@pytest.mark.asyncio
async def test_empty_tools_builds_empty_registry() -> None:
    registry = await build_tool_registry([], tool_env=ToolEnv())
    assert len(registry) == 0


@pytest.mark.asyncio
async def test_builtin_web_search_assembled() -> None:
    env = ToolEnv(web_search_client=RecordingTavilyClient())
    registry = await build_tool_registry(
        [BuiltinToolSpec(name="web_search", config={"max_results": 7})],
        tool_env=env,
    )
    tool = registry.get("web_search")
    assert isinstance(tool, WebSearchTool)
    assert tool.default_max_results == 7


@pytest.mark.asyncio
async def test_builtin_unknown_name_raises() -> None:
    with pytest.raises(AgentFactoryError, match="unknown builtin"):
        await build_tool_registry(
            [BuiltinToolSpec(name="nonsense")],
            tool_env=ToolEnv(web_search_client=RecordingTavilyClient()),
        )


@pytest.mark.asyncio
async def test_builtin_web_search_missing_client_raises() -> None:
    with pytest.raises(AgentFactoryError, match="Tavily client"):
        await build_tool_registry([BuiltinToolSpec(name="web_search")], tool_env=ToolEnv())


@pytest.mark.asyncio
async def test_http_tool_assembled() -> None:
    registry = await build_tool_registry(
        [HTTPToolSpec()], tool_env=ToolEnv(allowlist_provider=_allowlist)
    )
    assert isinstance(registry.get("http"), HTTPTool)


@pytest.mark.asyncio
async def test_http_tool_missing_allowlist_raises() -> None:
    with pytest.raises(AgentFactoryError, match="allowlist provider"):
        await build_tool_registry([HTTPToolSpec()], tool_env=ToolEnv())


@pytest.mark.asyncio
async def test_mcp_tools_assembled_from_pool() -> None:
    pool = await _seeded_pool()
    registry = await build_tool_registry([MCPToolSpec()], tool_env=ToolEnv(mcp_pool=pool))
    # Both server-advertised tools register, namespaced ``mcp:<server>.<tool>``.
    assert len(registry) == 2


@pytest.mark.asyncio
async def test_mcp_allow_tools_filters() -> None:
    pool = await _seeded_pool()
    registry = await build_tool_registry(
        [MCPToolSpec(allow_tools=["read_pr"])], tool_env=ToolEnv(mcp_pool=pool)
    )
    assert len(registry) == 1


@pytest.mark.asyncio
async def test_mcp_missing_pool_raises() -> None:
    with pytest.raises(AgentFactoryError, match="MCP server pool"):
        await build_tool_registry([MCPToolSpec()], tool_env=ToolEnv())


@pytest.mark.asyncio
async def test_multiple_tools_all_registered() -> None:
    env = ToolEnv(
        web_search_client=RecordingTavilyClient(),
        allowlist_provider=_allowlist,
    )
    registry = await build_tool_registry(
        [BuiltinToolSpec(name="web_search"), HTTPToolSpec()], tool_env=env
    )
    assert registry.get("web_search") is not None
    assert registry.get("http") is not None
