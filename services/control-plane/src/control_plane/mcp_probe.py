"""Connect-probe for tenant-registered remote MCP servers — Stream V-C.

Before a remote MCP server is persisted (or its url/token changed), the
control plane connects to it and calls ``list_tools`` to prove it is real and
reachable. The probe runs the orchestrator's remote MCP client in-process
(control-plane already depends on the orchestrator). The URL is SSRF-checked
at this boundary too — never trust that the caller validated it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping, Sequence

from helix_agent.common.url_validation import RemoteURLError, validate_remote_url
from orchestrator.tools.mcp import (
    MCPServerConfig,
    MCPToolDef,
    SseMCPClient,
    StreamableHttpMCPClient,
)

logger = logging.getLogger("helix.control_plane.mcp_probe")

# A factory so tests can inject a fake client. Production builds the real
# transport client from config + already-resolved headers.
ProbeClientFactory = Callable[[MCPServerConfig, Mapping[str, str]], object]


class McpProbeError(Exception):
    """Probe failed. ``code`` is the machine-readable API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _default_client_factory(config: MCPServerConfig, headers: Mapping[str, str]) -> object:
    if config.transport == "sse":
        return SseMCPClient(config=config, resolved_headers=dict(headers))
    return StreamableHttpMCPClient(config=config, resolved_headers=dict(headers))


async def probe_remote_mcp(
    *,
    name: str,
    transport: str,
    url: str,
    bearer_token: str | None,
    timeout_s: float,
    client_factory: ProbeClientFactory = _default_client_factory,
) -> Sequence[MCPToolDef]:
    """Connect to a remote MCP server and return its advertised tools.

    Raises :class:`McpProbeError` (with ``code`` in
    ``{MCP_SERVER_INVALID_URL, MCP_SERVER_PROBE_FAILED}``) on SSRF rejection,
    connect failure, timeout, or list_tools error. Never logs the token.
    """
    try:
        validate_remote_url(url)
    except RemoteURLError as exc:
        raise McpProbeError("MCP_SERVER_INVALID_URL", str(exc)) from exc

    headers: dict[str, str] = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    # MCPServerConfig.__post_init__ requires auth_config["token_ref"] when
    # auth_type="bearer". We supply the sentinel "secret://probe" — the actual
    # token is injected via resolved_headers above; the config field never
    # carries the real secret (it is repr=False regardless). If bearer_token is
    # None we use auth_type="none" so no sentinel is needed.
    config = MCPServerConfig(
        name=name,
        transport=transport,  # type: ignore[arg-type]
        url=url,
        auth_type="bearer" if bearer_token else "none",
        auth_config={"token_ref": "secret://probe"} if bearer_token else {},
        timeout_s=timeout_s,
    )
    client = client_factory(config, headers)
    try:
        await asyncio.wait_for(client.start(), timeout=timeout_s)  # type: ignore[attr-defined]
        tools: Sequence[MCPToolDef] = await asyncio.wait_for(client.list_tools(), timeout=timeout_s)  # type: ignore[attr-defined]
        return tools
    except McpProbeError:
        raise
    except Exception as exc:  # probe maps all failures (incl. TimeoutError) to McpProbeError
        logger.info("mcp_probe.failed server=%s transport=%s", name, transport)
        raise McpProbeError(
            "MCP_SERVER_PROBE_FAILED",
            f"could not connect to MCP server {name!r}: {type(exc).__name__}",
        ) from exc
    finally:
        try:
            await client.close()  # type: ignore[attr-defined]
        except Exception:  # best-effort teardown; close errors must not mask probe errors
            logger.info("mcp_probe.close_failed server=%s", name)
