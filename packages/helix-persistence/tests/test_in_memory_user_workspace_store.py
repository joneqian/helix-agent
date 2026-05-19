"""Unit tests for InMemoryUserWorkspaceStore — Stream J.15 contract."""

from __future__ import annotations

from uuid import uuid4

import pytest

from helix_agent.persistence import InMemoryUserWorkspaceStore, workspace_volume_name


@pytest.mark.asyncio
async def test_resolve_creates_then_returns_same_row() -> None:
    store = InMemoryUserWorkspaceStore()
    tenant_id, user_id = uuid4(), uuid4()

    first = await store.resolve(tenant_id=tenant_id, user_id=user_id)
    assert first.tenant_id == tenant_id
    assert first.user_id == user_id
    assert first.created_at is not None

    again = await store.resolve(tenant_id=tenant_id, user_id=user_id)
    # Idempotent: same (tenant, user) resolves to the same workspace.
    assert again.id == first.id
    assert again.created_at == first.created_at
    assert again.volume_name == first.volume_name


@pytest.mark.asyncio
async def test_resolve_volume_name_is_deterministic() -> None:
    store = InMemoryUserWorkspaceStore()
    tenant_id, user_id = uuid4(), uuid4()
    workspace = await store.resolve(tenant_id=tenant_id, user_id=user_id)
    assert workspace.volume_name == workspace_volume_name(tenant_id, user_id)


@pytest.mark.asyncio
async def test_resolve_bumps_last_accessed_at() -> None:
    store = InMemoryUserWorkspaceStore()
    tenant_id, user_id = uuid4(), uuid4()
    first = await store.resolve(tenant_id=tenant_id, user_id=user_id)
    again = await store.resolve(tenant_id=tenant_id, user_id=user_id)
    assert first.last_accessed_at is not None
    assert again.last_accessed_at is not None
    assert again.last_accessed_at >= first.last_accessed_at


@pytest.mark.asyncio
async def test_resolve_distinguishes_tenant_and_user() -> None:
    store = InMemoryUserWorkspaceStore()
    tenant_a, tenant_b = uuid4(), uuid4()
    user_x, user_y = uuid4(), uuid4()

    w1 = await store.resolve(tenant_id=tenant_a, user_id=user_x)
    # Same tenant, different user → different workspace.
    w2 = await store.resolve(tenant_id=tenant_a, user_id=user_y)
    # Different tenant, same user → different workspace.
    w3 = await store.resolve(tenant_id=tenant_b, user_id=user_x)

    assert len({w1.id, w2.id, w3.id}) == 3
    assert len({w1.volume_name, w2.volume_name, w3.volume_name}) == 3
