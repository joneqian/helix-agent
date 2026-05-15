"""MCP (Model Context Protocol) tool adapter — Stream E.9.

Wraps Anthropic's official ``mcp`` Python SDK so per-tenant MCP
servers configured via ``tenant_config.mcp_servers`` (E.8 migration
0011) get exposed to the orchestrator's :class:`ToolRegistry`. Per
Mini-ADR E-5, M0 ships **stdio transport only** — each MCP server is a
local subprocess. HTTP / SSE transports land in M1.

Components:

- :class:`MCPClient` Protocol — minimum surface the rest of the
  orchestrator depends on. ``RecordingMCPClient`` is the in-memory
  fake used by unit tests; ``StdioMCPClient`` is the production
  adapter around the SDK's ``stdio_client`` + ``ClientSession``
  context managers.

- :class:`MCPTool` — one **Helix** :class:`Tool` per MCP-exposed tool,
  namespaced as ``mcp:<server>.<tool>`` so the LLM sees them as
  first-class entries in the spec list.

- :class:`MCPServerPool` — lifecycle owner. Enforces an N=5 server
  cap per § 6 "MCP stdio 子进程泄漏" of
  [STREAM-E-DESIGN](../../../../../docs/streams/STREAM-E-DESIGN.md),
  and runs each server inside an ``AsyncExitStack`` so subprocess
  exits propagate cleanly on shutdown.

- :func:`register_mcp_tools` — helper that runs ``list_tools`` on a
  live :class:`MCPClient` and registers each as an :class:`MCPTool`.

Output truncation per Mini-ADR E-10 / § 1.1 E.9: each ``call_tool``
result is rendered to text (TextContent blocks concatenated) and, if
over 20 000 chars, **middle-trimmed** with the head 50 % + a
``[N chars truncated]`` placeholder + the tail 50 %. Middle trim
(not head or tail) lets the LLM see both the start of the response
(typically status / preamble) and the end (often a conclusion).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from orchestrator.tools.registry import (
    ToolContext,
    ToolNotFoundError,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)

logger = logging.getLogger(__name__)

DEFAULT_MCP_CHAR_CAP = 20_000
DEFAULT_MAX_SERVERS = 5
DEFAULT_TIMEOUT_S = 30.0
_TRUNCATION_PREFIX = "...["
_TRUNCATION_SUFFIX = " chars truncated]..."


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPServerConfig:
    """Per-server launch config from ``tenant_config.mcp_servers``.

    Mirrors the JSONB row shape: ``{"name", "command": [...], "env": {...}}``.
    Validation of the JSONB rows themselves lives in
    :class:`helix_agent.protocol.TenantConfigPatch` — this dataclass
    is just the runtime-typed view orchestrator startup hands to the
    pool.
    """

    name: str
    command: Sequence[str]
    env: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.command:
            msg = f"mcp server {self.name!r} has empty command"
            raise ValueError(msg)


@dataclass(frozen=True)
class MCPToolDef:
    """A single tool advertised by an MCP server's ``list_tools``."""

    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True)
class MCPCallResult:
    """Outcome of an MCP ``call_tool`` round-trip.

    ``content`` is the textified payload — concatenated TextContent
    blocks from the SDK's ``CallToolResult``. Non-text content
    (images, embedded resources) is dropped in M0 and noted by the
    adapter; multimodal lands with M2 / M3.
    """

    content: str
    is_error: bool = False


# ---------------------------------------------------------------------------
# Client protocol + impls
# ---------------------------------------------------------------------------


@runtime_checkable
class MCPClient(Protocol):
    """Minimum surface :class:`MCPTool` + :class:`MCPServerPool` need."""

    async def list_tools(self) -> Sequence[MCPToolDef]:
        """Return the tools the server is advertising."""

    async def call_tool(
        self,
        name: str,
        args: Mapping[str, Any],
    ) -> MCPCallResult:
        """Dispatch a tool call. Implementations may raise on
        transport errors — :class:`MCPTool.call` lets them propagate
        so the ReAct ``tools`` node wraps as :class:`ToolMessage(error)`."""

    async def close(self) -> None:
        """Tear the connection down (subprocess kill in the stdio case)."""


@dataclass
class RecordingMCPClient:
    """In-memory :class:`MCPClient` used by tests + dev fixtures.

    Hand it a list of :class:`MCPToolDef` for ``list_tools`` plus a
    mapping of ``{tool_name → response_string}`` for ``call_tool``;
    omitted names raise :class:`ToolNotFoundError`.
    """

    tools: Sequence[MCPToolDef] = field(default_factory=tuple)
    responses: Mapping[str, str] = field(default_factory=dict)
    raise_on_call: Mapping[str, Exception] = field(default_factory=dict)
    error_tools: frozenset[str] = field(default_factory=frozenset)
    closed: bool = False
    calls: list[tuple[str, Mapping[str, Any]]] = field(default_factory=list)

    async def list_tools(self) -> Sequence[MCPToolDef]:
        return tuple(self.tools)

    async def call_tool(
        self,
        name: str,
        args: Mapping[str, Any],
    ) -> MCPCallResult:
        self.calls.append((name, dict(args)))
        if name in self.raise_on_call:
            raise self.raise_on_call[name]
        if name not in self.responses:
            msg = f"recording client has no scripted response for {name!r}"
            raise ToolNotFoundError(msg)
        return MCPCallResult(
            content=self.responses[name],
            is_error=name in self.error_tools,
        )

    async def close(self) -> None:
        self.closed = True


@dataclass
class StdioMCPClient:
    """Production :class:`MCPClient` — wraps the mcp SDK stdio transport.

    Holds a single subprocess + ``ClientSession`` alive between
    ``start`` and ``close``. The session is managed via
    :class:`contextlib.AsyncExitStack` so subprocess teardown happens
    even if the orchestrator crashes mid-call.

    Not used directly by unit tests — they inject
    :class:`RecordingMCPClient` for determinism. The pool wires this
    one in production with real MCP server commands.
    """

    config: MCPServerConfig
    _stack: contextlib.AsyncExitStack | None = field(default=None, init=False, repr=False)
    _session: Any = field(default=None, init=False, repr=False)

    async def start(self) -> None:
        """Launch the subprocess and complete the MCP handshake."""
        # Imports kept local so the orchestrator can be imported in
        # contexts where the mcp SDK isn't available (e.g. middleware-
        # only unit tests with no MCP wiring).
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        if self._stack is not None:
            msg = f"StdioMCPClient {self.config.name!r} already started"
            raise RuntimeError(msg)

        params = StdioServerParameters(
            command=self.config.command[0],
            args=list(self.config.command[1:]),
            env=dict(self.config.env) or None,
        )
        stack = contextlib.AsyncExitStack()
        await stack.__aenter__()
        try:
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
        except BaseException:
            await stack.__aexit__(None, None, None)
            raise

        self._stack = stack
        self._session = session

    async def list_tools(self) -> Sequence[MCPToolDef]:
        if self._session is None:
            msg = f"StdioMCPClient {self.config.name!r} not started"
            raise RuntimeError(msg)
        result = await self._session.list_tools()
        return tuple(
            MCPToolDef(
                name=str(t.name),
                description=str(getattr(t, "description", "") or ""),
                input_schema=dict(getattr(t, "inputSchema", {}) or {}),
            )
            for t in result.tools
        )

    async def call_tool(
        self,
        name: str,
        args: Mapping[str, Any],
    ) -> MCPCallResult:
        if self._session is None:
            msg = f"StdioMCPClient {self.config.name!r} not started"
            raise RuntimeError(msg)
        result = await self._session.call_tool(name, dict(args))
        return MCPCallResult(
            content=_render_content_blocks(result.content),
            is_error=bool(getattr(result, "isError", False)),
        )

    async def close(self) -> None:
        if self._stack is None:
            return
        await self._stack.__aexit__(None, None, None)
        self._stack = None
        self._session = None


def _render_content_blocks(blocks: Sequence[Any]) -> str:
    """Concatenate :class:`mcp.types.TextContent` blocks. Non-text
    content (images, embedded resources) is dropped in M0 — log it
    so M1/M2 multimodal work has a paper trail."""
    parts: list[str] = []
    skipped = 0
    for block in blocks:
        block_type = getattr(block, "type", None)
        text = getattr(block, "text", None)
        if block_type == "text" and isinstance(text, str):
            parts.append(text)
        else:
            skipped += 1
    if skipped:
        logger.info("mcp.dropped_non_text_blocks count=%d", skipped)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Helix Tool wrapper
# ---------------------------------------------------------------------------


@dataclass
class MCPTool:
    """Helix :class:`Tool` wrapping one MCP-exposed tool.

    The Helix-side name is namespaced ``mcp:<server>.<tool>`` so the
    LLM (and the audit log) can tell which MCP server a call routed
    to. ``call`` ignores ``ctx`` in M0 — per-tenant MCP server
    selection happens at registration time (the orchestrator binds a
    pool per tenant); the tool itself only sees one server.
    """

    client: MCPClient
    tool_def: MCPToolDef
    server_name: str
    content_char_cap: int = DEFAULT_MCP_CHAR_CAP
    spec: ToolSpec = field(init=False)

    def __post_init__(self) -> None:
        # ``spec`` is derived from the other fields; we materialise it
        # here (rather than via @property) so the Tool Protocol's
        # ``spec: ToolSpec`` attribute contract is satisfied.
        object.__setattr__(
            self,
            "spec",
            ToolSpec(
                name=f"mcp:{self.server_name}.{self.tool_def.name}",
                description=self.tool_def.description,
                parameters=self.tool_def.input_schema,
            ),
        )

    async def call(self, args: Mapping[str, Any], *, ctx: ToolContext) -> ToolResult:
        del ctx
        result = await self.client.call_tool(self.tool_def.name, args)
        content, truncated = _middle_trim(result.content, self.content_char_cap)
        return ToolResult(
            content=content,
            meta={
                "server": self.server_name,
                "truncated": truncated,
                "is_error": result.is_error,
            },
        )


def _middle_trim(text: str, cap: int) -> tuple[str, bool]:
    """Middle-truncate to ``cap`` chars, keeping head + tail 50%.

    Returns ``(text, was_truncated)``. Letting the LLM see both ends
    of an over-cap response is the deer-flow ``_truncate_bash_output``
    pattern; with file contents in particular the head shows the
    metadata / shebang and the tail shows whatever the model was
    looking for (results, errors, EOF marker).
    """
    if len(text) <= cap:
        return text, False
    half = cap // 2
    dropped = len(text) - cap
    head = text[:half]
    tail = text[-half:]
    return (
        f"{head}\n{_TRUNCATION_PREFIX}{dropped}{_TRUNCATION_SUFFIX}\n{tail}",
        True,
    )


# ---------------------------------------------------------------------------
# Pool / lifecycle
# ---------------------------------------------------------------------------


class MCPServerPoolLimitError(RuntimeError):
    """Raised when adding a server would exceed ``max_servers``."""


@dataclass
class MCPServerPool:
    """Owns the live :class:`MCPClient` instances per tenant.

    M0 keeps things simple: one process-global pool. M1 promotes this
    to a per-tenant dict keyed by ``tenant_id`` (necessary once
    Sub-Agent + tenant isolation deepen). Enforces ``max_servers=5``
    per [STREAM-E-DESIGN § 6 risk table](../../../../../docs/streams/STREAM-E-DESIGN.md):
    each subprocess takes file descriptors + a Python interpreter
    (for npm-based servers), so the cap stops a runaway manifest from
    starving the host.
    """

    max_servers: int = DEFAULT_MAX_SERVERS
    _clients: dict[str, MCPClient] = field(default_factory=dict, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def add(self, name: str, client: MCPClient) -> None:
        async with self._lock:
            if name in self._clients:
                msg = f"mcp server {name!r} already registered"
                raise ValueError(msg)
            if len(self._clients) >= self.max_servers:
                msg = f"mcp pool already has {self.max_servers} servers; cannot add {name!r}"
                raise MCPServerPoolLimitError(msg)
            self._clients[name] = client

    def get(self, name: str) -> MCPClient | None:
        return self._clients.get(name)

    def names(self) -> list[str]:
        return list(self._clients.keys())

    async def close_all(self) -> None:
        async with self._lock:
            errors: list[Exception] = []
            for name, client in list(self._clients.items()):
                try:
                    await client.close()
                except Exception as exc:
                    logger.warning("mcp.close_failed server=%s err=%s", name, exc)
                    errors.append(exc)
            self._clients.clear()
            if errors:
                raise ExceptionGroup("mcp.close_errors", errors)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


async def register_mcp_tools(
    *,
    server_name: str,
    client: MCPClient,
    registry: ToolRegistry,
    content_char_cap: int = DEFAULT_MCP_CHAR_CAP,
) -> list[str]:
    """List tools from ``client`` and register each as :class:`MCPTool`.

    Returns the namespaced names registered, useful for audit
    attribution at orchestrator startup.
    """
    tools = await client.list_tools()
    registered: list[str] = []
    for tool_def in tools:
        helix_tool = MCPTool(
            client=client,
            tool_def=tool_def,
            server_name=server_name,
            content_char_cap=content_char_cap,
        )
        registry.register(helix_tool)
        registered.append(helix_tool.spec.name)
    logger.info("mcp.registered server=%s tools=%s", server_name, registered)
    return registered
