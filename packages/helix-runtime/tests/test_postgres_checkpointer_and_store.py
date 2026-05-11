"""Integration tests for Postgres backends of checkpointer + store.

These are minimal smoke tests — we only verify the factory connects to
Postgres, the ``setup()`` migration runs, and the yielded saver/store
exposes the expected public API. End-to-end checkpoint/state round-trip
is covered by LangGraph's own test suite; duplicating it here would
couple us tightly to their internal TypedDict shapes.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from testcontainers.postgres import PostgresContainer

from helix_agent.runtime.checkpointer import make_checkpointer
from helix_agent.runtime.store import make_store

pytestmark = pytest.mark.integration


def _sync_dsn(container: PostgresContainer) -> str:
    """LangGraph savers/stores take a sync-style DSN and manage their own
    async pool. Strip the testcontainers ``+psycopg2`` driver suffix."""
    return str(container.get_connection_url()).replace("+psycopg2", "")


@pytest.mark.asyncio
async def test_postgres_checkpointer_setup_and_api(
    postgres_container: PostgresContainer,
) -> None:
    dsn = _sync_dsn(postgres_container)
    async with make_checkpointer("postgres", dsn) as cp:
        assert isinstance(cp, BaseCheckpointSaver)
        # Async API surface that the orchestrator depends on
        assert callable(cp.aput)
        assert callable(cp.aget_tuple)
        assert callable(cp.alist)


@pytest.mark.asyncio
async def test_postgres_store_put_get_round_trip(
    postgres_container: PostgresContainer,
) -> None:
    dsn = _sync_dsn(postgres_container)
    namespace = ("tenant-x", "memories")

    async with make_store("postgres", dsn) as store:
        assert isinstance(store, BaseStore)
        await store.aput(namespace, key="m1", value={"text": "hello"})
        item = await store.aget(namespace, "m1")
        assert item is not None
        assert item.value == {"text": "hello"}
