"""In-process token-bucket :class:`RateLimiter` — M0 only.

ADR B-1 calls out that this implementation assumes **one control-plane
replica**: every replica owns an independent bucket, so deploying two
behind a single LB would defeat the limit. Stream C.6 replaces this with
a Redis-backed atomic implementation; until then the
``settings.single_instance`` guard fails startup when operators try to
scale beyond one replica.

The bucket map is bounded only by unique ``(dimension, key)`` pairs. For
dev / single-tenant M0 traffic this is fine; if it ever grows we'll
either evict (LRU) or migrate to Redis early.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from control_plane.ratelimit.base import RateLimitDecision

Clock = Callable[[], int]


def _default_clock() -> int:
    """Return current time as milliseconds since the epoch."""
    return time.monotonic_ns() // 1_000_000


@dataclass
class _TokenBucket:
    tokens: float
    last_refill_ms: int


class InProcessTokenBucketLimiter:
    """Asyncio-safe token bucket keyed by ``(dimension, key)``."""

    def __init__(
        self,
        *,
        capacity: int,
        refill_per_sec: float,
        clock: Clock | None = None,
    ) -> None:
        if capacity <= 0:
            msg = f"capacity must be > 0, got {capacity}"
            raise ValueError(msg)
        if refill_per_sec <= 0:
            msg = f"refill_per_sec must be > 0, got {refill_per_sec}"
            raise ValueError(msg)
        self._capacity = float(capacity)
        self._refill_per_sec = float(refill_per_sec)
        self._clock = clock or _default_clock
        self._buckets: dict[tuple[str, str], _TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, *, dimension: str, key: str) -> RateLimitDecision:
        async with self._lock:
            now_ms = self._clock()
            bucket = self._buckets.get((dimension, key))
            if bucket is None:
                bucket = _TokenBucket(tokens=self._capacity, last_refill_ms=now_ms)
                self._buckets[(dimension, key)] = bucket

            elapsed_s = max(0, now_ms - bucket.last_refill_ms) / 1000.0
            bucket.tokens = min(
                self._capacity,
                bucket.tokens + elapsed_s * self._refill_per_sec,
            )
            bucket.last_refill_ms = now_ms

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return RateLimitDecision(
                    allowed=True,
                    retry_after_s=0.0,
                    remaining=bucket.tokens,
                )

            deficit = 1.0 - bucket.tokens
            retry_after_s = deficit / self._refill_per_sec
            return RateLimitDecision(
                allowed=False,
                retry_after_s=retry_after_s,
                remaining=bucket.tokens,
            )
