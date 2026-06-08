"""Tests for the SE-6a co-evolve orchestration core.

Pure loop logic over injected seams (distill / replay / attribute / revise);
ties SE-4 (replay verdict) + SE-5 (distil + attribute) into the bounded
generation-verification-refinement loop. CI fakes stand in for the real deps
the SE-6b worker wires.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from control_plane.skill_attribution import AttributionVerdict, FailureKind, FailureSignal
from control_plane.skill_distiller import SkillDraft
from control_plane.skill_evolution import (
    EvolutionConfig,
    ReplayOutcome,
    evolve,
)


def _draft(name: str = "s", frag: str = "do it well") -> SkillDraft:
    return SkillDraft(
        name=name,
        prompt_fragment=frag,
        tool_names=(),
        description="d",
        category=None,
        high_risk=False,
    )


def _content(reason: str = "content") -> AttributionVerdict:
    return AttributionVerdict(kind=FailureKind.CONTENT, by_rule=False, reason=reason)


def _execution(reason: str = "env") -> AttributionVerdict:
    return AttributionVerdict(kind=FailureKind.EXECUTION, by_rule=True, reason=reason)


def _scripted_replays(outcomes: Sequence[ReplayOutcome]):
    it = iter(outcomes)

    async def replay(draft: SkillDraft, round_no: int) -> ReplayOutcome:
        return next(it)

    return replay


async def _no_distill() -> None:
    return None


# --------------------------------------------------------------------------- #


async def test_no_draft_outcome() -> None:
    async def attribute(d: SkillDraft, s: FailureSignal) -> AttributionVerdict:
        raise AssertionError("not reached")

    async def revise(d: SkillDraft, o: ReplayOutcome) -> SkillDraft | None:
        raise AssertionError("not reached")

    result = await evolve(
        distill=_no_distill,
        replay=_scripted_replays([]),
        attribute=attribute,
        revise=revise,
    )
    assert result.outcome == "no_draft"
    assert result.draft is None
    assert result.rounds == 0


async def test_first_replay_pass_is_grounded() -> None:
    async def distill() -> SkillDraft:
        return _draft()

    result = await evolve(
        distill=distill,
        replay=_scripted_replays([ReplayOutcome(verdict="pass")]),
        attribute=_unused_attr,
        revise=_unused_revise,
    )
    assert result.outcome == "grounded"
    assert result.rounds == 1
    assert result.history[0].verdict == "pass"


async def test_content_error_revise_then_pass() -> None:
    drafts = [_draft("v1"), _draft("v2")]

    async def distill() -> SkillDraft:
        return drafts[0]

    async def attribute(d: SkillDraft, s: FailureSignal) -> AttributionVerdict:
        return _content()

    async def revise(d: SkillDraft, o: ReplayOutcome) -> SkillDraft:
        return drafts[1]

    result = await evolve(
        distill=distill,
        replay=_scripted_replays(
            [
                ReplayOutcome(verdict="fail", failure_signal=FailureSignal(error_text="bad")),
                ReplayOutcome(verdict="pass"),
            ]
        ),
        attribute=attribute,
        revise=revise,
    )
    assert result.outcome == "grounded"
    assert result.rounds == 2
    assert result.draft is drafts[1]
    assert result.history[0].attribution is FailureKind.CONTENT


async def test_execution_error_rejected_no_revise() -> None:
    async def distill() -> SkillDraft:
        return _draft()

    revise_called = False

    async def revise(d: SkillDraft, o: ReplayOutcome) -> SkillDraft | None:
        nonlocal revise_called
        revise_called = True
        return _draft()

    async def attribute(d: SkillDraft, s: FailureSignal) -> AttributionVerdict:
        return _execution()

    result = await evolve(
        distill=distill,
        replay=_scripted_replays(
            [ReplayOutcome(verdict="fail", failure_signal=FailureSignal(timed_out=True))]
        ),
        attribute=attribute,
        revise=revise,
    )
    assert result.outcome == "rejected"
    assert revise_called is False  # execution error: do not feed back


async def test_inconclusive_is_rejected_for_human() -> None:
    async def distill() -> SkillDraft:
        return _draft()

    result = await evolve(
        distill=distill,
        replay=_scripted_replays([ReplayOutcome(verdict="inconclusive")]),
        attribute=_unused_attr,
        revise=_unused_revise,
    )
    assert result.outcome == "rejected"
    assert "inconclusive" in result.reason


async def test_revise_returns_none_is_rejected() -> None:
    async def distill() -> SkillDraft:
        return _draft()

    async def attribute(d: SkillDraft, s: FailureSignal) -> AttributionVerdict:
        return _content()

    async def revise(d: SkillDraft, o: ReplayOutcome) -> SkillDraft | None:
        return None

    result = await evolve(
        distill=distill,
        replay=_scripted_replays(
            [ReplayOutcome(verdict="fail", failure_signal=FailureSignal(error_text="x"))]
        ),
        attribute=attribute,
        revise=revise,
    )
    assert result.outcome == "rejected"


async def test_exhausts_max_rounds() -> None:
    async def distill() -> SkillDraft:
        return _draft()

    async def attribute(d: SkillDraft, s: FailureSignal) -> AttributionVerdict:
        return _content()

    async def revise(d: SkillDraft, o: ReplayOutcome) -> SkillDraft:
        return _draft()

    one_fail = ReplayOutcome(verdict="fail", failure_signal=FailureSignal(error_text="x"))
    fails = [one_fail, one_fail]
    result = await evolve(
        distill=distill,
        replay=_scripted_replays(fails),
        attribute=attribute,
        revise=revise,
        config=EvolutionConfig(max_rounds=2),
    )
    assert result.outcome == "exhausted"
    assert result.rounds == 2
    assert len(result.history) == 2


def test_config_rejects_nonpositive_rounds() -> None:
    with pytest.raises(ValueError):
        EvolutionConfig(max_rounds=0)


# helpers that must never be called in the pass/no-draft paths
async def _unused_attr(d: SkillDraft, s: FailureSignal) -> AttributionVerdict:
    raise AssertionError("attribute should not be called")


async def _unused_revise(d: SkillDraft, o: ReplayOutcome) -> SkillDraft | None:
    raise AssertionError("revise should not be called")
