"""Unit tests for :class:`InMemoryQuotaService` — Stream C.5."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from control_plane.quota import InMemoryQuotaService
from helix_agent.persistence.quota import (
    InMemoryTenantQuotaStore,
    InMemoryTokenReservationStore,
)
from helix_agent.protocol import (
    CheckRequest,
    CommitRequest,
    QuotaDimension,
    ReservationState,
    ReserveRequest,
    TenantQuotaPatch,
)


def _tenant() -> UUID:
    return uuid4()


def _quota_store_with_qps(
    tenant_id: UUID, limit: int = 2, burst: int = 2, scope: dict[str, str] | None = None
) -> InMemoryTenantQuotaStore:
    """Build a store seeded with a single tenant QPS row."""
    store = InMemoryTenantQuotaStore()
    return store, TenantQuotaPatch(  # type: ignore[return-value]
        dimension=QuotaDimension.QPS,
        scope=scope or {},
        limit_value=limit,
        burst=burst,
    )


async def _seed(store: InMemoryTenantQuotaStore, tenant_id: UUID, patch: TenantQuotaPatch) -> None:
    await store.upsert(tenant_id=tenant_id, patch=patch, updated_by="test")


# ---------------------------------------------------------------------------
# check — single-tenant token bucket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_allows_within_burst() -> None:
    tenant = _tenant()
    quota_store, patch = _quota_store_with_qps(tenant, limit=10, burst=3)
    await _seed(quota_store, tenant, patch)
    svc = InMemoryQuotaService(
        quota_store=quota_store,
        reservation_store=InMemoryTokenReservationStore(),
    )

    for _ in range(3):
        result = await svc.check(CheckRequest(tenant_id=tenant, cost=1))
        assert result.allowed
    # 4th spend within the same millisecond exceeds burst.
    result = await svc.check(CheckRequest(tenant_id=tenant, cost=1))
    assert not result.allowed
    assert result.blocked_dimension is QuotaDimension.QPS
    assert result.retry_after_s is not None and result.retry_after_s >= 0


@pytest.mark.asyncio
async def test_check_with_no_quota_is_unlimited() -> None:
    tenant = _tenant()
    svc = InMemoryQuotaService(
        quota_store=InMemoryTenantQuotaStore(),
        reservation_store=InMemoryTokenReservationStore(),
    )
    result = await svc.check(CheckRequest(tenant_id=tenant, cost=1))
    assert result.allowed
    assert result.remaining == {}


@pytest.mark.asyncio
async def test_check_uses_default_qps_when_configured() -> None:
    tenant = _tenant()
    svc = InMemoryQuotaService(
        quota_store=InMemoryTenantQuotaStore(),
        reservation_store=InMemoryTokenReservationStore(),
        default_qps_limit=5,
        default_qps_burst=2,
    )
    # 2 within burst → ok, 3rd → denied.
    assert (await svc.check(CheckRequest(tenant_id=tenant, cost=1))).allowed
    assert (await svc.check(CheckRequest(tenant_id=tenant, cost=1))).allowed
    assert not (await svc.check(CheckRequest(tenant_id=tenant, cost=1))).allowed


@pytest.mark.asyncio
async def test_check_scope_matches_agent() -> None:
    tenant = _tenant()
    store = InMemoryTenantQuotaStore()
    # Agent-scoped row applies only when agent name matches.
    await _seed(
        store,
        tenant,
        TenantQuotaPatch(
            dimension=QuotaDimension.QPS,
            scope={"agent": "alpha"},
            limit_value=10,
            burst=1,
        ),
    )
    svc = InMemoryQuotaService(quota_store=store, reservation_store=InMemoryTokenReservationStore())

    # Different agent → no dimension applies → unlimited.
    result_beta = await svc.check(CheckRequest(tenant_id=tenant, agent="beta", cost=1))
    assert result_beta.allowed
    assert result_beta.remaining == {}

    # alpha agent → burst=1, second spend denied.
    assert (await svc.check(CheckRequest(tenant_id=tenant, agent="alpha", cost=1))).allowed
    denied = await svc.check(CheckRequest(tenant_id=tenant, agent="alpha", cost=1))
    assert not denied.allowed


# ---------------------------------------------------------------------------
# reserve / commit / release — token reservation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reserve_grants_when_no_budget_configured() -> None:
    tenant = _tenant()
    svc = InMemoryQuotaService(
        quota_store=InMemoryTenantQuotaStore(),
        reservation_store=InMemoryTokenReservationStore(),
    )
    result = await svc.reserve_tokens(
        ReserveRequest(
            tenant_id=tenant,
            agent="alpha",
            thread_id=uuid4(),
            estimated_tokens=1000,
        )
    )
    assert result.granted
    assert result.reservation_id is not None
    assert result.reason == "ok"


@pytest.mark.asyncio
async def test_reserve_denies_when_over_monthly_budget() -> None:
    tenant = _tenant()
    reservations = InMemoryTokenReservationStore()
    # Configure a small budget so the reservation request overshoots.
    month = datetime.now(tz=UTC).date().replace(day=1)
    await reservations.set_budget_total_for_test(tenant_id=tenant, month=month, budget_total=500)
    svc = InMemoryQuotaService(
        quota_store=InMemoryTenantQuotaStore(),
        reservation_store=reservations,
    )
    result = await svc.reserve_tokens(
        ReserveRequest(
            tenant_id=tenant,
            agent="alpha",
            thread_id=uuid4(),
            estimated_tokens=1000,
        )
    )
    assert not result.granted
    assert result.reservation_id is None
    assert result.reason == "over_budget"


@pytest.mark.asyncio
async def test_commit_marks_committed_and_updates_ledger() -> None:
    tenant = _tenant()
    reservations = InMemoryTokenReservationStore()
    svc = InMemoryQuotaService(
        quota_store=InMemoryTenantQuotaStore(),
        reservation_store=reservations,
    )
    reserve = await svc.reserve_tokens(
        ReserveRequest(
            tenant_id=tenant,
            agent="alpha",
            thread_id=uuid4(),
            estimated_tokens=400,
        )
    )
    assert reserve.granted and reserve.reservation_id is not None

    await svc.commit_tokens(
        CommitRequest(
            reservation_id=reserve.reservation_id,
            tenant_id=tenant,
            actual_tokens=350,
        )
    )

    row = await reservations.get(reservation_id=reserve.reservation_id, tenant_id=tenant)
    assert row is not None
    assert row.state is ReservationState.COMMITTED
    assert row.actual == 350

    month = datetime.now(tz=UTC).date().replace(day=1)
    budget = await reservations.get_budget(tenant_id=tenant, month=month)
    assert budget is not None
    assert budget.used_total == 350
    assert budget.reserved_total == 0  # refunded after commit


@pytest.mark.asyncio
async def test_release_refunds_reserved_total() -> None:
    tenant = _tenant()
    reservations = InMemoryTokenReservationStore()
    svc = InMemoryQuotaService(
        quota_store=InMemoryTenantQuotaStore(),
        reservation_store=reservations,
    )
    reserve = await svc.reserve_tokens(
        ReserveRequest(
            tenant_id=tenant,
            agent="alpha",
            thread_id=uuid4(),
            estimated_tokens=200,
        )
    )
    assert reserve.reservation_id is not None
    await svc.release_tokens(reserve.reservation_id, tenant_id=tenant)
    row = await reservations.get(reservation_id=reserve.reservation_id, tenant_id=tenant)
    assert row is not None
    assert row.state is ReservationState.RELEASED

    month = datetime.now(tz=UTC).date().replace(day=1)
    budget = await reservations.get_budget(tenant_id=tenant, month=month)
    assert budget is not None
    assert budget.used_total == 0
    assert budget.reserved_total == 0


# ---------------------------------------------------------------------------
# reservation reaper integration (via store)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_expired_finds_stale_reservations() -> None:
    """``list_expired`` underpins the reaper — verify it surfaces old rows."""
    from datetime import timedelta

    tenant = _tenant()
    store = InMemoryTokenReservationStore()
    # Seed a reservation, then back-date it by hand.
    row = await store.reserve(
        tenant_id=tenant,
        agent_name="alpha",
        thread_id=uuid4(),
        estimated=100,
    )
    # Replace with an old reserved_at so the cutoff catches it.
    old = row.model_copy(update={"reserved_at": row.reserved_at - timedelta(hours=1)})
    # Direct dict poke is reasonable here — we're testing the listing
    # primitive that production uses, the model_copy is the test
    # harness mechanism for "this row is stale".
    store._reservations[row.id] = old  # type: ignore[attr-defined]

    expired = await store.list_expired(max_age_seconds=600)  # 10min
    assert len(expired) == 1
    assert expired[0].id == row.id


@pytest.mark.asyncio
async def test_reaper_runs_once_releases_stale_rows() -> None:
    from datetime import timedelta

    from control_plane.quota import ReservationReaper

    tenant = _tenant()
    store = InMemoryTokenReservationStore()
    row = await store.reserve(
        tenant_id=tenant,
        agent_name="alpha",
        thread_id=uuid4(),
        estimated=100,
    )
    store._reservations[row.id] = row.model_copy(  # type: ignore[attr-defined]
        update={"reserved_at": row.reserved_at - timedelta(hours=1)}
    )

    reaper = ReservationReaper(
        reservation_store=store,
        max_age_s=600,
        interval_s=60,
    )
    released = await reaper.run_once()
    assert released == 1

    final = await store.get(reservation_id=row.id, tenant_id=tenant)
    assert final is not None
    assert final.state is ReservationState.EXPIRED
