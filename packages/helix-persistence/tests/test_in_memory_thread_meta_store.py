"""Unit tests for InMemoryThreadMetaStore — Repository contract."""

from __future__ import annotations

from uuid import uuid4

import pytest

from helix_agent.persistence import InMemoryThreadMetaStore
from helix_agent.protocol import ThreadStatus


@pytest.mark.asyncio
async def test_create_and_get_round_trip() -> None:
    store = InMemoryThreadMetaStore()
    thread_id, tenant_id = uuid4(), uuid4()

    created = await store.create(
        thread_id=thread_id,
        tenant_id=tenant_id,
        created_by="user-1",
        agent_name="demo",
        agent_version="0.1.0",
    )
    assert created.thread_id == thread_id
    assert created.status == ThreadStatus.ACTIVE
    assert created.agent_version == "0.1.0"

    fetched = await store.get(thread_id, tenant_id=tenant_id)
    assert fetched is not None
    assert fetched.created_by == "user-1"


@pytest.mark.asyncio
async def test_get_filters_by_tenant() -> None:
    store = InMemoryThreadMetaStore()
    thread_id, owner, other = uuid4(), uuid4(), uuid4()
    await store.create(thread_id=thread_id, tenant_id=owner, created_by="x")

    assert await store.get(thread_id, tenant_id=other) is None
    assert await store.get(thread_id, tenant_id=owner) is not None


@pytest.mark.asyncio
async def test_create_rejects_duplicate_thread_id() -> None:
    store = InMemoryThreadMetaStore()
    thread_id, tenant_id = uuid4(), uuid4()
    await store.create(thread_id=thread_id, tenant_id=tenant_id, created_by="x")
    with pytest.raises(ValueError, match="already exists"):
        await store.create(thread_id=thread_id, tenant_id=tenant_id, created_by="x")


@pytest.mark.asyncio
async def test_list_by_tenant_pagination_and_status_filter() -> None:
    store = InMemoryThreadMetaStore()
    tenant_id = uuid4()
    threads = [uuid4() for _ in range(5)]
    for t in threads:
        await store.create(thread_id=t, tenant_id=tenant_id, created_by="x")

    await store.update_status(threads[0], ThreadStatus.COMPLETED, tenant_id=tenant_id)

    all_active = await store.list_by_tenant(tenant_id, status=ThreadStatus.ACTIVE)
    assert len(all_active) == 4

    page = await store.list_by_tenant(tenant_id, limit=2, offset=0)
    assert len(page) == 2


@pytest.mark.asyncio
async def test_update_status_returns_true_only_on_match() -> None:
    store = InMemoryThreadMetaStore()
    thread_id, owner, other = uuid4(), uuid4(), uuid4()
    await store.create(thread_id=thread_id, tenant_id=owner, created_by="x")

    # Bind awaited mutations before asserting; `assert await foo()` is stripped
    # under `python -O` and the side effect would disappear silently.
    owner_match = await store.update_status(thread_id, ThreadStatus.PAUSED, tenant_id=owner)
    assert owner_match is True
    other_mismatch = await store.update_status(thread_id, ThreadStatus.PAUSED, tenant_id=other)
    assert other_mismatch is False
    missing = await store.update_status(uuid4(), ThreadStatus.PAUSED, tenant_id=owner)
    assert missing is False


@pytest.mark.asyncio
async def test_check_access_and_delete() -> None:
    store = InMemoryThreadMetaStore()
    thread_id, owner, other = uuid4(), uuid4(), uuid4()
    await store.create(thread_id=thread_id, tenant_id=owner, created_by="x")

    owner_access = await store.check_access(thread_id, owner)
    assert owner_access is True
    other_access = await store.check_access(thread_id, other)
    assert other_access is False

    wrong_tenant_delete = await store.delete(thread_id, tenant_id=other)
    assert wrong_tenant_delete is False
    still_accessible = await store.check_access(thread_id, owner)
    assert still_accessible is True

    owner_delete = await store.delete(thread_id, tenant_id=owner)
    assert owner_delete is True
    gone = await store.check_access(thread_id, owner)
    assert gone is False
