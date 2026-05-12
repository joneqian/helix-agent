"""End-to-end tests for ``/v1/sessions`` CRUD + lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from control_plane.app import create_app
from control_plane.audit import build_default_audit_logger
from control_plane.settings import DEFAULT_DEV_TENANT_ID, Settings
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
async def session_client(audit_store: InMemoryAuditLogStore) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        env="dev",
        auth_mode="dev",
        rate_limit_burst=10_000,
        rate_limit_per_second=10_000.0,
    )
    app = create_app(settings=settings, audit_logger=build_default_audit_logger(audit_store))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://control-plane.test") as client:
        # Seed the agent so /v1/sessions can find it.
        await client.post("/v1/agents", json={"manifest_yaml": _AGENT_YAML})
        yield client


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_creates_session_for_known_agent(
    session_client: AsyncClient, audit_store: InMemoryAuditLogStore
) -> None:
    response = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    assert response.status_code == 201
    meta = response.json()["data"]
    assert meta["agent_name"] == "code-reviewer"
    assert meta["status"] == "active"
    assert meta["thread_id"]
    page = await audit_store.query(AuditQuery(tenant_id=_DEFAULT_TENANT))
    assert any(r.action.value == "session:write" for r in page.entries)


@pytest.mark.asyncio
async def test_post_rejects_unknown_agent(session_client: AsyncClient) -> None:
    response = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "no-such", "agent_version": "9.9.9"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AGENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_post_rejects_deleted_agent(session_client: AsyncClient) -> None:
    # Soft-delete the seeded agent first.
    await session_client.delete("/v1/agents/code-reviewer/1.0.0")
    response = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AGENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_single_session(session_client: AsyncClient) -> None:
    create = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    thread_id = create.json()["data"]["thread_id"]
    response = await session_client.get(f"/v1/sessions/{thread_id}")
    assert response.status_code == 200
    assert response.json()["data"]["thread_id"] == thread_id


@pytest.mark.asyncio
async def test_get_returns_404_for_unknown(session_client: AsyncClient) -> None:
    response = await session_client.get("/v1/sessions/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_filters_by_status(session_client: AsyncClient) -> None:
    for _ in range(3):
        await session_client.post(
            "/v1/sessions",
            json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
        )
    response = await session_client.get("/v1/sessions?status=active")
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 3


# ---------------------------------------------------------------------------
# pause / resume / cancel state machine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_then_resume(session_client: AsyncClient) -> None:
    create = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    tid = create.json()["data"]["thread_id"]
    pause = await session_client.post(f"/v1/sessions/{tid}:pause", json={})
    assert pause.status_code == 200
    assert pause.json()["data"]["status"] == "paused"

    resume = await session_client.post(f"/v1/sessions/{tid}:resume", json={"reason": "ack"})
    assert resume.status_code == 200
    assert resume.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_resume_from_active_returns_409(session_client: AsyncClient) -> None:
    create = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    tid = create.json()["data"]["thread_id"]
    response = await session_client.post(f"/v1/sessions/{tid}:resume", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_STATE_CONFLICT"


@pytest.mark.asyncio
async def test_pause_terminal_session_returns_409(session_client: AsyncClient) -> None:
    create = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    tid = create.json()["data"]["thread_id"]
    await session_client.post(f"/v1/sessions/{tid}:cancel", json={})
    response = await session_client.post(f"/v1/sessions/{tid}:pause", json={})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cancel_emits_session_cancel_audit(
    session_client: AsyncClient, audit_store: InMemoryAuditLogStore
) -> None:
    create = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    tid = create.json()["data"]["thread_id"]
    response = await session_client.post(
        f"/v1/sessions/{tid}:cancel", json={"reason": "user_abort"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "cancelled"

    page = await audit_store.query(AuditQuery(tenant_id=_DEFAULT_TENANT))
    assert any(r.action.value == "session:cancel" and r.resource_id == tid for r in page.entries)


@pytest.mark.asyncio
async def test_cancel_paused_session_succeeds(session_client: AsyncClient) -> None:
    create = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
    )
    tid = create.json()["data"]["thread_id"]
    await session_client.post(f"/v1/sessions/{tid}:pause", json={})
    response = await session_client.post(f"/v1/sessions/{tid}:cancel", json={})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_transition_404_for_unknown_thread(session_client: AsyncClient) -> None:
    response = await session_client.post(
        "/v1/sessions/00000000-0000-0000-0000-000000000099:pause",
        json={},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_other_tenant_cannot_see_session(session_client: AsyncClient) -> None:
    create = await session_client.post(
        "/v1/sessions",
        json={"agent_name": "code-reviewer", "agent_version": "1.0.0"},
        headers={"X-Helix-Tenant": str(_DEFAULT_TENANT)},
    )
    tid = create.json()["data"]["thread_id"]
    other = "11111111-1111-1111-1111-111111111111"
    response = await session_client.get(
        f"/v1/sessions/{tid}",
        headers={"X-Helix-Tenant": other},
    )
    assert response.status_code == 404
