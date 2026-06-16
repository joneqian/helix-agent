"""Stream 13.2 — full-flow idempotency seam for ``apply_approval_decision``.

The endpoint tests in ``test_runs_api`` seed an already-decided approval row to
exercise the replay branch. This drives the REAL winner path instead: a pending
approval → a genuine decide (the CAS winner persists ``continuation_run_id`` via
``mark_decided``) → a retry with the same key replays it WITHOUT spawning a
second continuation worker. ``run_agent`` is monkeypatched to a recording no-op
so no streaming / real graph is needed — the seam under test is the
store-then-replay data flow + spawn-exactly-once, which is model-agnostic.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from control_plane.api import runs as runs_module
from control_plane.api.runs import apply_approval_decision
from control_plane.audit import build_default_audit_logger
from helix_agent.persistence import InMemoryApprovalStore
from helix_agent.persistence.audit_log import InMemoryAuditLogStore
from helix_agent.protocol import ApprovalRecord, ApprovalStatus, Principal

_TENANT = uuid4()


def _request() -> SimpleNamespace:
    # A service principal owns no per-user instance (resolve_caller_user_id →
    # None) and an unowned thread (meta.user_id=None) passes caller_owns_thread.
    principal = Principal(subject_id=str(uuid4()), subject_type="service", tenant_id=_TENANT)
    return SimpleNamespace(
        state=SimpleNamespace(tenant_id=_TENANT, actor_id="svc", principal=principal)
    )


class _FakeGraph:
    async def aupdate_state(self, *_a: object, **_k: object) -> None:
        return None


class _FakeRunManager:
    def __init__(self) -> None:
        self.created: list[object] = []

    async def create(self, **kw: object) -> SimpleNamespace:
        rec = SimpleNamespace(**kw, bound_distilled_skills=())
        self.created.append(rec)
        return rec

    async def attach_task(self, _run_id: object, _task: object) -> bool:
        return True


class _FakeRuntime:
    def __init__(self) -> None:
        self.run_manager = _FakeRunManager()
        self.stream_bridge = object()
        self.run_event_store = None
        self.skill_run_usage_recorder = None
        self.trajectory_recorder = None

    async def get_agent(self, **_kw: object) -> SimpleNamespace:
        return SimpleNamespace(graph=_FakeGraph(), bound_distilled_skills=(), tool_replay_safe=None)

    def new_worker_spawn_budget(self) -> None:
        return None


class _FakeThreads:
    async def get(self, _thread_id: object, *, tenant_id: object) -> SimpleNamespace:
        del tenant_id
        return SimpleNamespace(agent_name="agent", agent_version="1.0.0", user_id=None)


class _FakeAgentRepo:
    async def get(self, *, tenant_id: object, name: object, version: object) -> SimpleNamespace:
        del tenant_id, name, version
        return SimpleNamespace(spec=SimpleNamespace())


def _pending(run_id: object, thread_id: object) -> ApprovalRecord:
    now = datetime.now(UTC)
    return ApprovalRecord(
        id=uuid4(),
        tenant_id=_TENANT,
        run_id=run_id,  # type: ignore[arg-type]
        thread_id=thread_id,  # type: ignore[arg-type]
        request_id="approval:flow",
        node="tools",
        reason_kind="policy_gate",
        action_summary="approval-gated tool 'http'",
        proposed_args={},
        requested_at=now,
        timeout_at=now + timedelta(hours=24),
        status=ApprovalStatus.PENDING,
    )


@pytest.mark.asyncio
async def test_winner_stores_continuation_then_retry_replays_without_respawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spawns: list[dict[str, object]] = []

    async def _fake_run_agent(**kw: object) -> None:
        spawns.append(kw)

    monkeypatch.setattr(runs_module, "run_agent", _fake_run_agent)

    approvals = InMemoryApprovalStore()
    run_id, thread_id = uuid4(), uuid4()
    await approvals.create(_pending(run_id, thread_id))

    runtime = _FakeRuntime()
    common = {
        "thread_id": thread_id,
        "run_id": run_id,
        "decision": "approve",
        "modified_args": None,
        "reason": None,
        "threads": _FakeThreads(),
        "users": object(),
        "agent_repo": _FakeAgentRepo(),
        "runtime": runtime,
        "approvals": approvals,
        "audit": build_default_audit_logger(InMemoryAuditLogStore()),
        "idempotency_key": "flow-key",
    }

    # 1) Winner decide — persists continuation_run_id via the CAS, spawns once.
    _record, continuation, replayed = await apply_approval_decision(request=_request(), **common)
    await asyncio.sleep(0)  # let the spawned task body run
    assert replayed is False
    assert len(spawns) == 1
    stored = await approvals.get_by_run(run_id=run_id, tenant_id=_TENANT)
    assert stored is not None
    assert stored.status is ApprovalStatus.APPROVED
    assert stored.continuation_run_id == continuation
    assert stored.idempotency_key == "flow-key"

    # 2) Retry with the SAME key — idempotent replay returns the same id, NO
    #    second worker spawned.
    record2, continuation2, replayed2 = await apply_approval_decision(request=_request(), **common)
    await asyncio.sleep(0)
    assert replayed2 is True
    assert record2 is None
    assert continuation2 == continuation
    assert len(spawns) == 1  # still exactly one — replay never re-spawns
