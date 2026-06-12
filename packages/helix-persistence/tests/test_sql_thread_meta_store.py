"""Integration tests for SqlThreadMetaStore against a real Postgres."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.postgres import PostgresContainer

from helix_agent.persistence import (
    DatabaseConfig,
    SqlThreadMetaStore,
    create_async_engine_from_config,
    create_async_session_factory,
)
from helix_agent.protocol import ThreadStatus

pytestmark = pytest.mark.integration

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

SqlStoreFixture = tuple[SqlThreadMetaStore, AsyncEngine]


def _sync_dsn(container: PostgresContainer) -> str:
    url = str(container.get_connection_url())
    return url.replace("+psycopg2", "+psycopg").replace("postgresql://", "postgresql+psycopg://", 1)


def _async_dsn(container: PostgresContainer) -> str:
    url = str(container.get_connection_url())
    return url.replace("+psycopg2", "+asyncpg").replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.fixture
def sql_store(postgres_container: PostgresContainer) -> Iterator[SqlStoreFixture]:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", _sync_dsn(postgres_container))
    command.upgrade(cfg, "head")

    engine = create_async_engine_from_config(DatabaseConfig(dsn=_async_dsn(postgres_container)))
    session_factory = create_async_session_factory(engine)
    yield SqlThreadMetaStore(session_factory), engine


@pytest.mark.asyncio
async def test_create_and_get_round_trip(sql_store: SqlStoreFixture) -> None:
    store, engine = sql_store
    try:
        thread_id, tenant_id = uuid4(), uuid4()
        meta = await store.create(
            thread_id=thread_id,
            tenant_id=tenant_id,
            created_by="user-1",
            agent_name="demo",
            agent_version="0.1.0",
        )
        assert meta.status == ThreadStatus.ACTIVE

        fetched = await store.get(thread_id, tenant_id=tenant_id)
        assert fetched is not None and fetched.agent_version == "0.1.0"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_filters_by_tenant(sql_store: SqlStoreFixture) -> None:
    store, engine = sql_store
    try:
        thread_id, owner, other = uuid4(), uuid4(), uuid4()
        await store.create(thread_id=thread_id, tenant_id=owner, created_by="u")

        assert await store.get(thread_id, tenant_id=other) is None
        assert await store.get(thread_id, tenant_id=owner) is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_user_id_round_trip_and_list_filter(sql_store: SqlStoreFixture) -> None:
    store, engine = sql_store
    try:
        tenant_id, user_a, user_b = uuid4(), uuid4(), uuid4()
        owned = await store.create(
            thread_id=uuid4(), tenant_id=tenant_id, created_by="x", user_id=user_a
        )
        assert owned.user_id == user_a
        await store.create(thread_id=uuid4(), tenant_id=tenant_id, created_by="x", user_id=user_b)
        unowned = await store.create(thread_id=uuid4(), tenant_id=tenant_id, created_by="x")
        assert unowned.user_id is None

        only_a = await store.list_by_tenant(tenant_id, user_id=user_a)
        assert [m.user_id for m in only_a] == [user_a]
        assert len(await store.list_by_tenant(tenant_id)) == 3
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_thread_id_rejected(sql_store: SqlStoreFixture) -> None:
    store, engine = sql_store
    try:
        thread_id, tenant_id = uuid4(), uuid4()
        await store.create(thread_id=thread_id, tenant_id=tenant_id, created_by="u")
        with pytest.raises(ValueError, match="already exists"):
            await store.create(thread_id=thread_id, tenant_id=tenant_id, created_by="u")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_by_tenant_pagination_and_status(sql_store: SqlStoreFixture) -> None:
    store, engine = sql_store
    try:
        tenant_id = uuid4()
        threads = [uuid4() for _ in range(5)]
        for t in threads:
            await store.create(thread_id=t, tenant_id=tenant_id, created_by="u")
        await store.update_status(threads[0], ThreadStatus.COMPLETED, tenant_id=tenant_id)

        active = await store.list_by_tenant(tenant_id, status=ThreadStatus.ACTIVE)
        assert len(active) == 4

        page = await store.list_by_tenant(tenant_id, limit=2, offset=0)
        assert len(page) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_status_tenant_isolation(sql_store: SqlStoreFixture) -> None:
    store, engine = sql_store
    try:
        thread_id, owner, other = uuid4(), uuid4(), uuid4()
        await store.create(thread_id=thread_id, tenant_id=owner, created_by="u")

        # Bind the awaited result first; `assert await foo()` would be stripped
        # under `python -O` and the side effect (the UPDATE) would silently
        # disappear (CodeQL py/side-effect-in-assert).
        owner_update = await store.update_status(thread_id, ThreadStatus.PAUSED, tenant_id=owner)
        assert owner_update is True
        other_update = await store.update_status(thread_id, ThreadStatus.PAUSED, tenant_id=other)
        assert other_update is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_tenant_isolation(sql_store: SqlStoreFixture) -> None:
    store, engine = sql_store
    try:
        thread_id, owner, other = uuid4(), uuid4(), uuid4()
        await store.create(thread_id=thread_id, tenant_id=owner, created_by="u")

        other_delete = await store.delete(thread_id, tenant_id=other)
        assert other_delete is False
        still_accessible = await store.check_access(thread_id, owner)
        assert still_accessible is True

        owner_delete = await store.delete(thread_id, tenant_id=owner)
        assert owner_delete is True
        gone = await store.check_access(thread_id, owner)
        assert gone is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_by_tenant_agent_filters(sql_store: SqlStoreFixture) -> None:
    """Stream H.6 (Mini-ADR H-10) — agent_name / agent_version WHERE clauses."""
    store, engine = sql_store
    try:
        tenant_id = uuid4()
        await store.create(
            thread_id=uuid4(),
            tenant_id=tenant_id,
            created_by="x",
            agent_name="reporter",
            agent_version="1.0.0",
        )
        await store.create(
            thread_id=uuid4(),
            tenant_id=tenant_id,
            created_by="x",
            agent_name="reporter",
            agent_version="2.0.0",
        )
        await store.create(
            thread_id=uuid4(),
            tenant_id=tenant_id,
            created_by="x",
            agent_name="scribe",
            agent_version="1.0.0",
        )

        by_name = await store.list_by_tenant(tenant_id, agent_name="reporter")
        assert {m.agent_version for m in by_name} == {"1.0.0", "2.0.0"}

        by_name_version = await store.list_by_tenant(
            tenant_id, agent_name="reporter", agent_version="2.0.0"
        )
        assert [m.agent_version for m in by_name_version] == ["2.0.0"]

        assert await store.list_by_tenant(tenant_id, agent_name="ghost") == []
        # No filter → all three (regression).
        assert len(await store.list_by_tenant(tenant_id)) == 3
    finally:
        await engine.dispose()
