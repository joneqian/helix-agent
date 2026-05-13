"""Auth subsystem — Stream C.1 (JWT) / C.2 (mTLS) / C.3 (API key + RBAC).

Public surface:

* :class:`JWTVerifier` / :class:`HTTPJWKSProvider` / :class:`StaticJWKSProvider`
  (C.1)
* :class:`MTLSVerifier` / :func:`parse_xfcc_header` (C.2)
* :class:`ApiKeyVerifier` / :func:`mint_api_key` / :data:`API_KEY_SENTINEL`
  (C.3)
* :class:`AuthMiddleware` — single middleware that fans out to all
  three branches and produces a unified :class:`Principal`
* :mod:`control_plane.auth.rbac` — pure ``is_allowed(...)`` decision
  matrix (C.3 follow-ups will narrow by tenant)
* :class:`AuthError` and subclasses — typed failure modes.
"""

from control_plane.auth.api_key_verifier import (
    API_KEY_PREFIX_LEN,
    API_KEY_SENTINEL,
    ApiKeyVerifier,
    GeneratedApiKey,
    is_api_key_bearer,
    mint_api_key,
    supports_scope,
)
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
from control_plane.auth.rbac import is_allowed

__all__ = [
    "API_KEY_PREFIX_LEN",
    "API_KEY_SENTINEL",
    "ApiKeyVerifier",
    "AuthBackendUnavailableError",
    "AuthError",
    "AuthMiddleware",
    "GeneratedApiKey",
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
    "is_allowed",
    "is_api_key_bearer",
    "mint_api_key",
    "parse_xfcc_header",
    "supports_scope",
]
