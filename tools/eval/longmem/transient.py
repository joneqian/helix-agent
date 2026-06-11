"""Shared transient-failure retry for real-run HTTP paths — Stream CM-N5.

Real baseline runs sit on DashScope for hours; three failure shapes
showed up in the wild (2026-06-10/11 rounds 2-4) and all must
self-heal:

- capacity throttling reported as HTTP 400 with a throttle-shaped
  body (DashScope quirk — not 429),
- genuine 429 / 5xx,
- transport drops (``ReadTimeout`` / ``ConnectError`` /
  ``RemoteProtocolError``) — round 4 killed a full end-to-end pass
  via a single unretried ``ReadTimeout`` on the answer call.

Genuine content 400s re-raise immediately. The backoff window must
out-wait DashScope's minutes-long throttling: 10 retries capped at
120s per sleep ≈ an 11-minute total window, with ±25% jitter so
concurrent callers desynchronise instead of retrying into the same
window.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

MAX_RETRIES = 10
SLEEP_CAP_S = 120.0
_THROTTLE_MARKERS = ("ServiceUnavailable", "Too many requests", "throttl", "rate limit")

T = TypeVar("T")


def is_retryable(exc: httpx.HTTPError) -> bool:
    """Transport drops and throttle/server-side statuses retry; the rest don't."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429 or status >= 500:
            return True
        return any(marker in exc.response.text for marker in _THROTTLE_MARKERS)
    return False


async def with_retries(fn: Callable[[], Awaitable[T]]) -> T:
    """Run ``fn``, retrying transient failures with exponential backoff."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await fn()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if not is_retryable(exc) or attempt == MAX_RETRIES:
                raise
            delay = min(2.0 * 2**attempt, SLEEP_CAP_S)
            # Retry jitter, not crypto.
            jitter = random.uniform(0.75, 1.25)  # noqa: S311
            await asyncio.sleep(delay * jitter)
    raise AssertionError("unreachable")  # pragma: no cover
