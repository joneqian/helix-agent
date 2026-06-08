"""Unit tests for the SE-9 self-evolution benchmark — Stream SE (SE-A14)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from self_evolution import (  # type: ignore[import-not-found]  # noqa: E402
    SelfEvolutionEvalCase,
    evaluate_set,
    load_cases,
)

_DATASET = _EVAL_DIR / "datasets" / "self_evolution" / "m0_baseline.yaml"


def test_load_cases_parses_ten() -> None:
    cases = load_cases(_DATASET)
    assert len(cases) == 10


@pytest.mark.asyncio
async def test_baseline_dataset_passes() -> None:
    cases = load_cases(_DATASET)
    report = await evaluate_set(cases)
    assert report.status == "PASS"
    assert report.aggregate_score["pass_rate"] == 1.0


@pytest.mark.asyncio
async def test_unknown_scenario_marks_case_failed() -> None:
    case = SelfEvolutionEvalCase(case_id="bogus", scenario="not_a_scenario")
    report = await evaluate_set([case])
    assert report.status == "FAIL"
    assert not report.per_case[0].passed
    assert any("unknown scenario" in n for n in report.per_case[0].notes)
