"""Auth subsystem — Stream C.1 - C.3.

C.1 ships the JWT path (this module) + ``AuthMiddleware``. API Key
(:mod:`api_key_verifier`) and mTLS (:mod:`mtls`) branches arrive in C.2 / C.3.

Public surface:

* :class:`JWTVerifier` — verifies RS256 JWTs against a :class:`JWKSProvider`
* :class:`JWKSProvider` — Protocol for fetching keys by ``kid``
* :class:`HTTPJWKSProvider` / :class:`StaticJWKSProvider` — production / test impls
* :class:`AuthMiddleware` — sits between Observability and AuditContext;
  produces ``request.state.principal`` (and the legacy ``tenant_id`` /
  ``actor_id`` aliases used by handlers and the audit emitter).
* :class:`AuthError` and subclasses — typed failure modes.
"""

from control_plane.auth.errors import (
    AuthBackendUnavailableError,
    AuthError,
    InvalidTokenError,
    MissingCredentialsError,
    TokenExpiredError,
)
from control_plane.auth.jwt_verifier import (
    HTTPJWKSProvider,
    JWKSProvider,
    JWTVerifier,
    StaticJWKSProvider,
)
from control_plane.auth.middleware import AuthMiddleware
from control_plane.auth.mtls import (
    MTLSVerifier,
    XfccElement,
    build_mtls_verifier,
    parse_xfcc_header,
)

__all__ = [
    "AuthBackendUnavailableError",
    "AuthError",
    "AuthMiddleware",
    "HTTPJWKSProvider",
    "InvalidTokenError",
    "JWKSProvider",
    "JWTVerifier",
    "MTLSVerifier",
    "MissingCredentialsError",
    "StaticJWKSProvider",
    "TokenExpiredError",
    "XfccElement",
    "build_mtls_verifier",
    "parse_xfcc_header",
]
