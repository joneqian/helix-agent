"""J.6 multimodal eval — Stream J.13a (M0 baseline).

Two scenarios, both fully deterministic so the baseline runs in CI:

* ``dispatch`` — the build-time decision in
  :func:`orchestrator.agent_factory.build_agent` that picks Path A
  (the main model accepts images via content blocks) vs Path B
  (a separate VL model behind the ``ask_image`` tool). Mirrors the
  pure if-else in ``agent_factory.py`` lines 167-217.
* ``ask_image`` — Path B keyword recall. Drives
  :meth:`orchestrator.tools.vision.AskImageTool.call` against a mock
  ``vl_caller`` that returns a scripted :class:`AIMessage`; the eval
  checks that the response carries the expected keyword.

Per Mini-ADR J-37, J.6 metric is ``pass-rate`` split by path with
threshold ≥ 0.80 each (§ 18.3). Real Path A keyword recall against a
real multimodal model is J.13b territory (online sampling); the M0
baseline here is the dispatch regression gate plus a Path B execution
gate.
"""

from __future__ import annotations

import sys as _sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from pathlib import Path as _Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import yaml
from langchain_core.messages import AIMessage, BaseMessage

from orchestrator.multimodal import ImageResolver, ResolvedImage
from orchestrator.tools.registry import ToolContext, ToolSpec
from orchestrator.tools.vision import AskImageTool

_EVAL_DIR = _Path(__file__).resolve().parent
if str(_EVAL_DIR) not in _sys.path:
    _sys.path.insert(0, str(_EVAL_DIR))

from _capability import (  # type: ignore[import-not-found]  # noqa: E402
    CapabilityCaseResult,
    CapabilityReport,
    JudgeCompletionFn,
)

CAPABILITY = "J.6_multimodal"
METRIC_TYPE = "pass-rate"
THRESHOLD = {"pass_rate_path_a": 0.80, "pass_rate_path_b": 0.80}


DispatchPath = Literal["path_a", "path_b", "no_multimodal", "error"]


def _classify_path(*, vision_block_present: bool, supports_vision: bool) -> DispatchPath:
    """Mirror the J.6 dispatch decision in ``agent_factory.build_agent``.

    Matches lines 167-175 + 188-217 of ``agent_factory.py``: the two
    boolean inputs fully determine the build-time path. Pure function so
    the eval is deterministic.
    """
    if vision_block_present and supports_vision:
        return "error"
    if vision_block_present:
        return "path_b"
    if supports_vision:
        return "path_a"
    return "no_multimodal"


@dataclass(frozen=True)
class DispatchCase:
    """One dispatch-decision case."""

    case_id: str
    vision_block_present: bool
    supports_vision: bool
    expected_path: DispatchPath
    path: Literal["path_a", "path_b"]  # which per-path metric this case feeds


@dataclass(frozen=True)
class AskImageCase:
    """One Path B keyword-recall case.

    ``mock_vl_reply`` is the scripted answer the mock ``vl_caller``
    returns; the eval checks ``expected_keyword`` is a (case-insensitive)
    substring of the answer the tool surfaces to the agent.
    """

    case_id: str
    image_ref: str
    question: str
    mock_vl_reply: str
    expected_keyword: str


@dataclass(frozen=True)
class _NoopImageResolver:
    """Implements :class:`ImageResolver` — Path B does not resolve images itself."""

    async def resolve(self, *, image_refs: Sequence[str]) -> dict[str, ResolvedImage]:
        return {}


_MockVlCaller = Callable[..., Awaitable[AIMessage]]


def _make_mock_vl_caller(reply_text: str) -> _MockVlCaller:
    async def _vl_caller(
        *, messages: Sequence[BaseMessage], tools: Sequence[ToolSpec]
    ) -> AIMessage:
        _ = messages, tools
        return AIMessage(content=reply_text)

    return _vl_caller


async def _run_dispatch_case(case: DispatchCase) -> CapabilityCaseResult:
    got = _classify_path(
        vision_block_present=case.vision_block_present,
        supports_vision=case.supports_vision,
    )
    passed = got == case.expected_path
    notes = () if passed else (f"expected_path={case.expected_path!r} got={got!r}",)
    return CapabilityCaseResult(case_id=case.case_id, passed=passed, notes=notes)


async def _run_ask_image_case(case: AskImageCase) -> CapabilityCaseResult:
    tenant_id = UUID(case.image_ref.split("/")[3])
    ctx = ToolContext(tenant_id=tenant_id, run_id=uuid4())
    tool = AskImageTool(
        vl_caller=cast(Any, _make_mock_vl_caller(case.mock_vl_reply)),
        image_resolver=cast(ImageResolver, _NoopImageResolver()),
    )
    args: Mapping[str, Any] = {"image_ref": case.image_ref, "question": case.question}
    result = await tool.call(args, ctx=ctx)
    answer = str(result.content)
    passed = case.expected_keyword.lower() in answer.lower()
    notes = (
        () if passed else (f"expected_keyword={case.expected_keyword!r} not in answer={answer!r}",)
    )
    return CapabilityCaseResult(case_id=case.case_id, passed=passed, notes=notes)


_AnyCase = DispatchCase | AskImageCase


async def evaluate_set(
    cases: Sequence[_AnyCase],
    *,
    judge: JudgeCompletionFn | None = None,
    rerun_count: int = 3,
) -> CapabilityReport:
    """Run every case; aggregate per-path pass-rate."""
    per_case: list[CapabilityCaseResult] = []
    path_a_results: list[bool] = []
    path_b_results: list[bool] = []

    for case in cases:
        if isinstance(case, DispatchCase):
            result = await _run_dispatch_case(case)
            (path_a_results if case.path == "path_a" else path_b_results).append(result.passed)
        else:
            result = await _run_ask_image_case(case)
            path_b_results.append(result.passed)
        per_case.append(result)

    pa = sum(path_a_results) / len(path_a_results) if path_a_results else 0.0
    pb = sum(path_b_results) / len(path_b_results) if path_b_results else 0.0
    meets_a = pa >= THRESHOLD["pass_rate_path_a"]
    meets_b = pb >= THRESHOLD["pass_rate_path_b"]
    status = "PASS" if meets_a and meets_b else "FAIL"
    return CapabilityReport(
        capability=CAPABILITY,
        metric_type=METRIC_TYPE,
        sample_size=len(per_case),
        threshold=THRESHOLD,
        aggregate_score={"pass_rate_path_a": pa, "pass_rate_path_b": pb},
        status=cast(Any, status),
        per_case=tuple(per_case),
    )


def load_cases(path: Path) -> list[_AnyCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[_AnyCase] = []
    for entry in raw.get("cases", []):
        scenario = entry.get("scenario", "dispatch")
        if scenario == "dispatch":
            out.append(_parse_dispatch_case(entry))
        elif scenario == "ask_image":
            out.append(_parse_ask_image_case(entry))
        else:
            msg = f"unknown scenario {scenario!r} in case {entry.get('id')!r}"
            raise ValueError(msg)
    return out


def _parse_dispatch_case(entry: dict[str, Any]) -> DispatchCase:
    return DispatchCase(
        case_id=str(entry["id"]),
        vision_block_present=bool(entry["vision_block_present"]),
        supports_vision=bool(entry["supports_vision"]),
        expected_path=cast(Any, entry["expected_path"]),
        path=cast(Any, entry["path"]),
    )


def _parse_ask_image_case(entry: dict[str, Any]) -> AskImageCase:
    return AskImageCase(
        case_id=str(entry["id"]),
        image_ref=str(entry["image_ref"]),
        question=str(entry["question"]),
        mock_vl_reply=str(entry["mock_vl_reply"]),
        expected_keyword=str(entry["expected_keyword"]),
    )


__all__ = [
    "CAPABILITY",
    "METRIC_TYPE",
    "THRESHOLD",
    "AskImageCase",
    "DispatchCase",
    "evaluate_set",
    "load_cases",
]
