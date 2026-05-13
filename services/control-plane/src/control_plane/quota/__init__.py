"""Quota engine — Stream C.5.

Public surface:

* :class:`QuotaService` — abstract Protocol consumed by handler-side
  admission + the internal HTTP API.
* :class:`InMemoryQuotaService` — single-process implementation;
  default for unit tests and the dev fallback when no Redis DSN is
  configured.
* :class:`RedisQuotaService` — production implementation; Redis Lua
  buckets + Postgres reservation ledger.
* :class:`ReservationReaper` — background task that auto-releases
  reservations stuck in ``RESERVED`` past their max age.
"""

from control_plane.quota.base import BudgetExceededError, QuotaService
from control_plane.quota.in_memory import InMemoryQuotaService
from control_plane.quota.reaper import ReservationReaper
from control_plane.quota.redis_quota import RedisQuotaService

__all__ = [
    "BudgetExceededError",
    "InMemoryQuotaService",
    "QuotaService",
    "RedisQuotaService",
    "ReservationReaper",
]
