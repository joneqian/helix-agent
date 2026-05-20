"""Tests for J.6 image-ref validation + Path A ``HumanMessage`` assembly.

Pure-helper unit tests; the handler integration is exercised by the
existing ``test_runs_api`` fixtures.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from control_plane.api.runs import (
    RunRequest,
    _build_human_message,
    _validate_image_refs,
)
from helix_agent.protocol.multimodal import ImageRef

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_THREAD = UUID("22222222-2222-2222-2222-222222222222")


def _ref(tenant: UUID = _TENANT, thread: UUID = _THREAD, ext: str = ".png") -> str:
    return ImageRef(tenant_id=tenant, thread_id=thread, image_id=uuid4(), ext=ext).to_uri()


# ---------------------------------------------------------------------------
# RunRequest schema
# ---------------------------------------------------------------------------


def test_run_request_defaults_image_refs_to_empty() -> None:
    assert RunRequest().image_refs == []


def test_run_request_accepts_valid_image_refs() -> None:
    req = RunRequest(image_refs=[_ref(), _ref()])
    assert len(req.image_refs) == 2


def test_run_request_rejects_malformed_image_ref() -> None:
    with pytest.raises(ValidationError) as exc:
        RunRequest(image_refs=["not-a-helix-ref"])
    assert "image ref" in str(exc.value)


# ---------------------------------------------------------------------------
# _validate_image_refs
# ---------------------------------------------------------------------------


def _validate(
    refs: list[str],
    *,
    supports_vision: bool = True,
    has_vision_block: bool = False,
    max_per_run: int = 8,
) -> None:
    _validate_image_refs(
        refs,
        tenant_id=_TENANT,
        thread_id=_THREAD,
        supports_vision=supports_vision,
        has_vision_block=has_vision_block,
        max_per_run=max_per_run,
    )


def test_validate_passes_no_refs() -> None:
    _validate([], supports_vision=False, has_vision_block=False)


def test_validate_passes_path_a() -> None:
    _validate([_ref()], supports_vision=True, has_vision_block=False)


def test_validate_passes_path_b() -> None:
    _validate([_ref()], supports_vision=False, has_vision_block=True)


def test_validate_422_for_image_incapable_agent() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate([_ref()], supports_vision=False, has_vision_block=False)
    assert exc.value.status_code == 422
    assert "does not accept image input" in exc.value.detail


def test_validate_422_for_too_many_refs() -> None:
    refs = [_ref() for _ in range(9)]
    with pytest.raises(HTTPException) as exc:
        _validate(refs, max_per_run=8)
    assert exc.value.status_code == 422
    assert "too many" in exc.value.detail


def test_validate_404_for_cross_tenant_ref() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate([_ref(tenant=uuid4())])
    assert exc.value.status_code == 404


def test_validate_404_for_cross_thread_ref() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate([_ref(thread=uuid4())])
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# _build_human_message
# ---------------------------------------------------------------------------


def test_build_human_message_plain_text_unchanged() -> None:
    msg = _build_human_message(input_text="hello", image_refs=[], supports_vision=False)
    assert msg.content == "hello"


def test_build_human_message_none_input_becomes_empty_string() -> None:
    msg = _build_human_message(input_text=None, image_refs=[], supports_vision=True)
    assert msg.content == ""


def test_build_human_message_path_a_emits_content_blocks() -> None:
    ref = _ref()
    msg = _build_human_message(input_text="what is this?", image_refs=[ref], supports_vision=True)
    assert msg.content == [
        {"type": "text", "text": "what is this?"},
        {"type": "image_ref", "ref": ref},
    ]


def test_build_human_message_path_a_omits_empty_text_block() -> None:
    ref = _ref()
    msg = _build_human_message(input_text=None, image_refs=[ref], supports_vision=True)
    assert msg.content == [{"type": "image_ref", "ref": ref}]


def test_build_human_message_path_b_falls_through_to_text_only() -> None:
    """PR6 stage: vision-incapable manifest gets a plain-text message;
    PR7 will add the Path B text-reference assembly that mentions the
    refs to the agent for ``ask_image`` to consume."""
    msg = _build_human_message(input_text="describe", image_refs=[_ref()], supports_vision=False)
    assert msg.content == "describe"
