"""SQLAlchemy-backed ``UserWorkspaceStore`` (Postgres / asyncpg)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from helix_agent.persistence.models import UserWorkspaceRow
from helix_agent.persistence.workspace.base import UserWorkspaceStore, workspace_volume_name
from helix_agent.protocol import UserWorkspace


def _row_to_workspace(row: UserWorkspaceRow) -> UserWorkspace:
    return UserWorkspace(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        volume_name=row.volume_name,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
        last_accessed_at=row.last_accessed_at,
    )


class SqlUserWorkspaceStore(UserWorkspaceStore):
    """Postgres-backed per-user workspace registry."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def resolve(self, *, tenant_id: UUID, user_id: UUID) -> UserWorkspace:
        now = datetime.now(UTC)
        # INSERT ... ON CONFLICT DO UPDATE — a race-free idempotent
        # upsert. ``volume_name`` is deterministic, so a conflicting
        # row already holds the same name; only ``last_accessed_at``
        # is bumped.
        insert_stmt = pg_insert(UserWorkspaceRow).values(
            tenant_id=tenant_id,
            user_id=user_id,
            volume_name=workspace_volume_name(tenant_id, user_id),
            created_at=now,
            last_accessed_at=now,
        )
        upsert = insert_stmt.on_conflict_do_update(
            constraint="user_workspace_identity_uniq",
            set_={"last_accessed_at": now},
        ).returning(UserWorkspaceRow.id)
        async with self._sf() as session:
            result = await session.execute(upsert)
            workspace_id = result.scalar_one()
            await session.commit()
            row = await session.get(UserWorkspaceRow, workspace_id)
            # Just inserted/updated in this transaction — always resolves.
            assert row is not None  # noqa: S101
            return _row_to_workspace(row)
