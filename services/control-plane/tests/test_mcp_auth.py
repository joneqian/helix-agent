"""Stream O Mini-ADR O-15 — per-tenant MCP bearer-token resolution contract."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from control_plane.mcp_auth import McpCredentialMissingError, resolve_mcp_bearer_ref
from helix_agent.protocol import TenantConfigRecord, TenantPlan

_NOW = datetime.now(UTC)


def _cfg(*, mode: str, mcp_creds: dict[str, str] | None = None) -> TenantConfigRecord:
    return TenantConfigRecord(
        tenant_id=uuid4(),
        display_name="Acme",
        plan=TenantPlan.FREE,
        credentials_mode=mode,  # type: ignore[arg-type]
        mcp_credentials=mcp_creds or {},
        created_at=_NOW,
        updated_at=_NOW,
        updated_by="tester",
    )


def test_platform_mode_returns_platform_ref() -> None:
    ref = resolve_mcp_bearer_ref(
        tenant_cfg=_cfg(mode="platform", mcp_creds={"github": "kms://acme/gh"}),
        server_name="github",
        platform_token_ref="secret://plat/github",
    )
    # Platform mode ignores the tenant ref entirely.
    assert ref == "secret://plat/github"


def test_tenant_mode_returns_tenant_ref() -> None:
    ref = resolve_mcp_bearer_ref(
        tenant_cfg=_cfg(mode="tenant", mcp_creds={"github": "kms://acme/gh"}),
        server_name="github",
        platform_token_ref="secret://plat/github",
    )
    assert ref == "kms://acme/gh"


def test_tenant_mode_missing_ref_raises() -> None:
    with pytest.raises(McpCredentialMissingError) as exc:
        resolve_mcp_bearer_ref(
            tenant_cfg=_cfg(mode="tenant", mcp_creds={}),
            server_name="github",
            platform_token_ref="secret://plat/github",
        )
    assert exc.value.server_name == "github"


def test_tenant_mode_empty_string_ref_raises() -> None:
    with pytest.raises(McpCredentialMissingError):
        resolve_mcp_bearer_ref(
            tenant_cfg=_cfg(mode="tenant", mcp_creds={"github": ""}),
            server_name="github",
            platform_token_ref="secret://plat/github",
        )
