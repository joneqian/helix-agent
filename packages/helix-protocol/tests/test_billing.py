"""Validation + pricing-helper tests for ``protocol/billing.py`` — Stream Y-3."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from helix_agent.protocol import (
    ModelRateCardPatch,
    ModelRateCardRecord,
    ModelRateCardUpsert,
    apply_markup,
)
from helix_agent.protocol.tenant_config import TenantPlan

_FROM = datetime(2026, 6, 1, tzinfo=UTC)


def _upsert(**over: object) -> ModelRateCardUpsert:
    kwargs: dict[str, object] = {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "input_token_micros": 15,
        "output_token_micros": 75,
        "markup_bps": 2000,
        "effective_from": _FROM,
    }
    kwargs.update(over)
    return ModelRateCardUpsert(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# apply_markup — integer math only
# ---------------------------------------------------------------------------


def test_apply_markup_twenty_percent() -> None:
    assert apply_markup(1_000_000, 2000) == 1_200_000


def test_apply_markup_zero() -> None:
    assert apply_markup(1_000_000, 0) == 1_000_000


def test_apply_markup_floor_division() -> None:
    # 7 * 2500 // 10000 = 17500 // 10000 = 1 (floor), so 7 + 1 = 8.
    assert apply_markup(7, 2500) == 8


# ---------------------------------------------------------------------------
# Upsert validation
# ---------------------------------------------------------------------------


def test_valid_upsert() -> None:
    row = _upsert()
    assert row.provider == "anthropic"
    assert row.cache_creation_token_micros == 0


def test_deprecated_model_allowed() -> None:
    # gpt-4o is deprecated in MODEL_CATALOG but must stay priceable.
    row = _upsert(provider="openai", model="gpt-4o")
    assert row.model == "gpt-4o"


def test_unknown_provider_rejected() -> None:
    with pytest.raises(ValidationError):
        _upsert(provider="nope")


def test_unknown_model_rejected() -> None:
    with pytest.raises(ValidationError):
        _upsert(model="not-a-model")


def test_negative_micros_rejected() -> None:
    with pytest.raises(ValidationError):
        _upsert(input_token_micros=-1)


def test_negative_markup_rejected() -> None:
    with pytest.raises(ValidationError):
        _upsert(markup_bps=-1)


def test_effective_until_must_exceed_from() -> None:
    with pytest.raises(ValidationError):
        _upsert(effective_until=_FROM)
    with pytest.raises(ValidationError):
        _upsert(effective_until=_FROM - timedelta(days=1))


def test_effective_until_open_ended_ok() -> None:
    row = _upsert(effective_until=None)
    assert row.effective_until is None


def test_plan_tier_override() -> None:
    row = _upsert(plan_tier=TenantPlan.ENTERPRISE)
    assert row.plan_tier is TenantPlan.ENTERPRISE


# ---------------------------------------------------------------------------
# Record validation (read model — same cross-field rules)
# ---------------------------------------------------------------------------


def test_record_rejects_bad_window() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ModelRateCardRecord(
            id="00000000-0000-0000-0000-000000000001",  # type: ignore[arg-type]
            provider="anthropic",
            model="claude-opus-4-8",
            input_token_micros=1,
            output_token_micros=1,
            cache_creation_token_micros=0,
            cache_read_token_micros=0,
            markup_bps=0,
            effective_from=_FROM,
            effective_until=_FROM,
            created_at=now,
            updated_at=now,
        )


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------


def test_patch_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        ModelRateCardPatch(input_token_micros=-1)


def test_patch_partial_ok() -> None:
    patch = ModelRateCardPatch(markup_bps=3000)
    assert patch.markup_bps == 3000
    assert patch.input_token_micros is None
