"""End-to-end tests for the SSE run trigger + Stream B acceptance flow."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from control_plane.app import create_app
from control_plane.audit import build_default_audit_logger
from control_plane.settings import DEFAULT_DEV_TENANT_ID, Settings
from helix_agent.common.deadline import CancelToken
from helix_agent.persistence.audit_log import InMemoryAuditLogStore
from helix_agent.protocol import AuditQuery

_DEFAULT_TENANT = DEFAULT_DEV_TENANT_ID

_AGENT_YAML = """\
apiVersion: helix.io/v1
kind: Agent
metadata:
  name: code-reviewer
  version: "1.0.0"
  tenant: platform-eng
spec:
  tenant_config: {}
  model:
    provider: anthropic
    name: claude-sonnet-4-5
  system_prompt:
    template: "you are a reviewer"
  sandbox:
    resources: { cpu: "1.0", memory: "1Gi" }
    network:
      egress: proxy
      allowlist: ["api.anthropic.com"]
    filesystem:
      readonly_root: true
      writable: ["/workspace"]
"""


@pytest.fixture
def audit_store() -> InMemoryAuditLogStore:
    return InMemoryAuditLogStore()


@pytest.fixture
async def runs_client(audit_store: InMemoryAuditLogStore) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        env="dev",
        auth_mode="dev",
        rate_limit_burst=10_000,
        rate_limit_per_second=10_000.0,
        # Deterministic, no inter-token sleep.
        run_fake_token_delay_s=0.0,
    )
    app = create_app(
        settings=settings,
        audit_logger=build_default_audit_logger(audit_store),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://control-plane.test") as client:
        await client.post("/v1/agents", json={"manifest_yaml": _AGENT_YAML})
        yield client


async def _parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for chunk in body.split("\n\n"):
        if not chunk.strip():
            continue
        event_type = ""
        data_payload = ""
        for line in chunk.splitlines():
            if line.startswith("event: "):
                event_type = line[len("event: ") :]
            elif line.startswith("data: "):
                data_payload = line[len("data: ") :]
        events.append((event_type, json.loads(data_payload)))
    return events


async def _create_session(client: AsyncClient) -> str:
    response = await client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    assert response.status_code == 201
    return str(response.json()["data"]["thread_id"])


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_emits_three_tokens_then_done(runs_client: AsyncClient) -> None:
    thread_id = await _create_session(runs_client)
    response = await runs_client.post(f"/v1/sessions/{thread_id}/runs", json={})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = await _parse_sse(response.text)
    types = [e[0] for e in events]
    assert types[:3] == ["token", "token", "token"]
    assert types[-1] == "done"

    # Token payloads carry monotonic seq numbers + non-empty text.
    for i, (kind, data) in enumerate(events[:3], start=1):
        assert kind == "token"
        assert data["seq"] == i
        assert isinstance(data["text"], str) and data["text"]
    assert events[-1][1]["reason"] == "fake_complete"
    assert events[-1][1]["thread_id"] == thread_id


@pytest.mark.asyncio
async def test_run_emits_session_write_audit(
    runs_client: AsyncClient, audit_store: InMemoryAuditLogStore
) -> None:
    thread_id = await _create_session(runs_client)
    response = await runs_client.post(f"/v1/sessions/{thread_id}/runs", json={"input": "hi"})
    assert response.status_code == 200
    _ = response.text  # exhaust the stream

    page = await audit_store.query(AuditQuery(tenant_id=_DEFAULT_TENANT))
    run_events = [
        r
        for r in page.entries
        if r.action.value == "session:write"
        and r.resource_id == thread_id
        and r.details.get("stage") == "run.start"
    ]
    assert run_events, "expected a run.start audit row"
    assert run_events[0].details["input_len"] == 2


# ---------------------------------------------------------------------------
# error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_against_unknown_session_returns_404(runs_client: AsyncClient) -> None:
    response = await runs_client.post(
        "/v1/sessions/00000000-0000-0000-0000-000000000099/runs",
        json={},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_against_cancelled_session_returns_409(runs_client: AsyncClient) -> None:
    thread_id = await _create_session(runs_client)
    await runs_client.post(f"/v1/sessions/{thread_id}:cancel", json={})
    response = await runs_client.post(f"/v1/sessions/{thread_id}/runs", json={})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_run_against_paused_session_returns_409(runs_client: AsyncClient) -> None:
    thread_id = await _create_session(runs_client)
    await runs_client.post(f"/v1/sessions/{thread_id}:pause", json={})
    response = await runs_client.post(f"/v1/sessions/{thread_id}/runs", json={})
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# cancellation mid-stream — drive the inner generator directly so we can
# flip the token between iterations.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_stream_short_circuits_on_cancel() -> None:
    from uuid import uuid4

    from control_plane.api.runs import _fake_stream

    cancel_token = CancelToken()
    cancel_token.cancel()
    chunks: list[bytes] = [
        chunk
        async for chunk in _fake_stream(
            thread_id=uuid4(),
            cancel_token=cancel_token,
            token_delay_s=0.0,
        )
    ]
    assert len(chunks) == 1
    assert b"event: done" in chunks[0]
    assert b'"reason":"cancelled"' in chunks[0]


# ---------------------------------------------------------------------------
# Stream B acceptance: create agent → create session → run → done
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_b_full_acceptance_flow(runs_client: AsyncClient) -> None:
    """End-to-end happy path used as Stream B verification gate #1."""
    # 1. List the seeded agent.
    agents = await runs_client.get("/v1/agents")
    assert agents.status_code == 200
    assert agents.json()["data"]["total"] == 1

    # 2. Create a session bound to it.
    session_response = await runs_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    assert session_response.status_code == 201
    thread_id = session_response.json()["data"]["thread_id"]

    # 3. Trigger a run and read the SSE.
    run_response = await runs_client.post(
        f"/v1/sessions/{thread_id}/runs",
        json={"input": "review the PR"},
    )
    assert run_response.status_code == 200
    events = await _parse_sse(run_response.text)
    assert [e[0] for e in events] == ["token", "token", "token", "done"]
