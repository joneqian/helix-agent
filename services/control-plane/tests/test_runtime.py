"""Tests for control-plane ↔ orchestrator runtime glue."""

from __future__ import annotations

import pytest

from control_plane.runtime import make_knowledge_retriever, resolve_embedder, resolve_reranker
from helix_agent.persistence import InMemoryKnowledgeStore
from helix_agent.runtime.secret_store import parse_secret_ref
from helix_agent.testing import InMemorySecretStore
from orchestrator.llm import FakeEmbedder, OpenAICompatibleEmbedder
from orchestrator.tools import KnowledgeRetriever, LLMReranker


@pytest.mark.asyncio
async def test_resolve_embedder_none_ref_returns_none() -> None:
    """No embedding key → no embedder → long-term memory unavailable."""
    embedder = await resolve_embedder(
        api_key_ref=None, model="text-embedding-v4", secret_store=InMemorySecretStore()
    )
    assert embedder is None


@pytest.mark.asyncio
async def test_resolve_embedder_builds_from_secret() -> None:
    store = InMemorySecretStore()
    ref = "secret://helix-agent/dev/embedding"
    await store.put(parse_secret_ref(ref), "sk-embed-test")

    embedder = await resolve_embedder(
        api_key_ref=ref, model="text-embedding-v4", secret_store=store
    )
    assert isinstance(embedder, OpenAICompatibleEmbedder)
    assert embedder.model == "text-embedding-v4"


@pytest.mark.asyncio
async def test_resolve_reranker_none_ref_returns_none() -> None:
    """No rerank key → no reranker → hybrid search returns the fused order."""
    reranker = await resolve_reranker(
        api_key_ref=None,
        provider="qwen",
        model="qwen-plus",
        secret_store=InMemorySecretStore(),
    )
    assert reranker is None


@pytest.mark.asyncio
async def test_resolve_reranker_builds_llm_reranker() -> None:
    store = InMemorySecretStore()
    ref = "secret://helix-agent/dev/rerank"
    await store.put(parse_secret_ref(ref), "sk-rerank-test")

    reranker = await resolve_reranker(
        api_key_ref=ref, provider="qwen", model="qwen-plus", secret_store=store
    )
    assert isinstance(reranker, LLMReranker)


def test_make_knowledge_retriever_none_without_embedder() -> None:
    retriever = make_knowledge_retriever(
        store=InMemoryKnowledgeStore(), embedder=None, reranker=None
    )
    assert retriever is None


def test_make_knowledge_retriever_builds_with_embedder() -> None:
    retriever = make_knowledge_retriever(
        store=InMemoryKnowledgeStore(), embedder=FakeEmbedder(), reranker=None
    )
    assert isinstance(retriever, KnowledgeRetriever)
