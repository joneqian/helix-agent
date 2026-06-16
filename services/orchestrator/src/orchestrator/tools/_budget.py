"""Per-run dynamic-worker spawn budget — 1.3 Orchestrator-Worker.

A leaf module (no imports from ``orchestrator.tools.registry``) so both
``registry`` (which references the type on :class:`ToolContext`) and
``spawn_worker`` (which constructs + consumes it) can import it without
forming an import cycle.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field


@dataclass
class WorkerSpawnBudget:
    """Per-run spawn budget — a cumulative count cap + a concurrency gate.

    Created once per run (in ``sse.run_agent``) from the platform settings
    and threaded through :class:`~orchestrator.tools.registry.ToolContext` so
    every ``spawn_worker`` call in the run shares it. ``max_per_run`` bounds
    total spawns across all turns; the semaphore bounds how many workers run
    at once.
    """

    max_per_run: int
    max_concurrent: int
    _spawned: int = 0
    _sem: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._sem = asyncio.Semaphore(self.max_concurrent)

    def try_reserve(self) -> bool:
        """Count one spawn against the per-run cap; ``False`` if exhausted."""
        if self._spawned >= self.max_per_run:
            return False
        self._spawned += 1
        return True

    @asynccontextmanager
    async def concurrency(self) -> AsyncIterator[None]:
        async with self._sem:
            yield
