"""Per-user scope helpers — Stream J.14.

Resolve the calling principal to a ``tenant_user.id`` and enforce
thread ownership for human-user principals.

A thread stamped with a ``user_id`` is private to that user. Machine
principals (service / service_account) and tenant admins keep
tenant-wide access; threads with no ``user_id`` (created before J.14,
or machine-triggered) keep the legacy tenant-scoped behaviour.
"""

from __future__ import annotations

from uuid import UUID

from starlette.requests import Request

from control_plane.auth.rbac import is_admin
from helix_agent.persistence.tenant_user import TenantUserStore
from helix_agent.protocol import Principal, ThreadMeta


def get_user_repo(request: Request) -> TenantUserStore:
    """FastAPI dependency — the per-user registry store."""
    return request.app.state.tenant_user_repo  # type: ignore[no-any-return]


async def resolve_caller_user_id(request: Request, users: TenantUserStore) -> UUID | None:
    """Return the calling user's ``tenant_user.id``.

    ``None`` for machine principals (service / service_account) — they
    own no per-user instance. For human users this upserts the registry
    row and bumps ``last_active_at``.
    """
    principal: Principal = request.state.principal
    if principal.subject_type != "user":
        return None
    user = await users.resolve(
        tenant_id=principal.tenant_id,
        subject_type=principal.subject_type,
        subject_id=principal.subject_id,
    )
    return user.id


def caller_owns_thread(
    *,
    meta: ThreadMeta,
    caller_user_id: UUID | None,
    principal: Principal,
) -> bool:
    """``True`` if the principal may read / run / mutate ``meta``'s thread."""
    if meta.user_id is None:
        return True  # unowned — legacy tenant-scoped access
    if principal.subject_type != "user":
        return True  # machine principal — tenant-scoped
    if is_admin(principal):
        return True  # tenant admin — tenant-wide access
    return caller_user_id == meta.user_id


def thread_list_filter(*, caller_user_id: UUID | None, principal: Principal) -> UUID | None:
    """The ``user_id`` filter for thread *list* endpoints.

    A plain user sees only their own threads; tenant admins and machine
    principals see every thread in the tenant (``None`` = no filter).
    """
    if caller_user_id is None:  # machine principal
        return None
    if is_admin(principal):
        return None
    return caller_user_id
