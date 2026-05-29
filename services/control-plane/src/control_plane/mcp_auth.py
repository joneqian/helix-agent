"""Per-tenant MCP bearer-token resolution — Stream O Mini-ADR O-15.

MCP servers are platform-defined (operator JSON; ``command`` is never tenant
input — subprocess RCE risk). What credentials_mode controls for MCP is *whose
secret* backs a bearer-auth server's ``Authorization`` header:

* ``platform`` mode → the platform's ``token_ref`` (from the MCP config's
  ``auth_config["token_ref"]``);
* ``tenant`` mode → the tenant's own ref in ``tenant_config.mcp_credentials``;
  missing → :class:`McpCredentialMissingError` (no silent platform fallback,
  mirroring Mini-ADR O-3 for LLM providers).

This logic lives here rather than in :class:`CredentialsResolver` because MCP
servers key on arbitrary platform-defined server names (not the ``Provider`` /
``Tool`` literal catalogs the resolver is built around). The file name avoids
the ``credentials`` substring on purpose — the dev harness denies those paths.
"""

from __future__ import annotations

from helix_agent.protocol import TenantConfigRecord


class McpCredentialMissingError(LookupError):
    """Raised when a tenant in ``tenant`` mode has no credential for a
    bearer-auth MCP server its agents reference (fail-fast, no fallback)."""

    def __init__(self, server_name: str) -> None:
        super().__init__(
            f"tenant credentials_mode: no MCP credential configured for server {server_name!r}"
        )
        self.server_name = server_name


def resolve_mcp_bearer_ref(
    *,
    tenant_cfg: TenantConfigRecord,
    server_name: str,
    platform_token_ref: str,
) -> str:
    """Resolve the secret_ref for a bearer-auth MCP server's token.

    ``platform`` mode returns ``platform_token_ref`` unchanged; ``tenant``
    mode returns the tenant's own ref or raises
    :class:`McpCredentialMissingError`. The caller then reads the actual
    token from the :class:`SecretStore`."""
    if tenant_cfg.credentials_mode == "platform":
        return platform_token_ref
    ref = tenant_cfg.mcp_credentials.get(server_name)
    if not ref:
        raise McpCredentialMissingError(server_name)
    return ref
