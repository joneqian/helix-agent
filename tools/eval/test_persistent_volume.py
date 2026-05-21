"""Unit tests for the J.15 persistent volume eval — Stream J.13a."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from persistent_volume import (  # noqa: E402
    WorkspaceCase,
    evaluate_set,
    load_cases,
)


def test_load_cases_parses_eleven() -> None:
    """6 lifecycle + 2 listing + 3 quota = 11 cases."""
    cases = load_cases(_EVAL_DIR / "datasets" / "persistent_volume" / "m0_baseline.yaml")
    assert len(cases) == 11


@pytest.mark.asyncio
async def test_baseline_dataset_passes() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "persistent_volume" / "m0_baseline.yaml")
    report = await evaluate_set(cases)
    assert report.status == "PASS"
    assert report.aggregate_score["pass_rate"] >= 0.90


@pytest.mark.asyncio
async def test_mark_archived_without_soft_delete_is_state_machine_error() -> None:
    """The lifecycle guard rejects archive on an active workspace."""
    case = WorkspaceCase(
        case_id="invariant",
        setup=({"action": "resolve"},),
        test_action="mark_archived",
        expected_outcome="error_state_invariant",
    )
    report = await evaluate_set([case])
    assert report.status == "PASS"
    assert report.per_case[0].passed


@pytest.mark.asyncio
async def test_quota_rejects_over_limit() -> None:
    case = WorkspaceCase(
        case_id="over-limit",
        setup=({"action": "resolve"},),
        test_action="quota_check",
        test_args={
            "override_size_bytes": 2 * 1024**3,
            "override_size_limit_bytes": 1 * 1024**3,
        },
        expected_outcome="error_quota_exceeded",
    )
    report = await evaluate_set([case])
    assert report.per_case[0].passed


@pytest.mark.asyncio
async def test_unexpected_outcome_is_marked_failed() -> None:
    """A case whose expectation contradicts reality fails loudly."""
    case = WorkspaceCase(
        case_id="contradictory",
        setup=({"action": "resolve"},),
        test_action="mark_archived",
        expected_outcome="ok",  # actually raises ValueError → state_invariant
    )
    report = await evaluate_set([case])
    assert report.status == "FAIL"
    assert not report.per_case[0].passed
