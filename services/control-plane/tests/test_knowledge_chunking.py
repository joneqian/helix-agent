"""Tests for J.5 structure-aware + semantic Markdown chunking."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from control_plane.knowledge.chunking import (
    _cosine_distance,
    chunk_markdown,
    chunk_markdown_semantic,
    count_tokens,
)


class _ScriptedEmbedder:
    """Embedder test double — vector chosen by a topic marker in the text."""

    def __init__(self, markers: dict[str, tuple[float, ...]]) -> None:
        self._markers = markers

    async def embed(self, texts: Sequence[str], *, tenant_id: UUID) -> list[tuple[float, ...]]:
        del tenant_id
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> tuple[float, ...]:
        for marker, vector in self._markers.items():
            if marker in text:
                return vector
        return (0.0, 0.0)


class _FailEmbedder:
    """Embedder that raises if used — proves a code path skips embedding."""

    async def embed(self, texts: Sequence[str], *, tenant_id: UUID) -> list[tuple[float, ...]]:
        del tenant_id
        raise AssertionError("embedder must not be called")


def test_count_tokens() -> None:
    assert count_tokens("") == 0
    assert count_tokens("hello world") > 0


def test_empty_input_yields_no_chunks() -> None:
    assert chunk_markdown("", max_tokens=512, overlap_tokens=64) == []


def test_no_headings_has_no_section_prefix() -> None:
    chunks = chunk_markdown("just some plain text.", max_tokens=512, overlap_tokens=0)
    assert len(chunks) == 1
    assert not chunks[0].startswith("[Section:")
    assert "plain text" in chunks[0]


def test_different_sections_become_separate_chunks() -> None:
    src = "# A\n\nalpha content.\n\n# B\n\nbeta content."
    chunks = chunk_markdown(src, max_tokens=512, overlap_tokens=0)
    assert len(chunks) == 2
    assert chunks[0].startswith("[Section: A]")
    assert "alpha content" in chunks[0]
    assert chunks[1].startswith("[Section: B]")
    assert "beta content" in chunks[1]


def test_nested_heading_breadcrumb_prefix() -> None:
    src = "# Guide\n\n## Setup\n\ninstall steps here."
    chunks = chunk_markdown(src, max_tokens=512, overlap_tokens=0)
    assert chunks[0].startswith("[Section: Guide > Setup]")
    assert "install steps" in chunks[0]


def test_chinese_content_chunks_with_breadcrumb() -> None:
    src = "# 健康保险\n\n## 免赔额\n\n免赔额是每年五百元。"
    chunks = chunk_markdown(src, max_tokens=512, overlap_tokens=0)
    assert len(chunks) == 1
    assert chunks[0].startswith("[Section: 健康保险 > 免赔额]")
    assert "五百元" in chunks[0]


def test_overlap_repeats_text_within_a_section() -> None:
    body = " ".join(f"word{i} sentence{i}." for i in range(40))
    src = f"# S\n\n{body}"
    without = chunk_markdown(src, max_tokens=30, overlap_tokens=0)
    overlapped = chunk_markdown(src, max_tokens=30, overlap_tokens=15)
    assert len(without) > 1
    assert len(overlapped) > 1
    # Overlap re-emits the previous chunk's tail → more total text.
    assert sum(len(c) for c in overlapped) > sum(len(c) for c in without)


def test_overlap_not_carried_across_a_heading_change() -> None:
    src = "# A\n\nuniquealphatoken here.\n\n# B\n\nuniquebetatoken here."
    chunks = chunk_markdown(src, max_tokens=512, overlap_tokens=64)
    assert len(chunks) == 2
    assert "uniquealphatoken" not in chunks[1]


def test_table_kept_whole_when_it_fits() -> None:
    src = "# T\n\n| a | b |\n| - | - |\n| 1 | 2 |\n| 3 | 4 |"
    chunks = chunk_markdown(src, max_tokens=512, overlap_tokens=0)
    assert len(chunks) == 1
    assert "| 1 | 2 |" in chunks[0]
    assert "| 3 | 4 |" in chunks[0]


def test_oversized_table_splits_by_rows_keeping_header() -> None:
    rows = "\n".join(f"| row{i} | value{i} |" for i in range(30))
    src = f"# T\n\n| name | value |\n| - | - |\n{rows}"
    chunks = chunk_markdown(src, max_tokens=40, overlap_tokens=0)
    assert len(chunks) > 1
    # Every part is a valid table — the header row is repeated.
    for chunk in chunks:
        assert "| name | value |" in chunk


def test_oversized_paragraph_is_hard_split() -> None:
    paragraph = " ".join(f"sentence number {i} of the paragraph." for i in range(60))
    src = f"# P\n\n{paragraph}"
    chunks = chunk_markdown(src, max_tokens=30, overlap_tokens=0)
    assert len(chunks) > 1
    assert all("sentence number" in chunk for chunk in chunks)


def test_consecutive_paragraphs_pack_into_one_chunk() -> None:
    src = "# S\n\nfirst short paragraph.\n\nsecond short paragraph."
    chunks = chunk_markdown(src, max_tokens=512, overlap_tokens=0)
    assert len(chunks) == 1
    assert "first short paragraph" in chunks[0]
    assert "second short paragraph" in chunks[0]


# ---------------------------------------------------------------------------
# semantic refinement
# ---------------------------------------------------------------------------


def test_cosine_distance() -> None:
    assert _cosine_distance((1.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)
    assert _cosine_distance((1.0, 0.0), (0.0, 1.0)) == pytest.approx(1.0)
    assert _cosine_distance((0.0, 0.0), (1.0, 0.0)) == 1.0  # zero vector


@pytest.mark.asyncio
async def test_semantic_split_at_topic_shift() -> None:
    src = "TOPICA first.\n\nTOPICA second.\n\nTOPICB third.\n\nTOPICB fourth."
    embedder = _ScriptedEmbedder({"TOPICA": (1.0, 0.0), "TOPICB": (0.0, 1.0)})
    chunks = await chunk_markdown_semantic(
        src, max_tokens=512, overlap_tokens=0, embedder=embedder, tenant_id=uuid4()
    )
    # The A→B topic shift splits a section structural chunking keeps whole.
    assert len(chunks) == 2
    assert "TOPICA first" in chunks[0]
    assert "TOPICA second" in chunks[0]
    assert "TOPICB third" in chunks[1]
    assert "TOPICB fourth" in chunks[1]
    assert len(chunk_markdown(src, max_tokens=512, overlap_tokens=0)) == 1


@pytest.mark.asyncio
async def test_semantic_no_split_when_section_is_coherent() -> None:
    src = "TOPICA one.\n\nTOPICA two.\n\nTOPICA three."
    embedder = _ScriptedEmbedder({"TOPICA": (1.0, 0.0)})
    chunks = await chunk_markdown_semantic(
        src, max_tokens=512, overlap_tokens=0, embedder=embedder, tenant_id=uuid4()
    )
    assert len(chunks) == 1


@pytest.mark.asyncio
async def test_semantic_still_flushes_on_heading_change() -> None:
    # Same topic marker → no semantic break, but the heading change flushes.
    src = "# A\n\nTOPICA content.\n\n# B\n\nTOPICA other."
    embedder = _ScriptedEmbedder({"TOPICA": (1.0, 0.0)})
    chunks = await chunk_markdown_semantic(
        src, max_tokens=512, overlap_tokens=0, embedder=embedder, tenant_id=uuid4()
    )
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_semantic_skips_embedding_for_single_block() -> None:
    # < 2 blocks → no topic shift possible → embedder is never called.
    chunks = await chunk_markdown_semantic(
        "just one paragraph.",
        max_tokens=512,
        overlap_tokens=0,
        embedder=_FailEmbedder(),
        tenant_id=uuid4(),
    )
    assert len(chunks) == 1


@pytest.mark.asyncio
async def test_semantic_empty_input() -> None:
    chunks = await chunk_markdown_semantic(
        "", max_tokens=512, overlap_tokens=64, embedder=_FailEmbedder(), tenant_id=uuid4()
    )
    assert chunks == []
