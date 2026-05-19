"""Abstract ``UserWorkspaceStore`` repository — Stream J.15.

Implementations:
- :class:`helix_agent.persistence.workspace.memory.InMemoryUserWorkspaceStore`
- :class:`helix_agent.persistence.workspace.sql.SqlUserWorkspaceStore`
"""

from __future__ import annotations

import abc
from uuid import UUID

from helix_agent.protocol import UserWorkspace


def workspace_volume_name(tenant_id: UUID, user_id: UUID) -> str:
    """Return the docker named-volume identifier for a ``(tenant, user)`` pair.

    Deterministic — the same pair always maps to the same volume, so a
    ``resolve()`` after a row already exists never has to reconcile a
    name. The id components are plain UUIDs (no secret), and an
    ``helix-ws-`` prefix makes the volume self-describing in
    ``docker volume ls``.
    """
    return f"helix-ws-{tenant_id}-{user_id}"


class UserWorkspaceStore(abc.ABC):
    """Per-user persistent-workspace registry, scoped to ``(tenant_id, user_id)``.

    Supervisor-owned — there is no RLS on ``user_workspace``; the tenant
    and user are passed explicitly and scoping is application-layer
    (Mini-ADR J-1).
    """

    @abc.abstractmethod
    async def resolve(self, *, tenant_id: UUID, user_id: UUID) -> UserWorkspace:
        """Return the workspace for ``(tenant_id, user_id)``, creating it if absent.

        Idempotent upsert keyed by ``(tenant_id, user_id)``. The
        ``volume_name`` is deterministic (:func:`workspace_volume_name`),
        so a repeat call never changes it; ``last_accessed_at`` is
        bumped to *now* on every call.
        """
