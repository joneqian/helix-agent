"""Abstract auth-store interfaces — Stream C.3.

Three stores; each is per-tenant and tenant-aware:

* :class:`ServiceAccountStore` — CRUD on ``service_account`` rows
* :class:`ApiKeyStore` — CRUD on ``api_key`` rows + prefix lookup
* :class:`RoleBindingStore` — CRUD on ``role_binding`` rows
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from helix_agent.protocol import ApiKey, ApiKeyScope, Role, RoleBinding, ServiceAccount


class DuplicateServiceAccountError(Exception):
    """``(tenant_id, name)`` collision."""

    def __init__(self, *, tenant_id: UUID, name: str) -> None:
        super().__init__(f"service_account already exists: tenant={tenant_id} name={name}")
        self.tenant_id = tenant_id
        self.name = name


class DuplicateApiKeyPrefixError(Exception):
    """``prefix`` collision (vanishingly rare; 16-char random + retry covers it)."""

    def __init__(self, *, prefix: str) -> None:
        super().__init__(f"api_key prefix already exists: {prefix}")
        self.prefix = prefix


class DuplicateRoleBindingError(Exception):
    """``(subject_type, subject_id, tenant_id, role)`` collision."""

    def __init__(
        self,
        *,
        subject_type: str,
        subject_id: UUID,
        tenant_id: UUID,
        role: Role,
    ) -> None:
        super().__init__(
            f"role_binding already exists: subject={subject_type}:{subject_id} "
            f"tenant={tenant_id} role={role.value}"
        )
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.tenant_id = tenant_id
        self.role = role


# ---------------------------------------------------------------------------
# ServiceAccountStore
# ---------------------------------------------------------------------------


class ServiceAccountStore(abc.ABC):
    @abc.abstractmethod
    async def create(
        self,
        *,
        tenant_id: UUID,
        name: str,
        description: str,
        created_by: str,
    ) -> ServiceAccount:
        """Raises :class:`DuplicateServiceAccountError` on ``(tenant_id, name)`` collision."""

    @abc.abstractmethod
    async def get(self, *, tenant_id: UUID, service_account_id: UUID) -> ServiceAccount | None:
        """Fetch one row by id, scoped to ``tenant_id``."""

    @abc.abstractmethod
    async def list_by_tenant(
        self,
        *,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ServiceAccount]:
        """Paginated list, newest first."""

    @abc.abstractmethod
    async def delete(self, *, tenant_id: UUID, service_account_id: UUID) -> bool:
        """Hard-delete (cascades to API keys). Returns ``False`` if no row matched."""


# ---------------------------------------------------------------------------
# ApiKeyStore
# ---------------------------------------------------------------------------


class ApiKeyStore(abc.ABC):
    @abc.abstractmethod
    async def create(
        self,
        *,
        tenant_id: UUID,
        service_account_id: UUID,
        prefix: str,
        secret_hash: str,
        scopes: Sequence[ApiKeyScope],
        expires_at: datetime | None,
        created_by: str,
    ) -> ApiKey:
        """Raises :class:`DuplicateApiKeyPrefixError` if prefix collides."""

    @abc.abstractmethod
    async def get_by_prefix(self, *, prefix: str) -> ApiKey | None:
        """Tenant-agnostic prefix lookup — by design, since the verifier
        path runs **before** ``request.state.tenant_id`` is resolved.
        Soft-deleted (revoked) keys are returned for the caller to
        check."""

    @abc.abstractmethod
    async def list_by_service_account(
        self,
        *,
        tenant_id: UUID,
        service_account_id: UUID,
    ) -> list[ApiKey]:
        """All keys for one service account; newest first."""

    @abc.abstractmethod
    async def revoke(self, *, tenant_id: UUID, api_key_id: UUID) -> bool:
        """Stamp ``revoked_at`` if not already set. Returns ``False`` for
        unknown / wrong-tenant id."""

    @abc.abstractmethod
    async def rotate(
        self,
        *,
        tenant_id: UUID,
        api_key_id: UUID,
        new_prefix: str,
        new_secret_hash: str,
        grace_period_s: int,
        rotated_at: datetime,
        actor_id: str,
    ) -> tuple[ApiKey, ApiKey] | None:
        """Stream K.K1 — issue a replacement and start the grace window.

        Stamps ``rotated_at`` + ``grace_period_s`` on the old row (so
        the verifier keeps accepting it until the window closes), then
        inserts a new row inheriting ``service_account_id`` / ``scopes`` /
        ``expires_at`` from the old one. The new row's ``rotated_at`` /
        ``grace_period_s`` are ``NULL`` (it has not itself been rotated).

        Returns ``(old, new)`` on success or ``None`` when the
        ``api_key_id`` is unknown, belongs to a different tenant, or
        was already revoked / already rotated.

        Raises :class:`DuplicateApiKeyPrefixError` on prefix collision.
        """

    @abc.abstractmethod
    async def touch_last_used(self, *, api_key_id: UUID, when: datetime) -> None:
        """Best-effort last-used timestamp update. Never raises."""


# ---------------------------------------------------------------------------
# RoleBindingStore
# ---------------------------------------------------------------------------


class RoleBindingStore(abc.ABC):
    @abc.abstractmethod
    async def create(
        self,
        *,
        subject_type: str,
        subject_id: UUID,
        tenant_id: UUID,
        role: Role,
        granted_by: str,
    ) -> RoleBinding:
        """Raises :class:`DuplicateRoleBindingError` on conflict."""

    @abc.abstractmethod
    async def list_for_subject(
        self,
        *,
        subject_type: str,
        subject_id: UUID,
        tenant_id: UUID | None = None,
    ) -> list[RoleBinding]:
        """All role rows for a given subject; optionally filtered by tenant."""

    @abc.abstractmethod
    async def list_for_tenant(self, *, tenant_id: UUID) -> list[RoleBinding]:
        """All role rows for the tenant — used by the admin UI."""

    @abc.abstractmethod
    async def delete(self, *, tenant_id: UUID, role_binding_id: UUID) -> bool:
        """Delete by id. Returns ``False`` if no row matched."""
