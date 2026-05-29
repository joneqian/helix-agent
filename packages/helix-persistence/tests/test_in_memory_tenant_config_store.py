"""Unit tests for :class:`InMemoryTenantConfigStore.create` — Stream P (P-1/P-3)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from helix_agent.persistence.tenant_config.base import TenantConfigAlreadyExistsError
from helix_agent.persistence.tenant_config.memory import InMemoryTenantConfigStore
from helix_agent.protocol import TenantPlan


@pytest.mark.asyncio
async def test_create_writes_first_row_with_defaults() -> None:
    store = InMemoryTenantConfigStore()
    tenant_id = uuid4()

    record = await store.create(
        tenant_id=tenant_id,
        display_name="Acme Inc",
        actor_id="bootstrap",
    )

    assert record.tenant_id == tenant_id
    assert record.display_name == "Acme Inc"
    assert record.plan is TenantPlan.FREE  # default
    assert record.updated_by == "bootstrap"
    # Every other field falls back to its baseline default.
    assert record.model_credentials_ref == {}
    assert record.credentials_mode == "platform"
    # And the row is now readable via get().
    assert (await store.get(tenant_id=tenant_id)) == record


@pytest.mark.asyncio
async def test_create_honours_explicit_plan() -> None:
    store = InMemoryTenantConfigStore()
    tenant_id = uuid4()

    record = await store.create(
        tenant_id=tenant_id,
        display_name="Pro Co",
        plan=TenantPlan.PRO,
        actor_id="admin",
    )

    assert record.plan is TenantPlan.PRO


@pytest.mark.asyncio
async def test_create_rejects_existing_tenant() -> None:
    store = InMemoryTenantConfigStore()
    tenant_id = uuid4()
    await store.create(tenant_id=tenant_id, display_name="First", actor_id="a")

    with pytest.raises(TenantConfigAlreadyExistsError) as exc:
        await store.create(tenant_id=tenant_id, display_name="Second", actor_id="b")
    assert exc.value.tenant_id == tenant_id
    # The original row is untouched (no silent overwrite, unlike upsert).
    assert (await store.get(tenant_id=tenant_id)).display_name == "First"
