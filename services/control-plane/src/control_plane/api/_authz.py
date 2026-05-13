"""FastAPI dependencies that enforce :mod:`control_plane.auth.rbac` — Stream C.3.

Centralises the ``authorize`` pattern used by admin routers so each
handler can declare its required ``(resource, action)`` without touching
audit emission.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from control_plane.audit import emit
from control_plane.auth.rbac import Action, Resource, collect_roles_for_audit, is_allowed
from helix_agent.common.observability import current_trace_id_hex
from helix_agent.protocol import AuditAction, AuditResult, Principal
from helix_agent.runtime.audit.logger import AuditLogger

logger = logging.getLogger("helix.control_plane.api.authz")


def _get_audit(request: Request) -> AuditLogger:
    return request.app.state.audit_logger  # type: ignore[no-any-return]


def _principal(request: Request) -> Principal:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        # AuthMiddleware should have already 401'd, but belt-and-braces.
        raise HTTPException(status_code=401, detail="unauthenticated")
    return principal


def require(resource: Resource, action: Action) -> Callable[..., Awaitable[Principal]]:
    """Return a FastAPI dependency that 403s if the principal lacks ``(resource, action)``."""

    async def _dep(
        request: Request,
        principal: Annotated[Principal, Depends(_principal)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
    ) -> Principal:
        if is_allowed(principal, resource=resource, action=action):
            return principal
        try:
            await emit(
                audit,
                tenant_id=principal.tenant_id,
                actor_id=principal.subject_id,
                action=AuditAction.AUTH_LOGIN_FAILED,
                resource_type="user",
                resource_id=f"{resource}:{action}",
                result=AuditResult.DENIED,
                reason="RBAC_FORBIDDEN",
                trace_id=current_trace_id_hex(),
                details={
                    "resource": resource,
                    "action": action,
                    "roles": list(collect_roles_for_audit(principal)),
                    "subject_type": principal.subject_type,
                },
            )
        except Exception:
            # Never block the 403 on audit failure; record it and proceed.
            logger.exception("authz.deny_audit_emit_failed")
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "principal lacks required role"},
        )

    return _dep
