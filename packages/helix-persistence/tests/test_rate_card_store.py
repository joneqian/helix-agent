"""Unit tests for the in-memory model rate-card store — Stream Y (Y-3).

Covers CRUD + conflict + the ``resolve`` most-specific/temporal selection rules.
The SQL store shares the pure ``_resolve`` helper, so resolution semantics are
exercised here against the in-memory impl; SQL CRUD/RLS lives in the integration
suite (no real-PG harness gap for resolution — it is pure logic).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from helix_agent.persistence.billing import (
    InMemoryModelRateCardStore,
    ModelRateCardConflictError,
    ModelRateCardNotFoundError,
)
from helix_agent.protocol import (
    ModelRateCardPatch,
    ModelRateCardRecord,
    ModelRateCardUpsert,
    TenantPlan,
)

_JAN = datetime(2026, 1, 1, tzinfo=UTC)
_FEB = datetime(2026, 2, 1, tzinfo=UTC)
_MAR = datetime(2026, 3, 1, tzinfo=UTC)


async def _make(store: InMemoryModelRateCardStore, **over: Any) -> ModelRateCardRecord:
    kwargs: dict[str, Any] = {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "input_token_micros": 15,
        "output_token_micros": 75,
        "markup_bps": 2000,
        "effective_from": _JAN,
    }
    kwargs.update(over)
    return await store.create(upsert=ModelRateCardUpsert(**kwargs), actor_id="sysadmin")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_get() -> None:
    store = InMemoryModelRateCardStore()
    rec = await _make(store)
    assert rec.tenant_id is None
    fetched = await store.get(rec.id)
    assert fetched is not None
    assert fetched.input_token_micros == 15
    assert fetched.markup_bps == 2000


@pytest.mark.asyncio
async def test_get_missing_returns_none() -> None:
    store = InMemoryModelRateCardStore()
    assert await store.get(uuid4()) is None


@pytest.mark.asyncio
async def test_create_duplicate_conflicts() -> None:
    store = InMemoryModelRateCardStore()
    await _make(store)
    with pytest.raises(ModelRateCardConflictError):
        await _make(store)


@pytest.mark.asyncio
async def test_create_same_key_different_tier_ok() -> None:
    store = InMemoryModelRateCardStore()
    await _make(store)
    # Different plan_tier => different natural key, no conflict.
    rec = await _make(store, plan_tier=TenantPlan.ENTERPRISE)
    assert rec.plan_tier is TenantPlan.ENTERPRISE


@pytest.mark.asyncio
async def test_create_same_key_different_effective_from_ok() -> None:
    store = InMemoryModelRateCardStore()
    await _make(store, effective_until=_FEB)
    rec = await _make(store, effective_from=_FEB)
    assert rec.effective_from == _FEB


@pytest.mark.asyncio
async def test_patch_updates_price() -> None:
    store = InMemoryModelRateCardStore()
    rec = await _make(store)
    updated = await store.patch(
        rate_card_id=rec.id, patch=ModelRateCardPatch(input_token_micros=99, markup_bps=3000)
    )
    assert updated.input_token_micros == 99
    assert updated.markup_bps == 3000
    # output untouched
    assert updated.output_token_micros == 75


@pytest.mark.asyncio
async def test_patch_missing_raises() -> None:
    store = InMemoryModelRateCardStore()
    with pytest.raises(ModelRateCardNotFoundError):
        await store.patch(rate_card_id=uuid4(), patch=ModelRateCardPatch(markup_bps=1))


@pytest.mark.asyncio
async def test_patch_bad_window_rejected() -> None:
    store = InMemoryModelRateCardStore()
    rec = await _make(store, effective_from=_FEB)
    # effective_until <= effective_from must fail re-validation.
    with pytest.raises(ValueError, match="effective_until"):
        await store.patch(rate_card_id=rec.id, patch=ModelRateCardPatch(effective_until=_JAN))


@pytest.mark.asyncio
async def test_delete() -> None:
    store = InMemoryModelRateCardStore()
    rec = await _make(store)
    await store.delete(rec.id)
    assert await store.get(rec.id) is None


@pytest.mark.asyncio
async def test_delete_missing_raises() -> None:
    store = InMemoryModelRateCardStore()
    with pytest.raises(ModelRateCardNotFoundError):
        await store.delete(uuid4())


# ---------------------------------------------------------------------------
# list filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_filters_provider_model() -> None:
    store = InMemoryModelRateCardStore()
    await _make(store)
    await _make(store, provider="openai", model="gpt-5.5")
    assert len(await store.list()) == 2
    only_oai = await store.list(provider="openai")
    assert len(only_oai) == 1
    assert only_oai[0].provider == "openai"
    only_model = await store.list(model="claude-opus-4-8")
    assert len(only_model) == 1


@pytest.mark.asyncio
async def test_list_excludes_expired_by_default() -> None:
    store = InMemoryModelRateCardStore()
    past = datetime.now(UTC) - timedelta(days=2)
    await _make(store, effective_from=past - timedelta(days=1), effective_until=past)
    await _make(store, effective_from=past, effective_until=None)
    active = await store.list()
    assert len(active) == 1
    all_rows = await store.list(include_expired=True)
    assert len(all_rows) == 2


# ---------------------------------------------------------------------------
# resolve — most-specific + temporal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_tier_beats_generic() -> None:
    store = InMemoryModelRateCardStore()
    generic = await _make(store, plan_tier=None)
    tier = await _make(store, plan_tier=TenantPlan.ENTERPRISE)
    hit = await store.resolve(
        provider="anthropic", model="claude-opus-4-8", plan_tier=TenantPlan.ENTERPRISE, at=_FEB
    )
    assert hit is not None and hit.id == tier.id
    # A tier with no specific row falls back to generic.
    hit2 = await store.resolve(
        provider="anthropic", model="claude-opus-4-8", plan_tier=TenantPlan.PRO, at=_FEB
    )
    assert hit2 is not None and hit2.id == generic.id


@pytest.mark.asyncio
async def test_resolve_no_generic_fallback_when_only_tier_specific() -> None:
    """A NULL-tier (free) caller gets no rate when only a tier-specific row
    exists — an enterprise row is NOT a generic fallback."""
    store = InMemoryModelRateCardStore()
    await _make(store, plan_tier=TenantPlan.ENTERPRISE)  # no generic row
    hit = await store.resolve(
        provider="anthropic", model="claude-opus-4-8", plan_tier=None, at=_FEB
    )
    assert hit is None


@pytest.mark.asyncio
async def test_resolve_temporal_window_excludes_expired() -> None:
    store = InMemoryModelRateCardStore()
    # Window [JAN, FEB) — at FEB it is no longer in effect.
    await _make(store, effective_from=_JAN, effective_until=_FEB)
    assert (
        await store.resolve(provider="anthropic", model="claude-opus-4-8", plan_tier=None, at=_FEB)
        is None
    )
    # at JAN it is in effect (lower bound inclusive).
    assert (
        await store.resolve(provider="anthropic", model="claude-opus-4-8", plan_tier=None, at=_JAN)
        is not None
    )


@pytest.mark.asyncio
async def test_resolve_open_ended_included() -> None:
    store = InMemoryModelRateCardStore()
    await _make(store, effective_from=_JAN, effective_until=None)
    far_future = datetime(2099, 1, 1, tzinfo=UTC)
    hit = await store.resolve(
        provider="anthropic", model="claude-opus-4-8", plan_tier=None, at=far_future
    )
    assert hit is not None


@pytest.mark.asyncio
async def test_resolve_latest_effective_from_wins() -> None:
    store = InMemoryModelRateCardStore()
    await _make(store, effective_from=_JAN, effective_until=None, input_token_micros=10)
    newer = await _make(store, effective_from=_FEB, effective_until=None, input_token_micros=20)
    # At MAR both windows are open & contain MAR; the later effective_from wins.
    hit = await store.resolve(
        provider="anthropic", model="claude-opus-4-8", plan_tier=None, at=_MAR
    )
    assert hit is not None and hit.id == newer.id
    assert hit.input_token_micros == 20


@pytest.mark.asyncio
async def test_resolve_no_match_returns_none() -> None:
    store = InMemoryModelRateCardStore()
    await _make(store)
    assert await store.resolve(provider="openai", model="gpt-5.5", plan_tier=None, at=_FEB) is None
