"""Unit tests for the J.5 RAG eval — Stream J.13a closeout."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from rag import (  # type: ignore[import-not-found]  # noqa: E402
    RagCase,
    RagChunk,
    RagDocument,
    RagKnowledgeBase,
    evaluate_set,
    load_cases,
)
from run_baseline import _FakeKeywordEmbedder  # type: ignore[import-not-found]  # noqa: E402


def test_load_cases_parses_eleven() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "rag" / "m0_baseline.yaml")
    assert len(cases) == 11


@pytest.mark.asyncio
async def test_baseline_dataset_passes() -> None:
    cases = load_cases(_EVAL_DIR / "datasets" / "rag" / "m0_baseline.yaml")
    report = await evaluate_set(cases, embedder=_FakeKeywordEmbedder())
    assert report.status == "PASS"
    assert report.aggregate_score["pass_rate"] >= 0.80
    assert report.aggregate_score["recall_at_k"] >= 0.70


@pytest.mark.asyncio
async def test_missing_expected_chunk_fails() -> None:
    """A case whose expected chunk lives in a KB the query doesn't include
    must fail — proves the eval doesn't silently accept misses."""
    case = RagCase(
        case_id="missing-expected",
        knowledge_bases=(
            RagKnowledgeBase(
                name="kb-a",
                documents=(
                    RagDocument(
                        filename="a.md",
                        chunks=(RagChunk(id="a-001", content="alpha topic content"),),
                    ),
                ),
            ),
        ),
        query_bases=("kb-a",),
        query="completely unrelated phrase xyz",
        expected_chunk_ids=("nonexistent-id",),
        k=5,
    )
    report = await evaluate_set([case], embedder=_FakeKeywordEmbedder())
    assert report.status == "FAIL"
    assert not report.per_case[0].passed


@pytest.mark.asyncio
async def test_unknown_query_base_returns_empty() -> None:
    """``query_bases`` containing a base the store doesn't have produces
    empty retrieval — the retriever resolves base names at query time
    (the production contract)."""
    case = RagCase(
        case_id="unknown-base",
        knowledge_bases=(
            RagKnowledgeBase(
                name="kb-real",
                documents=(
                    RagDocument(
                        filename="x.md",
                        chunks=(RagChunk(id="x-001", content="alpha"),),
                    ),
                ),
            ),
        ),
        query_bases=("kb-real", "kb-does-not-exist"),
        query="alpha",
        expected_chunk_ids=("x-001",),
        k=5,
    )
    report = await evaluate_set([case], embedder=_FakeKeywordEmbedder())
    # The real base still resolves and the chunk still lands; missing
    # base is silently skipped per ``KnowledgeRetriever._resolve_base_ids``.
    assert report.status == "PASS"
