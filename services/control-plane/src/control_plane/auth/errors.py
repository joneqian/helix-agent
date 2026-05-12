"""Typed auth failures — Stream C.1.

These never carry exception detail from the underlying library (PyJWT
exceptions, JWKS HTTP failures, etc.). The middleware translates them to
HTTP responses using the public ``code`` / ``public_message`` attributes —
internal details are logged server-side via the structured logger
(matches CodeQL ``py/stack-trace-exposure`` mitigation pattern established
in B.5).
"""

from __future__ import annotations


class AuthError(Exception):
    """Base class. ``status`` is the HTTP code; ``code`` goes into envelope."""

    code: str = "AUTH_UNAUTHENTICATED"
    public_message: str = "Authentication required"
    status: int = 401


class MissingCredentialsError(AuthError):
    """No ``Authorization`` header (or an unparseable one) was provided."""

    code = "AUTH_MISSING_CREDENTIALS"
    public_message = "Authentication required"


class InvalidTokenError(AuthError):
    """Token decoded but failed verification (signature, iss, aud, kid)."""

    code = "AUTH_INVALID_TOKEN"
    public_message = "Invalid or unrecognised token"


class TokenExpiredError(AuthError):
    """Signed correctly but ``exp`` is in the past."""

    code = "AUTH_TOKEN_EXPIRED"
    public_message = "Token has expired"


class AuthBackendUnavailableError(AuthError):
    """JWKS endpoint unreachable / 5xx — request cannot be validated."""

    code = "AUTH_BACKEND_UNAVAILABLE"
    public_message = "Authentication backend unavailable"
    status = 503
