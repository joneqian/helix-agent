"""J.2 reflect eval — Stream J.13a (M0 baseline).

Drives :func:`orchestrator.graph_builder.reflect._parse_reflection`
(a pure parser) against a curated dataset of ``(trajectory_kind,
reflect_llm_reply)`` pairs. Two metric axes per Mini-ADR J-37:

* ``correction_rate`` — fraction of *buggy*-trajectory cases where the
  parser returns ``verdict="revise"``. The parser fails safe to
  ``accept`` on a malformed reply (Mini-ADR J-5a), so a buggy case with
  a malformed scripted reply correctly *misses* the bug — exposing the
  fail-safe in the baseline rather than papering over it.
* ``false_positive_rate`` — fraction of *correct*-trajectory cases
  where the parser returns ``revise`` anyway. Conservative threshold:
  ≤ 0.20 (rare false alarms are tolerable; common ones aren't).

The eval tests parser semantics; the *quality* of the reflect LLM's
judgement against a real model lives in J.13b (online sampling).
"""

from __future__ import annotations

import sys as _sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from pathlib import Path as _Path
from typing import Any, Literal, cast

import yaml

# ``_parse_reflection`` is intentionally private (an internal of the
# reflect node) — but this eval *is* the production-grade regression
# gate for its semantics, so the eval owns the right to depend on it.
from orchestrator.graph_builder.reflect import _parse_reflection

_EVAL_DIR = _Path(__file__).resolve().parent
if str(_EVAL_DIR) not in _sys.path:
    _sys.path.insert(0, str(_EVAL_DIR))

from _capability import (  # type: ignore[import-not-found]  # noqa: E402
    CapabilityCaseResult,
    CapabilityReport,
    JudgeCompletionFn,
)

CAPABILITY = "J.2_reflect"
METRIC_TYPE = "pass-rate"
THRESHOLD = {"correction_rate": 0.75, "false_positive_rate": 0.20}


@dataclass(frozen=True)
class ReflectCase:
    """One reflect parser case.

    ``kind`` records whether the underlying trajectory is buggy or
    correct so we can split the metric in two. The parser sees only
    ``reflect_llm_reply`` and ``expected_verdict``; ``kind`` exists for
    aggregation.
    """

    case_id: str
    kind: Literal["buggy", "correct"]
    reflect_llm_reply: str
    expected_verdict: Literal["accept", "revise"]


async def _run_case(case: ReflectCase) -> CapabilityCaseResult:
    reflection, _ = _parse_reflection(case.reflect_llm_reply, plan=None)
    verdict = reflection.verdict
    passed = verdict == case.expected_verdict
    notes = () if passed else (f"expected_verdict={case.expected_verdict!r} got={verdict!r}",)
    return CapabilityCaseResult(
        case_id=case.case_id,
        passed=passed,
        scores={"verdict_revise": 1.0 if verdict == "revise" else 0.0},
        notes=notes,
    )


async def evaluate_set(
    cases: Sequence[ReflectCase],
    *,
    judge: JudgeCompletionFn | None = None,
    rerun_count: int = 3,
) -> CapabilityReport:
    """Run every case through the reflect parser; split metrics by kind."""
    per_case: list[CapabilityCaseResult] = []
    for case in cases:
        per_case.append(await _run_case(case))

    sample = len(per_case)
    buggy_indices = [i for i, c in enumerate(cases) if c.kind == "buggy"]
    correct_indices = [i for i, c in enumerate(cases) if c.kind == "correct"]
    correction_rate = (
        sum(per_case[i].scores["verdict_revise"] for i in buggy_indices) / len(buggy_indices)
        if buggy_indices
        else 0.0
    )
    false_positive_rate = (
        sum(per_case[i].scores["verdict_revise"] for i in correct_indices) / len(correct_indices)
        if correct_indices
        else 0.0
    )

    meets_correction = correction_rate >= THRESHOLD["correction_rate"]
    meets_fp = false_positive_rate <= THRESHOLD["false_positive_rate"]
    status = "PASS" if meets_correction and meets_fp else "FAIL"
    return CapabilityReport(
        capability=CAPABILITY,
        metric_type=METRIC_TYPE,
        sample_size=sample,
        threshold=THRESHOLD,
        aggregate_score={
            "correction_rate": correction_rate,
            "false_positive_rate": false_positive_rate,
        },
        status=cast(Any, status),
        per_case=tuple(per_case),
    )


def load_cases(path: Path) -> list[ReflectCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[ReflectCase] = []
    for entry in raw.get("cases", []):
        out.append(_parse_case(entry))
    return out


def _parse_case(entry: dict[str, Any]) -> ReflectCase:
    return ReflectCase(
        case_id=str(entry["id"]),
        kind=cast(Any, entry["kind"]),
        reflect_llm_reply=str(entry["reflect_llm_reply"]),
        expected_verdict=cast(Any, entry["expected_verdict"]),
    )


__all__ = [
    "CAPABILITY",
    "METRIC_TYPE",
    "THRESHOLD",
    "ReflectCase",
    "evaluate_set",
    "load_cases",
]
