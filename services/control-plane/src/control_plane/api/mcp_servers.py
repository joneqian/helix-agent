"""Tenant MCP server registration API — Stream V-C."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def manifest_references_server(spec_json: Mapping[str, Any], server_name: str) -> bool:
    """Return whether an agent manifest references the named MCP server.

    Reads ``spec.tools[].servers`` from the raw manifest dict (the
    ``MCPToolSpec.servers`` field is added in V-E; pre-V-E manifests have no
    ``servers`` key, so this is dormant — and forward-compatible — until then).
    """
    spec = spec_json.get("spec")
    if not isinstance(spec, Mapping):
        return False
    tools = spec.get("tools")
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, Mapping) or tool.get("type") != "mcp":
            continue
        servers = tool.get("servers")
        if isinstance(servers, list) and server_name in servers:
            return True
    return False
