"""Unit tests for the J.1 plan_execute eval — Stream J.13a."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from plan_execute import (  # noqa: E402
    PlanCase,
    evaluate_set,
    load_cases,
)


def test_load_cases_parses_twenty() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "plan_execute" / "m0_baseline.yaml")
    assert len(cases) == 20


@pytest.mark.asyncio
async def test_baseline_dataset_passes() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "plan_execute" / "m0_baseline.yaml")
    report = await evaluate_set(cases)
    assert report.status == "PASS"
    assert report.aggregate_score["pass_rate"] >= 0.80
    assert report.aggregate_score["judge_mean"] >= 4.0


@pytest.mark.asyncio
async def test_missing_goal_keyword_marks_case_failed() -> None:
    """A case whose parsed plan misses a required keyword fails structurally."""
    case = PlanCase(
        case_id="missing-kw",
        task="Compute the answer",
        llm_reply='{"goal": "Unrelated goal", "steps": ["a", "b"]}',
        expected_goal_keywords=("Compute",),
        min_steps=1,
        mock_judge_score=5,
    )
    report = await evaluate_set([case])
    assert report.status == "FAIL"
    assert report.aggregate_score["pass_rate"] == 0.0


@pytest.mark.asyncio
async def test_low_judge_mean_marks_set_failed() -> None:
    """Structural pass-rate alone doesn't earn PASS — judge_mean must also clear 4.0."""
    case = PlanCase(
        case_id="low-judge",
        task="Greet",
        llm_reply='{"goal": "Greet user", "steps": ["say hi"]}',
        expected_goal_keywords=("Greet",),
        min_steps=1,
        mock_judge_score=2,
    )
    report = await evaluate_set([case])
    assert report.aggregate_score["pass_rate"] == 1.0
    assert report.aggregate_score["judge_mean"] == 2.0
    assert report.status == "FAIL"
