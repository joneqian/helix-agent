"""Tests for the J.4 ``ChildAgentBuilder`` wiring — ``make_child_agent_builder``."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from control_plane.subagent_runtime import SubAgentNotFoundError, make_child_agent_builder
from helix_agent.persistence.agent_spec import InMemoryAgentSpecStore
from helix_agent.protocol import AgentSpec, AgentSpecStatus
from helix_agent.testing import InMemorySecretStore
from orchestrator import BuiltAgent, ToolEnv

_SHA = "a" * 64


def _spec(name: str, version: str = "1.0.0") -> AgentSpec:
    return AgentSpec.model_validate(
        {
            "apiVersion": "helix.io/v1",
            "kind": "Agent",
            "metadata": {"name": name, "version": version, "tenant": "t"},
            "spec": {
                "tenant_config": {},
                "model": {"provider": "anthropic", "name": "claude"},
                "system_prompt": {"template": "x"},
                "sandbox": {
                    "resources": {"cpu": "1", "memory": "1Gi"},
                    "network": {"egress": "proxy", "allowlist": ["a.com"]},
                    "filesystem": {},
                },
            },
        }
    )


@pytest.fixture
def build_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace ``build_agent`` with a recorder so the wiring is tested
    without real LLM provider clients."""
    calls: list[dict[str, Any]] = []

    async def _fake_build_agent(spec: AgentSpec, **kwargs: Any) -> BuiltAgent:
        calls.append({"spec": spec, **kwargs})
        return BuiltAgent(graph=object(), system_prompt="", max_steps=1)  # type: ignore[arg-type]

    monkeypatch.setattr("control_plane.subagent_runtime.build_agent", _fake_build_agent)
    return calls


@pytest.mark.asyncio
async def test_resolves_and_builds_subagent(build_calls: list[dict[str, Any]]) -> None:
    tenant = uuid4()
    store = InMemoryAgentSpecStore()
    await store.create(
        tenant_id=tenant, spec=_spec("researcher"), spec_sha256=_SHA, created_by="test"
    )
    builder = make_child_agent_builder(
        spec_store=store,
        secret_store=InMemorySecretStore(),
        checkpointer=InMemorySaver(),
        base_tool_env=ToolEnv(),
    )

    built = await builder(tenant_id=tenant, name="researcher", version="1.0.0", depth=1)

    assert isinstance(built, BuiltAgent)
    assert len(build_calls) == 1
    # The child builds at the depth the SubAgentTool requested.
    assert build_calls[0]["subagent_depth"] == 1


@pytest.mark.asyncio
async def test_depth_keyed_cache_hits(build_calls: list[dict[str, Any]]) -> None:
    tenant = uuid4()
    store = InMemoryAgentSpecStore()
    await store.create(
        tenant_id=tenant, spec=_spec("researcher"), spec_sha256=_SHA, created_by="test"
    )
    builder = make_child_agent_builder(
        spec_store=store,
        secret_store=InMemorySecretStore(),
        checkpointer=InMemorySaver(),
        base_tool_env=ToolEnv(),
    )

    first = await builder(tenant_id=tenant, name="researcher", version="1.0.0", depth=1)
    second = await builder(tenant_id=tenant, name="researcher", version="1.0.0", depth=1)

    assert second is first
    assert len(build_calls) == 1  # second call served from the cache


@pytest.mark.asyncio
async def test_same_manifest_different_depth_rebuilds(build_calls: list[dict[str, Any]]) -> None:
    # Depth is part of the cache key — the same manifest at depth 2 builds
    # a different graph (fewer / no SubAgentTools) than at depth 1.
    tenant = uuid4()
    store = InMemoryAgentSpecStore()
    await store.create(
        tenant_id=tenant, spec=_spec("researcher"), spec_sha256=_SHA, created_by="test"
    )
    builder = make_child_agent_builder(
        spec_store=store,
        secret_store=InMemorySecretStore(),
        checkpointer=InMemorySaver(),
        base_tool_env=ToolEnv(),
    )

    await builder(tenant_id=tenant, name="researcher", version="1.0.0", depth=1)
    await builder(tenant_id=tenant, name="researcher", version="1.0.0", depth=2)

    assert len(build_calls) == 2
    assert {c["subagent_depth"] for c in build_calls} == {1, 2}


@pytest.mark.asyncio
async def test_child_tool_env_carries_the_builder(build_calls: list[dict[str, Any]]) -> None:
    # A sub-agent's own ToolEnv carries the same builder, so a child can
    # delegate to a grandchild.
    tenant = uuid4()
    store = InMemoryAgentSpecStore()
    await store.create(
        tenant_id=tenant, spec=_spec("researcher"), spec_sha256=_SHA, created_by="test"
    )
    builder = make_child_agent_builder(
        spec_store=store,
        secret_store=InMemorySecretStore(),
        checkpointer=InMemorySaver(),
        base_tool_env=ToolEnv(),
    )

    await builder(tenant_id=tenant, name="researcher", version="1.0.0", depth=1)

    assert build_calls[0]["tool_env"].child_agent_builder is builder


@pytest.mark.asyncio
async def test_unknown_agent_ref_raises(build_calls: list[dict[str, Any]]) -> None:
    builder = make_child_agent_builder(
        spec_store=InMemoryAgentSpecStore(),
        secret_store=InMemorySecretStore(),
        checkpointer=InMemorySaver(),
        base_tool_env=ToolEnv(),
    )
    with pytest.raises(SubAgentNotFoundError):
        await builder(tenant_id=uuid4(), name="ghost", version="1.0.0", depth=1)
    assert build_calls == []


@pytest.mark.asyncio
async def test_soft_deleted_agent_ref_raises(build_calls: list[dict[str, Any]]) -> None:
    tenant = uuid4()
    store = InMemoryAgentSpecStore()
    await store.create(
        tenant_id=tenant, spec=_spec("researcher"), spec_sha256=_SHA, created_by="test"
    )
    await store.update_status(
        tenant_id=tenant, name="researcher", version="1.0.0", status=AgentSpecStatus.DELETED
    )
    builder = make_child_agent_builder(
        spec_store=store,
        secret_store=InMemorySecretStore(),
        checkpointer=InMemorySaver(),
        base_tool_env=ToolEnv(),
    )
    with pytest.raises(SubAgentNotFoundError):
        await builder(tenant_id=tenant, name="researcher", version="1.0.0", depth=1)
