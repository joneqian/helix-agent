"""Stream O Mini-ADR O-14 — make_mcp_allowlist_provider reads
``tenant_config.mcp_allowlist`` for the agent builder."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from control_plane.runtime import make_mcp_allowlist_provider
from control_plane.tenancy import TenantConfigNotConfiguredError


class _Svc:
    def __init__(self, allowlist: list[str] | None) -> None:
        self._allowlist = allowlist

    async def get(self, *, tenant_id: object, actor_id: object | None = None) -> object:
        if self._allowlist is None:
            raise TenantConfigNotConfiguredError(tenant_id=tenant_id)  # type: ignore[arg-type]
        return SimpleNamespace(mcp_allowlist=self._allowlist)


@pytest.mark.asyncio
async def test_returns_configured_allowlist() -> None:
    provider = make_mcp_allowlist_provider(_Svc(["gitlab", "linear"]))  # type: ignore[arg-type]
    assert await provider(uuid4()) == ["gitlab", "linear"]


@pytest.mark.asyncio
async def test_unconfigured_tenant_yields_empty() -> None:
    provider = make_mcp_allowlist_provider(_Svc(None))  # type: ignore[arg-type]
    assert await provider(uuid4()) == []
