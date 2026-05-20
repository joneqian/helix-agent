"""Service-account + API-key Pydantic models — Stream C.3.

Three persisted artefacts:

* :class:`ServiceAccount` — long-lived programmatic identity owned by a
  tenant. Has zero or more :class:`ApiKey` rows attached.
* :class:`ApiKey` — bearer credential. The plaintext secret is returned
  **once** at creation; the stored row carries only ``prefix`` (for
  lookup) + ``hash`` (argon2id of the full bytes).
* :class:`ApiKeyScope` — coarse-grained capability list. Maps onto the
  RBAC matrix at request time (Stream C.4 will narrow it further with
  Postgres RLS).

See ``subsystems/15-authn-authz.md`` § 3 / 5.4 + ADR C-2.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Service Account
# ---------------------------------------------------------------------------


class ServiceAccount(BaseModel):
    """A tenant-scoped programmatic identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str
    description: str = ""
    is_active: bool = True
    created_at: datetime
    created_by: str


# ---------------------------------------------------------------------------
# API Key
# ---------------------------------------------------------------------------


class ApiKeyScope(StrEnum):
    """The bag of scopes an API key may carry.

    Kept small in M0 — narrower than the RBAC ``(role, resource, action)``
    matrix because issuing per-action API keys is unusual. Common usage
    pattern: pick one of ``read`` / ``write`` / ``admin``.
    """

    READ = "read"  # GET endpoints
    WRITE = "write"  # POST/PUT/DELETE business endpoints
    ADMIN = "admin"  # service-account / role-binding mutations


#: Stored prefix length. The full bearer string is
#: ``aforge_pat_<5hex>_<32 random>`` (49 chars total); the prefix column
#: persists ``aforge_pat_<5hex>_<8 random>`` (25 chars). The 8 random
#: hex from the tail belong to the prefix segment so that two API keys
#: sharing the same tenant do not collide on the column's ``UNIQUE``
#: constraint — Stream K.K1 surfaced this latent Stream C.3 bug while
#: implementing rotation (which is structurally "create a second key").
#: Keep this constant in sync with
#: :data:`control_plane.auth.api_key_verifier.API_KEY_PREFIX_LEN`.
API_KEY_STORED_PREFIX_LEN: int = 25


class ApiKey(BaseModel):
    """A persisted API-key row (sans secret).

    The plaintext bearer is **never** stored or echoed after creation —
    the caller of :meth:`ApiKeyStore.create` receives :class:`ApiKeyCreated`
    once, then must hand the secret to the end user.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    service_account_id: UUID
    tenant_id: UUID
    prefix: str
    secret_hash: str
    scopes: tuple[ApiKeyScope, ...] = ()
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    #: Stream K.K1 — set when a /rotate call replaces this key. While
    #: ``now() < rotated_at + grace_period_s`` the bearer still verifies
    #: (double-active window). The verifier stops accepting the bearer
    #: once the window closes; the row is left in place for audit /
    #: traceability and reaped by ``retention-cleanup-job`` on its own
    #: schedule.
    rotated_at: datetime | None = None
    grace_period_s: int | None = None
    created_at: datetime
    created_by: str

    @property
    def is_active(self) -> bool:
        """``revoked_at`` is empty.

        Stream K.K1 grace-window check (``rotated_at + grace_period_s``)
        lives in :meth:`ApiKeyVerifier.verify` so this property stays a
        cheap, time-free predicate suitable for UI listings.
        """
        return self.revoked_at is None


class ApiKeyCreated(BaseModel):
    """One-shot return shape for ``POST /v1/service_accounts/{id}/api_keys``.

    Carries the plaintext bearer token. Callers must surface it to the
    user immediately and never persist it server-side. The companion
    :class:`ApiKey` row carries the same metadata minus the secret.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    api_key: ApiKey
    plaintext: str

    @classmethod
    def from_key(cls, *, api_key: ApiKey, plaintext: str) -> Self:
        return cls(api_key=api_key, plaintext=plaintext)


# ---------------------------------------------------------------------------
# Role binding
# ---------------------------------------------------------------------------


class Role(StrEnum):
    """The three-tier role model per ``subsystems/15`` § 3.3."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class RoleBinding(BaseModel):
    """Maps a subject (user / service_account) to a role within a tenant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    subject_type: str  # "user" | "service_account"
    subject_id: UUID
    tenant_id: UUID
    role: Role
    granted_by: str
    granted_at: datetime
