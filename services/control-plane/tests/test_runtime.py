"""Tests for control-plane ↔ orchestrator runtime glue."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from control_plane.runtime import (
    AgentRuntime,
    ResolvingEmbedder,
    ResolvingReranker,
    make_image_resolver,
    make_knowledge_retriever,
    resolve_embedder,
    resolve_object_store_config,
    resolve_reranker,
)
from helix_agent.common.credentials import CredentialsResolver
from helix_agent.persistence import InMemoryKnowledgeStore
from helix_agent.protocol import AgentSpec, TenantConfigRecord
from helix_agent.runtime.runs import RunManager
from helix_agent.runtime.secret_store import parse_secret_ref
from helix_agent.runtime.storage import InMemoryObjectStore
from helix_agent.runtime.stream_bridge import InMemoryStreamBridge
from helix_agent.testing import InMemorySecretStore
from orchestrator.llm import FakeEmbedder
from orchestrator.multimodal import ObjectStoreImageResolver
from orchestrator.tools import KnowledgeRetriever

_MINIMAL_MANIFEST: dict[str, Any] = {
    "apiVersion": "helix.io/v1",
    "kind": "Agent",
    "metadata": {"name": "x", "version": "1", "tenant": "test-tenant"},
    "spec": {
        "tenant_config": {},
        "model": {"provider": "anthropic", "name": "claude-haiku-4-5"},
        "system_prompt": {"template": "you help"},
        "sandbox": {
            "resources": {"cpu": "1.0", "memory": "1Gi"},
            "network": {"egress": "none", "allowlist": []},
            "filesystem": {"readonly_root": True, "writable": []},
        },
    },
}


def _make_spec(*, name: str = "x", version: str = "1") -> AgentSpec:
    manifest = dict(_MINIMAL_MANIFEST)
    manifest["metadata"] = dict(manifest["metadata"], name=name, version=version)
    return AgentSpec.model_validate(manifest)


class _NeverCalledTenantConfig:
    """``resolve_embedder`` / ``resolve_reranker`` are pure factories — they
    never touch the tenant config, so this getter is never invoked."""

    async def get(self, *, tenant_id: UUID) -> TenantConfigRecord:  # pragma: no cover
        raise AssertionError("factory must not resolve tenant config")


def _resolver() -> CredentialsResolver:
    return CredentialsResolver(
        platform_provider_credentials={},  # type: ignore[arg-type]
        platform_tool_credentials={},  # type: ignore[arg-type]
        tenant_config_getter=_NeverCalledTenantConfig(),
    )


@pytest.mark.asyncio
async def test_resolve_embedder_unsupported_provider_returns_none() -> None:
    """Embedding provider absent from the catalog → no embedder → long-term
    memory globally unavailable (build-time gate preserved, Mini-ADR O-11)."""
    embedder = await resolve_embedder(
        resolver=_resolver(),
        secret_store=InMemorySecretStore(),
        provider="qwen",
        model="text-embedding-v4",
        supported_providers=[],
    )
    assert embedder is None


@pytest.mark.asyncio
async def test_resolve_embedder_builds_resolving_embedder() -> None:
    embedder = await resolve_embedder(
        resolver=_resolver(),
        secret_store=InMemorySecretStore(),
        provider="qwen",
        model="text-embedding-v4",
        supported_providers=["qwen"],
    )
    assert isinstance(embedder, ResolvingEmbedder)
    assert embedder.model == "text-embedding-v4"
    assert embedder.provider == "qwen"


@pytest.mark.asyncio
async def test_resolve_reranker_unsupported_provider_returns_none() -> None:
    """Rerank provider absent from the catalog → no reranker → hybrid search
    returns the fused order."""
    reranker = await resolve_reranker(
        resolver=_resolver(),
        secret_store=InMemorySecretStore(),
        provider="qwen",
        model="qwen-plus",
        supported_providers=[],
    )
    assert reranker is None


@pytest.mark.asyncio
async def test_resolve_reranker_builds_resolving_reranker() -> None:
    reranker = await resolve_reranker(
        resolver=_resolver(),
        secret_store=InMemorySecretStore(),
        provider="qwen",
        model="qwen-plus",
        supported_providers=["qwen"],
    )
    assert isinstance(reranker, ResolvingReranker)
    assert reranker.provider == "qwen"


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


# ---------------------------------------------------------------------------
# AgentRuntime.invalidate_tenant (Stream V-D, Mini-ADR V-4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_tenant_drops_only_that_tenants_cached_agents() -> None:
    """invalidate_tenant(a) drops all entries for tenant a, leaves tenant b cached."""
    builds: list[tuple[UUID | None, str | None]] = []

    async def _builder(spec: AgentSpec, *, tenant_id: UUID | None = None) -> object:
        builds.append((tenant_id, spec.metadata.name if spec is not None else None))
        return object()  # stand-in BuiltAgent

    runtime = AgentRuntime(
        run_manager=RunManager(store=None),  # type: ignore[arg-type]
        stream_bridge=InMemoryStreamBridge(),
        agent_builder=_builder,  # type: ignore[arg-type]
    )
    a, b = uuid4(), uuid4()
    spec = _make_spec(name="x", version="1")

    await runtime.get_agent(tenant_id=a, name="x", version="1", spec=spec)
    await runtime.get_agent(tenant_id=b, name="x", version="1", spec=spec)
    assert len(builds) == 2

    runtime.invalidate_tenant(a)

    # tenant a rebuilds; tenant b still cached (no new build)
    await runtime.get_agent(tenant_id=a, name="x", version="1", spec=spec)
    await runtime.get_agent(tenant_id=b, name="x", version="1", spec=spec)
    assert len(builds) == 3  # only a rebuilt
