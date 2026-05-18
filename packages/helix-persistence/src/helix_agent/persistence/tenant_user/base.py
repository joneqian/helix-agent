"""Abstract ``TenantUserStore`` repository — Stream J.14.

Implementations:
- :class:`helix_agent.persistence.tenant_user.memory.InMemoryTenantUserStore`
- :class:`helix_agent.persistence.tenant_user.sql.SqlTenantUserStore`
"""

from __future__ import annotations

import abc
from uuid import UUID

from helix_agent.protocol import SubjectType, TenantUser


class TenantUserStore(abc.ABC):
    """Per-user registry repository.

    Every method takes ``tenant_id`` explicitly — the tenant is the hard
    isolation boundary. ``user_id`` (the surrogate ``TenantUser.id``) is
    an application-layer ownership scope.
    """

    @abc.abstractmethod
    async def resolve(
        self,
        *,
        tenant_id: UUID,
        subject_type: SubjectType,
        subject_id: str,
        display_name: str | None = None,
    ) -> TenantUser:
        """Return the registry row for this principal, creating it if absent.

        Idempotent upsert keyed by ``(tenant_id, subject_type,
        subject_id)``. ``last_active_at`` is bumped to *now* on every
        call; ``display_name`` overwrites the stored value only when a
        non-``None`` value is supplied.
        """

    @abc.abstractmethod
    async def get(self, user_id: UUID, *, tenant_id: UUID) -> TenantUser | None:
        """Read a user by surrogate id, filtered to ``tenant_id``.

        Returns ``None`` when the row does not exist or belongs to a
        different tenant — never reveals cross-tenant existence.
        """
