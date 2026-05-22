"""Trigger scheduler — Stream J.10 (Mini-ADR J-26 / J-42).

A single-replica background worker inside the control-plane. Every
``interval_s`` it polls the ``agent_trigger`` table for enabled ``cron``
triggers, computes each one's next fire time with ``croniter``, and —
for any trigger whose schedule has come due — starts an agent run via
the shared :func:`control_plane.trigger_firing.fire_trigger` path.

Mini-ADR J-42: the ``agent_trigger`` table is the single source of
truth (no APScheduler jobstore). Restart-safe — on restart the next
fire time is recomputed from the cron expression + ``last_fired_at``;
a long outage fires a due trigger once, not once per missed slot.

Wiring (in :func:`control_plane.app.create_app`): started from the
FastAPI ``lifespan`` ``yield``, stopped via :meth:`stop` from the
``finally`` branch — the same shape as :class:`ReservationReaper`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from croniter import croniter

from control_plane.runtime import AgentRuntime
from control_plane.trigger_firing import fire_trigger
from helix_agent.common.observability import helix_counter
from helix_agent.persistence import (
    ApprovalStore,
    ThreadMetaStore,
    TriggerRunStore,
    TriggerStore,
)
from helix_agent.persistence.agent_spec import AgentSpecStore
from helix_agent.persistence.rls import (
    bypass_rls_var,
    current_tenant_id_var,
    current_user_id_var,
)
from helix_agent.protocol import TriggerRecord
from helix_agent.runtime.audit.logger import AuditLogger

logger = logging.getLogger("helix.control_plane.scheduler")

#: Periodic-loop failures — alerting keys off ``rate(...)``.
_scheduler_cycle_errors = helix_counter(
    "helix_control_plane_trigger_scheduler_cycle_errors_total",
    "Trigger scheduler cycles that ended in a caught exception.",
)


def _next_fire(expr: str, after: datetime) -> datetime:
    """Next cron fire time strictly after ``after`` (raises on a bad expr)."""
    result: datetime = croniter(expr, after).get_next(datetime)
    return result


def _is_cron_due(trigger: TriggerRecord, *, now: datetime) -> bool:
    """Whether a cron trigger's next scheduled fire has come due.

    The base is ``last_fired_at`` (or ``created_at`` for a trigger that
    never fired). A malformed cron expression raises — the caller
    catches it per-trigger so one bad row never aborts the sweep.
    """
    expr = trigger.config.get("expr")
    if not isinstance(expr, str):
        msg = f"trigger {trigger.id} has no cron expr"
        raise ValueError(msg)
    base = trigger.last_fired_at or trigger.created_at
    return _next_fire(expr, base) <= now


class TriggerScheduler:
    """Background worker: poll ``agent_trigger`` + fire due cron triggers."""

    def __init__(
        self,
        *,
        trigger_store: TriggerStore,
        trigger_run_store: TriggerRunStore,
        agent_spec_store: AgentSpecStore,
        thread_store: ThreadMetaStore,
        runtime: AgentRuntime,
        audit_logger: AuditLogger,
        approval_store: ApprovalStore,
        interval_s: int,
        batch_size: int = 100,
    ) -> None:
        if interval_s <= 0:
            msg = "interval_s must be positive"
            raise ValueError(msg)
        self._triggers = trigger_store
        self._trigger_runs = trigger_run_store
        self._agents = agent_spec_store
        self._threads = thread_store
        self._runtime = runtime
        self._audit = audit_logger
        self._approvals = approval_store
        self._interval_s = interval_s
        self._batch_size = batch_size
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Schedule the periodic loop. Idempotent: re-calling is a no-op."""
        if self.is_running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="trigger-scheduler")

    async def stop(self) -> None:
        """Signal stop + await the loop's clean exit."""
        if self._task is None:
            return
        self._stop.set()
        try:
            await asyncio.wait_for(self._task, timeout=self._interval_s + 5)
        except (TimeoutError, asyncio.CancelledError):
            self._task.cancel()
        finally:
            self._task = None

    async def run_once(self) -> int:
        """Run one sweep: fire every due cron trigger. Return the count fired.

        The ``agent_trigger`` scan is cross-tenant, so it runs in an
        RLS-bypass context (same as :class:`ReservationReaper`); each
        firing then re-scopes to the trigger's own tenant.
        """
        bypass = bypass_rls_var.set(True)
        tenant = current_tenant_id_var.set(None)
        try:
            triggers = await self._triggers.list_enabled_cron()
        finally:
            current_tenant_id_var.reset(tenant)
            bypass_rls_var.reset(bypass)

        now = datetime.now(UTC)
        fired = 0
        for trigger in triggers[: self._batch_size]:
            try:
                if not _is_cron_due(trigger, now=now):
                    continue
                if await self._fire(trigger, now=now):
                    fired += 1
            except Exception:
                # One bad trigger (malformed cron, missing agent, …)
                # must never abort the sweep.
                logger.exception(
                    "scheduler.trigger_failed",
                    extra={
                        "trigger_id": str(trigger.id),
                        "tenant_id": str(trigger.tenant_id),
                    },
                )
        return fired

    async def _fire(self, trigger: TriggerRecord, *, now: datetime) -> bool:
        """Fire ``trigger`` inside its own tenant (+ user) RLS context."""
        tenant_tok = current_tenant_id_var.set(trigger.tenant_id)
        bypass_tok = bypass_rls_var.set(False)
        user_tok = current_user_id_var.set(trigger.user_id)
        try:
            return await fire_trigger(
                trigger,
                now=now,
                agent_spec_store=self._agents,
                runtime=self._runtime,
                thread_store=self._threads,
                audit_logger=self._audit,
                approval_store=self._approvals,
                trigger_store=self._triggers,
                trigger_run_store=self._trigger_runs,
            )
        finally:
            current_user_id_var.reset(user_tok)
            bypass_rls_var.reset(bypass_tok)
            current_tenant_id_var.reset(tenant_tok)

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                fired = await self.run_once()
                if fired:
                    logger.info("scheduler.swept", extra={"fired_count": fired})
            except Exception:
                logger.exception("scheduler.cycle_failed")
                _scheduler_cycle_errors.inc()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval_s)
            except TimeoutError:
                # Normal periodic wake-up — the interval elapsed with no stop
                # signal, so loop round for the next sweep.
                pass


__all__ = ["TriggerScheduler"]
