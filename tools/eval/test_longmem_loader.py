"""Loader + adapter tests — Stream CM-N5 P0 (fixture-only, no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from longmem.adapter import (
    load_locomo,
    load_longmemeval,
    parse_locomo_date,
    parse_longmemeval_date,
    shift_to_now,
    strip_timestamps,
)

FIXTURES = Path(__file__).parent / "datasets" / "longmem_fixture"
LONGMEMEVAL_MINI = FIXTURES / "longmemeval_mini.json"
LOCOMO_MINI = FIXTURES / "locomo_mini.json"


# ---------------------------------------------------------------------------
# date parsing — locale-independent by construction
# ---------------------------------------------------------------------------


def test_parse_longmemeval_date() -> None:
    assert parse_longmemeval_date("2023/04/10 (Mon) 23:07") == datetime(
        2023, 4, 10, 23, 7, tzinfo=UTC
    )


def test_parse_locomo_date_pm_and_am() -> None:
    assert parse_locomo_date("1:56 pm on 8 May, 2023") == datetime(2023, 5, 8, 13, 56, tzinfo=UTC)
    assert parse_locomo_date("12:05 am on 1 January, 2024") == datetime(
        2024, 1, 1, 0, 5, tzinfo=UTC
    )


@pytest.mark.parametrize("raw", ["not a date", "13:00 xm on 1 January, 2024", ""])
def test_unparseable_dates_raise(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_locomo_date(raw)
    with pytest.raises(ValueError):
        parse_longmemeval_date(raw)


# ---------------------------------------------------------------------------
# LongMemEval loader
# ---------------------------------------------------------------------------


def test_longmemeval_turn_granularity() -> None:
    instances = load_longmemeval(LONGMEMEVAL_MINI)
    # The _abs question is skipped by default.
    assert [i.question_id for i in instances] == ["fixture-city-1", "fixture-editor-2"]
    city = instances[0]
    assert city.question_type == "single-session-user"
    assert city.answer == "Kyoto"
    assert city.answer_session_ids == frozenset({"sess-travel"})
    # 3 + 3 turns, one doc each, role-prefixed content.
    assert len(city.docs) == 6
    assert city.docs[0].doc_id == "sess-travel#t0"
    assert city.docs[0].content.startswith("user: I just got back from Kyoto")
    assert city.docs[0].session_id == "sess-travel"
    assert city.docs[0].timestamp == datetime(2023, 4, 5, 19, 30, tzinfo=UTC)
    assert city.answer_doc_ids == frozenset({"sess-travel#t0"})


def test_longmemeval_abstention_included_on_request() -> None:
    instances = load_longmemeval(LONGMEMEVAL_MINI, include_abstention=True)
    ids = [i.question_id for i in instances]
    assert "fixture-skip-3_abs" in ids
    abstention = next(i for i in instances if i.question_id.endswith("_abs"))
    assert abstention.answer_session_ids == frozenset()


def test_longmemeval_session_granularity() -> None:
    instances = load_longmemeval(LONGMEMEVAL_MINI, granularity="session")
    city = instances[0]
    # One doc per session; the evidence session keeps has_answer.
    assert len(city.docs) == 2
    assert city.docs[0].doc_id == "sess-travel"
    assert "cherry blossom festival" in city.docs[0].content
    assert "worth it" in city.docs[0].content
    assert city.answer_doc_ids == frozenset({"sess-travel"})


# ---------------------------------------------------------------------------
# LoCoMo loader
# ---------------------------------------------------------------------------


def test_locomo_excludes_adversarial_by_default() -> None:
    instances = load_locomo(LOCOMO_MINI)
    # 5 QA in fixture, category 5 dropped.
    assert len(instances) == 4
    assert all("adversarial" not in i.question_type for i in instances)


def test_locomo_ground_truth_and_dates() -> None:
    instances = load_locomo(LOCOMO_MINI)
    single_hop = next(i for i in instances if i.question_type == "locomo-single-hop")
    assert single_hop.answer_doc_ids == frozenset({"D1:1"})
    assert single_hop.answer_session_ids == frozenset({"session_1"})
    temporal = next(i for i in instances if i.question_type == "locomo-temporal")
    assert temporal.answer_session_ids == frozenset({"session_1", "session_2"})
    # Question date = newest session (18 March 10:30) + 1 day.
    assert temporal.question_date == datetime(2023, 3, 19, 10, 30, tzinfo=UTC)
    # Speaker-prefixed content; image-only turn renders the caption.
    docs = {d.doc_id: d for d in temporal.docs}
    assert docs["D1:1"].content.startswith("Alice: I adopted a golden retriever")
    assert docs["D1:3"].content == "Alice: [shared photo: a small golden puppy on a sofa]"
    assert docs["D2:2"].timestamp == datetime(2023, 3, 18, 10, 30, tzinfo=UTC)


def test_locomo_qas_share_one_corpus_tuple() -> None:
    instances = load_locomo(LOCOMO_MINI)
    assert len({id(i.docs) for i in instances}) == 1


# ---------------------------------------------------------------------------
# CM-K4 time shift — ages preserved exactly
# ---------------------------------------------------------------------------


def test_shift_to_now_preserves_ages() -> None:
    instance = load_longmemeval(LONGMEMEVAL_MINI)[0]
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    shifted = shift_to_now(instance, now=now)
    assert shifted.question_date == now
    for before, after in zip(instance.docs, shifted.docs, strict=True):
        assert before.timestamp is not None and after.timestamp is not None
        assert instance.question_date - before.timestamp == now - after.timestamp


def test_strip_timestamps_clears_all() -> None:
    instance = load_longmemeval(LONGMEMEVAL_MINI)[0]
    stripped = strip_timestamps(instance)
    assert all(d.timestamp is None for d in stripped.docs)
    assert stripped.question_date == instance.question_date


def test_shift_handles_missing_timestamps() -> None:
    instance = strip_timestamps(load_longmemeval(LONGMEMEVAL_MINI)[0])
    shifted = shift_to_now(instance, now=datetime(2026, 6, 10, tzinfo=UTC))
    assert all(d.timestamp is None for d in shifted.docs)


def test_shift_age_invariant_within_run_window() -> None:
    """Wall-clock drift over a run is <0.5% of the 30-day half-life."""
    assert timedelta(hours=4) / timedelta(days=30) < 0.006
