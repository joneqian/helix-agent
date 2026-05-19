"""Tests for the J.6 multimodal content-block helpers + resolver."""

from __future__ import annotations

import base64

import pytest

from orchestrator.multimodal import (
    IMAGE_REF_BLOCK_TYPE,
    ImageResolver,
    InMemoryImageResolver,
    ResolvedImage,
    image_ref_block,
    split_human_content,
)

_DATA = b"\x89PNG\r\n\x1a\nfake-image-bytes"


def test_image_ref_block_shape() -> None:
    block = image_ref_block("helix://image/abc")
    assert block == {"type": IMAGE_REF_BLOCK_TYPE, "ref": "helix://image/abc"}


def test_split_human_content_plain_string() -> None:
    assert split_human_content("just text") == ("just text", [])


def test_split_human_content_text_blocks_only() -> None:
    content = [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]
    assert split_human_content(content) == ("hello world", [])


def test_split_human_content_collects_image_refs() -> None:
    content = [
        {"type": "text", "text": "look:"},
        image_ref_block("helix://image/one"),
        image_ref_block("helix://image/two"),
    ]
    text, refs = split_human_content(content)
    assert text == "look:"
    assert refs == ["helix://image/one", "helix://image/two"]


def test_split_human_content_accepts_bare_string_blocks() -> None:
    assert split_human_content(["a", "b"]) == ("ab", [])


def test_split_human_content_ignores_unknown_block_kinds() -> None:
    content = [123, {"type": "text", "text": "x"}, {"type": "mystery"}]
    assert split_human_content(content) == ("x", [])


def test_resolved_image_base64_round_trips() -> None:
    img = ResolvedImage(media_type="image/png", data=_DATA)
    assert base64.b64decode(img.base64_data) == _DATA


def test_resolved_image_data_uri() -> None:
    img = ResolvedImage(media_type="image/jpeg", data=_DATA)
    assert img.data_uri == f"data:image/jpeg;base64,{img.base64_data}"


@pytest.mark.asyncio
async def test_in_memory_resolver_resolves_known_ref() -> None:
    img = ResolvedImage(media_type="image/webp", data=_DATA)
    resolver = InMemoryImageResolver(images={"helix://image/x": img})
    assert await resolver.resolve("helix://image/x") is img


@pytest.mark.asyncio
async def test_in_memory_resolver_raises_on_missing_ref() -> None:
    resolver = InMemoryImageResolver()
    with pytest.raises(KeyError, match="no image for ref"):
        await resolver.resolve("helix://image/missing")


def test_in_memory_resolver_satisfies_protocol() -> None:
    assert isinstance(InMemoryImageResolver(), ImageResolver)
