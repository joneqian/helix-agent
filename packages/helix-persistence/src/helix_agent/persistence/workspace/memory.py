"""In-memory ``UserWorkspaceStore`` for unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from helix_agent.persistence.workspace.base import UserWorkspaceStore, workspace_volume_name
from helix_agent.protocol import UserWorkspace


class InMemoryUserWorkspaceStore(UserWorkspaceStore):
    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, UUID], UserWorkspace] = {}

    async def resolve(self, *, tenant_id: UUID, user_id: UUID) -> UserWorkspace:
        now = datetime.now(UTC)
        key = (tenant_id, user_id)
        existing = self._rows.get(key)
        if existing is not None:
            updated = existing.model_copy(update={"last_accessed_at": now})
            self._rows[key] = updated
            return updated
        workspace = UserWorkspace(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            volume_name=workspace_volume_name(tenant_id, user_id),
            size_bytes=0,
            created_at=now,
            last_accessed_at=now,
        )
        self._rows[key] = workspace
        return workspace
