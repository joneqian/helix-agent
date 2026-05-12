"""``AuthMiddleware`` — JWT validation in front of the API surface.

Stream C.1 only implements the **JWT branch**. The middleware exists in
the request lifecycle between :class:`ObservabilityMiddleware` (outer) and
:class:`AuditContextMiddleware` (inner) — Auth must run first so the
downstream context-var publisher / rate limiter / handlers can read
``request.state.principal``.

API key (Stream C.3) and mTLS (Stream C.2) branches will land as
additional ``Authorization``-header / scope-based recognisers inside this
same middleware (ADR C-2 — single middleware, unified Principal).

Endpoints exempt from authentication are matched by *prefix* — the
defaults are ``/healthz`` and ``/metrics``. Exempt requests pass through
without a principal; AuditContextMiddleware falls back to its dev defaults
in that case.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from control_plane.audit import emit
from control_plane.auth.errors import AuthError, MissingCredentialsError
from control_plane.auth.jwt_verifier import JWTVerifier
from helix_agent.common.observability import current_trace_id_hex
from helix_agent.protocol import AuditAction, AuditResult, Principal
from helix_agent.runtime.audit.logger import AuditLogger

logger = logging.getLogger("helix.control_plane.auth")

_BEARER_PREFIX = "bearer "

# Audit failures are bucketed under a synthetic "system" tenant when we
# couldn't extract one from the token. UUID is the nil-UUID for visibility
# in dashboards (matches B-5's dev-default convention).
_UNKNOWN_TENANT = UUID("00000000-0000-0000-0000-000000000000")
_UNKNOWN_ACTOR = "unauthenticated"


class AuthMiddleware(BaseHTTPMiddleware):
    """Verify the JWT and populate :attr:`Request.state.principal`."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        verifier: JWTVerifier,
        exempt_path_prefixes: Iterable[str] = ("/healthz", "/metrics"),
        audit_logger: AuditLogger | None = None,
    ) -> None:
        super().__init__(app)
        self._verifier = verifier
        # Tuple so the prefix scan is O(n) but n is tiny (~2).
        self._exempt = tuple(p.rstrip("/") for p in exempt_path_prefixes)
        self._audit_logger = audit_logger

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if self._is_exempt(request.url.path):
            return await call_next(request)

        token = _extract_bearer(request)
        if token is None:
            return await self._reject(request, MissingCredentialsError())

        try:
            claims = await self._verifier.verify(token)
        except AuthError as exc:
            return await self._reject(request, exc)

        principal = Principal.from_jwt_claims(claims)
        request.state.principal = principal
        # Legacy aliases — pre-C.1 handlers (audit emit, rate-limit key
        # builder, runs.py) read these and continue to work unchanged.
        request.state.tenant_id = principal.tenant_id
        request.state.actor_id = principal.subject_id

        return await call_next(request)

    def _is_exempt(self, path: str) -> bool:
        path_clean = path.rstrip("/")
        return any(
            path_clean == prefix or path_clean.startswith(prefix + "/") for prefix in self._exempt
        )

    async def _reject(self, request: Request, error: AuthError) -> JSONResponse:
        # Server-side detail goes to the structured logger; the response
        # only ever carries the public ``code`` / ``public_message``.
        logger.info(
            "auth.reject",
            extra={
                "error_code": error.code,
                "path": request.url.path,
                "method": request.method,
            },
        )
        if self._audit_logger is not None:
            try:
                await emit(
                    self._audit_logger,
                    tenant_id=_UNKNOWN_TENANT,
                    actor_id=_UNKNOWN_ACTOR,
                    action=AuditAction.AUTH_LOGIN_FAILED,
                    resource_type="user",
                    resource_id=error.code,
                    trace_id=current_trace_id_hex(),
                    result=AuditResult.DENIED,
                    reason=error.code,
                    details={"path": request.url.path, "method": request.method},
                )
            except Exception:
                # Audit failures must never block the auth response.
                logger.exception("auth.reject.audit_emit_failed")
        return JSONResponse(
            status_code=error.status,
            content={
                "success": False,
                "data": None,
                "error": {"code": error.code, "message": error.public_message},
            },
            headers={"WWW-Authenticate": 'Bearer realm="helix-agent"'},
        )


def _extract_bearer(request: Request) -> str | None:
    """Return the bearer token from ``Authorization`` or ``None`` if absent/malformed."""
    raw = request.headers.get("Authorization", "")
    if not raw:
        return None
    if not raw.lower().startswith(_BEARER_PREFIX):
        return None
    token = raw[len(_BEARER_PREFIX) :].strip()
    return token or None
