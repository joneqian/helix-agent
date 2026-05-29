"""Stream O Mini-ADR O-12 — mode-switch gate completeness for infra providers.

``_collect_used_providers`` walks agent manifests for the providers a tenant
references. Beyond the manifest model fields, long-term memory uses the
platform ``embedding_provider`` (platform infra, not in any model field), so
an agent declaring ``memory.long_term`` must add it to the gate. Rerank is
deliberately NOT added — a missing rerank credential degrades gracefully
(Mini-ADR O-9).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from control_plane.api.tenant_config import _collect_used_providers
from helix_agent.protocol import AgentSpec, AgentSpecRecord, AgentSpecStatus

_SHA = "a" * 64


def _spec(*, with_long_term_memory: bool) -> AgentSpec:
    body: dict[str, object] = {
        "tenant_config": {},
        "model": {"provider": "anthropic", "name": "claude"},
        "system_prompt": {"template": "x"},
        "sandbox": {
            "resources": {"cpu": "1", "memory": "1Gi"},
            "network": {"egress": "proxy", "allowlist": ["a.com"]},
            "filesystem": {},
        },
    }
    if with_long_term_memory:
        body["memory"] = {"long_term": {}}
    return AgentSpec.model_validate(
        {
            "apiVersion": "helix.io/v1",
            "kind": "Agent",
            "metadata": {"name": "a", "version": "1.0.0", "tenant": "t"},
            "spec": body,
        }
    )


def _record(spec: AgentSpec) -> AgentSpecRecord:
    now = datetime.now(UTC)
    return AgentSpecRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name="a",
        version="1.0.0",
        spec=spec,
        spec_sha256=_SHA,
        status=AgentSpecStatus.ACTIVE,
        created_by="tester",
        created_at=now,
        updated_at=now,
    )


def test_long_term_memory_adds_embedding_provider() -> None:
    used = _collect_used_providers(
        [_record(_spec(with_long_term_memory=True))], embedding_provider="qwen"
    )
    assert "anthropic" in used  # the primary model provider
    assert "qwen" in used  # O-12 — embedding provider gated for long-term memory


def test_no_long_term_memory_omits_embedding_provider() -> None:
    used = _collect_used_providers(
        [_record(_spec(with_long_term_memory=False))], embedding_provider="qwen"
    )
    assert used == {"anthropic"}


def test_embedding_provider_is_deduped_when_also_a_model_provider() -> None:
    # If the embedding provider equals a model provider already collected,
    # it appears once (set semantics) — no double counting.
    used = _collect_used_providers(
        [_record(_spec(with_long_term_memory=True))], embedding_provider="anthropic"
    )
    assert used == {"anthropic"}
