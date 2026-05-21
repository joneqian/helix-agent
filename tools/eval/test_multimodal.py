"""Unit tests for the J.6 multimodal eval — Stream J.13a."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from multimodal import (  # noqa: E402
    AskImageCase,
    DispatchCase,
    _classify_path,
    evaluate_set,
    load_cases,
)


def test_classify_path_covers_four_branches() -> None:
    """Dispatch decision is a 4-way classifier."""
    assert _classify_path(vision_block_present=False, supports_vision=True) == "path_a"
    assert _classify_path(vision_block_present=True, supports_vision=False) == "path_b"
    assert _classify_path(vision_block_present=False, supports_vision=False) == "no_multimodal"
    assert _classify_path(vision_block_present=True, supports_vision=True) == "error"


def test_load_cases_parses_twelve() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "multimodal" / "m0_baseline.yaml")
    assert len(cases) == 12
    dispatch = [c for c in cases if isinstance(c, DispatchCase)]
    ask_image = [c for c in cases if isinstance(c, AskImageCase)]
    assert len(dispatch) == 6
    assert len(ask_image) == 6


@pytest.mark.asyncio
async def test_baseline_dataset_passes() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "multimodal" / "m0_baseline.yaml")
    report = await evaluate_set(cases)
    assert report.status == "PASS"
    assert report.aggregate_score["pass_rate_path_a"] >= 0.80
    assert report.aggregate_score["pass_rate_path_b"] >= 0.80


def test_load_cases_rejects_unknown_scenario(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("cases:\n  - id: bogus\n    scenario: typo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown scenario"):
        load_cases(bad)
