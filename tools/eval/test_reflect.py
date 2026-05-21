"""Unit tests for the J.2 reflect eval — Stream J.13a."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from reflect import (  # noqa: E402
    ReflectCase,
    evaluate_set,
    load_cases,
)


def test_load_cases_parses_sixteen() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "reflect" / "m0_baseline.yaml")
    assert len(cases) == 16


@pytest.mark.asyncio
async def test_baseline_dataset_passes() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "reflect" / "m0_baseline.yaml")
    report = await evaluate_set(cases)
    assert report.status == "PASS"
    # 7 of 8 buggy cases correctly say revise; the malformed one
    # safely accepts.
    assert report.aggregate_score["correction_rate"] >= 0.75
    assert report.aggregate_score["false_positive_rate"] <= 0.20


@pytest.mark.asyncio
async def test_high_false_positive_marks_fail() -> None:
    """A correct trajectory whose reply forces ``revise`` trips false_positive."""
    case = ReflectCase(
        case_id="false-alarm",
        kind="correct",
        reflect_llm_reply='{"verdict": "revise", "critique": "spurious"}',
        expected_verdict="revise",  # the eval still treats this as "correctly parsed"
    )
    # ``passed`` per-case is True (parser extracted the right verdict),
    # but false_positive_rate counts revise-on-correct.
    report = await evaluate_set([case])
    assert report.aggregate_score["false_positive_rate"] == 1.0
    assert report.status == "FAIL"


@pytest.mark.asyncio
async def test_low_correction_rate_marks_fail() -> None:
    """A buggy trajectory whose malformed reply falls back to ``accept``."""
    case = ReflectCase(
        case_id="missed-bug",
        kind="buggy",
        reflect_llm_reply="no JSON at all",
        expected_verdict="accept",  # parser fail-safes to accept
    )
    report = await evaluate_set([case])
    assert report.aggregate_score["correction_rate"] == 0.0
    assert report.status == "FAIL"
