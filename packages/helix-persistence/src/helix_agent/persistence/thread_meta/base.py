# ============================================================
# Adapted from bytedance/deer-flow @ 813d3c94efa7fdea6aafcb4f459304db91fcaed0
# Source: backend/packages/harness/deerflow/persistence/thread_meta/base.py
# License: MIT (see vendor LICENSE)
# Modifications:
#   - tenant_id (UUID) is a required first-class parameter; DeerFlow's
#     three-state user_id AUTO sentinel collapsed to "tenant_id required"
#     (Stream C wires the contextvar at call sites instead)
#   - Returns Pydantic ThreadMeta (helix-agent-protocol) instead of dict
#   - Dropped DeerFlow-specific fields: assistant_id / display_name /
#     metadata_json (we may add them later if a use case appears)
#   - check_access semantics simplified: 1 mode (existing-or-bypass) instead
#     of DeerFlow's permissive / strict pair
# Last sync: 2026-05-11
# ============================================================

"""Abstract ``ThreadMetaStore`` repository — ADR-0002 schema.

Implementations:
- :class:`helix_agent.persistence.thread_meta.memory.InMemoryThreadMetaStore`
- :class:`helix_agent.persistence.thread_meta.sql.SqlThreadMetaStore`
"""

from __future__ import annotations

import abc
from uuid import UUID

from helix_agent.protocol import ThreadMeta, ThreadStatus


class ThreadMetaStore(abc.ABC):
    """Per-thread metadata repository.

    Every mutating / read method takes ``tenant_id`` explicitly. There is
    no AUTO sentinel — Stream C wires tenant context at the call site
    (Control Plane handlers, Orchestrator worker pickup, etc.).
    """

    @abc.abstractmethod
    async def create(
        self,
        *,
        thread_id: UUID,
        tenant_id: UUID,
        created_by: str,
        agent_name: str | None = None,
        agent_version: str | None = None,
    ) -> ThreadMeta:
        """Insert a new thread; ``thread_id`` must be unique."""

    @abc.abstractmethod
    async def get(self, thread_id: UUID, *, tenant_id: UUID) -> ThreadMeta | None:
        """Read a thread, filtered to ``tenant_id``.

        Returns ``None`` when the row does not exist or belongs to a
        different tenant — never reveals cross-tenant existence.
        """

    @abc.abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        status: ThreadStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ThreadMeta]:
        """Paginated list of threads for ``tenant_id``, newest first."""

    @abc.abstractmethod
    async def update_status(
        self,
        thread_id: UUID,
        status: ThreadStatus,
        *,
        tenant_id: UUID,
    ) -> bool:
        """Update status; returns True if a row matched the tenant filter."""

    @abc.abstractmethod
    async def check_access(self, thread_id: UUID, tenant_id: UUID) -> bool:
        """``True`` iff the thread exists and belongs to ``tenant_id``."""

    @abc.abstractmethod
    async def delete(self, thread_id: UUID, *, tenant_id: UUID) -> bool:
        """Delete the thread; returns True if a row matched the tenant filter.

        Test / admin only. Production retention is driven by Stream D.3 TTL job.
        """
