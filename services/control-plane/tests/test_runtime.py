"""Tests for control-plane ↔ orchestrator runtime glue."""

from __future__ import annotations

import pytest

from control_plane.runtime import (
    make_image_resolver,
    make_knowledge_retriever,
    resolve_embedder,
    resolve_object_store_config,
    resolve_reranker,
)
from helix_agent.persistence import InMemoryKnowledgeStore
from helix_agent.runtime.secret_store import parse_secret_ref
from helix_agent.runtime.storage import InMemoryObjectStore
from helix_agent.testing import InMemorySecretStore
from orchestrator.llm import FakeEmbedder, OpenAICompatibleEmbedder
from orchestrator.multimodal import ObjectStoreImageResolver
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


def test_make_image_resolver_builds_object_store_resolver() -> None:
    resolver = make_image_resolver(InMemoryObjectStore())
    assert isinstance(resolver, ObjectStoreImageResolver)


@pytest.mark.asyncio
async def test_resolve_object_store_config_memory_returns_none() -> None:
    """The in-memory backend needs no S3 config."""
    config = await resolve_object_store_config(
        backend="memory",
        endpoint_url=None,
        region="us-east-1",
        bucket="helix-agent",
        access_key_ref=None,
        secret_key_ref=None,
        secret_store=InMemorySecretStore(),
    )
    assert config is None


@pytest.mark.asyncio
async def test_resolve_object_store_config_s3_without_endpoint_raises() -> None:
    with pytest.raises(RuntimeError, match="s3-compatible"):
        await resolve_object_store_config(
            backend="s3-compatible",
            endpoint_url=None,
            region="us-east-1",
            bucket="helix-agent",
            access_key_ref=None,
            secret_key_ref=None,
            secret_store=InMemorySecretStore(),
        )


@pytest.mark.asyncio
async def test_resolve_object_store_config_s3_resolves_keys() -> None:
    store = InMemorySecretStore()
    await store.put(parse_secret_ref("secret://helix-agent/dev/s3-access"), "AKID")
    await store.put(parse_secret_ref("secret://helix-agent/dev/s3-secret"), "SKEY")

    config = await resolve_object_store_config(
        backend="s3-compatible",
        endpoint_url="http://minio:9000",
        region="us-east-1",
        bucket="helix-agent",
        access_key_ref="secret://helix-agent/dev/s3-access",
        secret_key_ref="secret://helix-agent/dev/s3-secret",
        secret_store=store,
    )
    assert config is not None
    assert config.endpoint_url == "http://minio:9000"
    assert config.access_key == "AKID"
    assert config.secret_key == "SKEY"
