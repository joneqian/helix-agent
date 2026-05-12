"""Unit tests for ``RunManager``."""

from __future__ import annotations

from uuid import uuid4

import pytest

from helix_agent.runtime.runs import DisconnectMode, RunManager, RunStatus


@pytest.mark.asyncio
async def test_create_registers_run_in_pending_state() -> None:
    mgr = RunManager()
    run_id, thread_id, tenant_id = uuid4(), uuid4(), uuid4()

    record = await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)

    assert record.status is RunStatus.PENDING
    assert record.on_disconnect is DisconnectMode.CANCEL
    assert record.run_id == run_id
    assert mgr.get(run_id) is record


@pytest.mark.asyncio
async def test_create_rejects_duplicate_run_id() -> None:
    mgr = RunManager()
    run_id, thread_id, tenant_id = uuid4(), uuid4(), uuid4()

    await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)
    with pytest.raises(ValueError, match="already exists"):
        await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_list_by_thread_filters_by_tenant() -> None:
    mgr = RunManager()
    thread_id, tenant_a, tenant_b = uuid4(), uuid4(), uuid4()
    for _ in range(3):
        await mgr.create(run_id=uuid4(), thread_id=thread_id, tenant_id=tenant_a)
    await mgr.create(run_id=uuid4(), thread_id=thread_id, tenant_id=tenant_b)

    a_runs = await mgr.list_by_thread(thread_id, tenant_id=tenant_a)
    b_runs = await mgr.list_by_thread(thread_id, tenant_id=tenant_b)
    assert len(a_runs) == 3
    assert len(b_runs) == 1


@pytest.mark.asyncio
async def test_set_status_transitions() -> None:
    mgr = RunManager()
    run_id, thread_id, tenant_id = uuid4(), uuid4(), uuid4()
    await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)

    transitioned = await mgr.set_status(run_id, RunStatus.RUNNING)
    assert transitioned is True
    assert mgr.get(run_id) is not None
    assert mgr.get(run_id).status is RunStatus.RUNNING  # type: ignore[union-attr]

    succeeded = await mgr.set_status(run_id, RunStatus.SUCCESS)
    assert succeeded is True
    assert mgr.get(run_id).status is RunStatus.SUCCESS  # type: ignore[union-attr]

    missing = await mgr.set_status(uuid4(), RunStatus.SUCCESS)
    assert missing is False


@pytest.mark.asyncio
async def test_cancel_signals_abort_event_and_marks_interrupted() -> None:
    mgr = RunManager()
    run_id, thread_id, tenant_id = uuid4(), uuid4(), uuid4()
    record = await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)
    await mgr.set_status(run_id, RunStatus.RUNNING)

    cancelled = await mgr.cancel(run_id)
    assert cancelled is True
    assert record.abort_event.is_set()
    assert mgr.get(run_id).status is RunStatus.INTERRUPTED  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_cancel_does_not_overwrite_terminal_status() -> None:
    mgr = RunManager()
    run_id, thread_id, tenant_id = uuid4(), uuid4(), uuid4()
    await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)
    await mgr.set_status(run_id, RunStatus.SUCCESS)

    cancelled = await mgr.cancel(run_id)
    assert cancelled is True
    # SUCCESS is terminal — cancel signals abort_event but should not flip status
    assert mgr.get(run_id).status is RunStatus.SUCCESS  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_has_inflight_returns_true_for_running_runs() -> None:
    mgr = RunManager()
    thread_id, tenant_id = uuid4(), uuid4()
    run_id = uuid4()
    await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)

    flying = await mgr.has_inflight(thread_id, tenant_id=tenant_id)
    assert flying is True

    await mgr.set_status(run_id, RunStatus.SUCCESS)
    not_flying = await mgr.has_inflight(thread_id, tenant_id=tenant_id)
    assert not_flying is False


@pytest.mark.asyncio
async def test_has_inflight_tenant_isolation() -> None:
    mgr = RunManager()
    thread_id, tenant_a, tenant_b = uuid4(), uuid4(), uuid4()
    await mgr.create(run_id=uuid4(), thread_id=thread_id, tenant_id=tenant_a)

    a = await mgr.has_inflight(thread_id, tenant_id=tenant_a)
    b = await mgr.has_inflight(thread_id, tenant_id=tenant_b)
    assert a is True
    assert b is False


@pytest.mark.asyncio
async def test_cleanup_removes_run() -> None:
    mgr = RunManager()
    run_id, thread_id, tenant_id = uuid4(), uuid4(), uuid4()
    await mgr.create(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id)

    await mgr.cleanup(run_id, delay=0)
    assert mgr.get(run_id) is None
