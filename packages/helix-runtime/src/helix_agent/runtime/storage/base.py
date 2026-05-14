"""``ObjectStore`` Protocol — S3-compatible object storage abstraction.

Per [ADR-0004](../../../../../../docs/adr/0004-object-storage.md). All
call sites depend on this Protocol, not the S3 client directly, so the
in-memory implementation can stand in for unit tests and a different
S3-compatible backend (MinIO / Aliyun OSS / AWS S3 / Tencent COS) can be
swapped via the factory without code changes.

**Multipart upload deferred** to M0 follow-up (per ADR § 3). M0 first cut
handles small objects only; ``put`` takes ``bytes`` rather than a stream.

Stream D.1b extends ``put`` with optional S3 Object Lock parameters
(``retain_until`` + ``lock_mode``) used by the D.1c audit WORM backup
worker. See STREAM-D-DESIGN § 2.3 + Mini-ADR D-2.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Literal, Protocol

# The two Object Lock retention modes S3 / MinIO expose. We deliberately
# do not surface ``None`` semantics other than "no lock" — see Mini-ADR
# D-2: limiting to ``governance`` / ``compliance`` keeps in-memory mock
# and S3 backend behaviorally aligned and prevents callers from drifting
# the bucket-level default by accident.
LockMode = Literal["governance", "compliance"]


class ObjectStoreError(Exception):
    """Base class for object-store failures."""


class ObjectNotFoundError(ObjectStoreError):
    """Raised by ``get`` / ``delete`` when the key does not exist."""


class ObjectLockedError(ObjectStoreError):
    """Raised when a put would overwrite a still-retained, locked object.

    The compliance mode is intentionally un-overridable — even root
    cannot shorten ``retain_until`` or delete before it elapses. The
    in-memory store surfaces this as ``ObjectLockedError``; the S3
    backend lets the underlying ``AccessDenied`` propagate wrapped as
    :class:`ObjectStoreError` since each S3-compatible vendor returns
    a slightly different code.
    """


class ObjectStore(Protocol):
    """Tenant-namespaced object storage surface.

    The store does **not** enforce key-naming convention; callers must
    prefix with ``{tenant_id}/...`` per ADR-0004 § 2.3. Cross-tenant
    isolation lives at the access-control layer (Stream C).
    """

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
        retain_until: datetime | None = None,
        lock_mode: LockMode | None = None,
    ) -> None:
        """Write ``data`` at ``key``; overwrites if the key already exists.

        Optional Object Lock parameters (STREAM-D-DESIGN § 2.3):

        * ``retain_until`` — UTC datetime the object stays
          retention-locked until. ``None`` means no retention is set.
        * ``lock_mode`` — ``"governance"`` (privileged roles may override)
          or ``"compliance"`` (immutable until ``retain_until``).

        Contract:

        * Both ``retain_until`` and ``lock_mode`` must be supplied
          together, or neither — passing one without the other raises
          :class:`ValueError`. They jointly express "lock this object
          until X" and have no useful single-argument form.
        * For ``lock_mode="compliance"``, re-putting the same key
          before ``retain_until`` raises :class:`ObjectLockedError`
          (in-memory) or surfaces the backend's ``AccessDenied``
          wrapped as :class:`ObjectStoreError` (S3).
        * For ``lock_mode="governance"``, a privileged caller may
          override and re-put before retention elapses — the lock
          is advisory in the mode sense.
        * The target bucket must already have Object Lock enabled when
          locks are used; bucket-level setup belongs to IaC, not the
          runtime API.
        """

    async def get(self, key: str) -> bytes:
        """Read the full object at ``key``.

        :raises ObjectNotFoundError: the key does not exist.
        """

    async def delete(self, key: str) -> None:
        """Remove the object at ``key``.

        Idempotent — deleting a non-existent key does NOT raise.
        """

    async def list_prefix(self, prefix: str) -> list[str]:
        """Return every key beginning with ``prefix``, lexicographically sorted."""

    async def presigned_url(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        method: Literal["GET", "PUT"] = "GET",
    ) -> str:
        """Generate a time-limited signed URL the client can fetch directly.

        Used by the Control Plane to hand off large upload/download flows to
        the client without proxying bytes through the API tier.
        """


def validate_lock_args(retain_until: datetime | None, lock_mode: LockMode | None) -> None:
    """Reject the partial-spec cases described in :class:`ObjectStore.put`.

    Pulled out as a standalone helper so every backend uses the same
    rule and unit tests can pin the message without instantiating
    a store.
    """
    if (retain_until is None) != (lock_mode is None):
        msg = (
            "retain_until and lock_mode must be specified together "
            f"(got retain_until={retain_until!r}, lock_mode={lock_mode!r})"
        )
        raise ValueError(msg)
