"""End-to-end tests for ``/v1/service_accounts``, ``/v1/api_keys``,
``/v1/role_bindings`` admin endpoints — Stream C.3.

Tests piggy-back on the existing in-memory app fixture from conftest,
issuing JWTs with the appropriate role claim. The API-key bearer is
also exercised end-to-end: after creating a key via the admin API we
turn around and use it to call ``/v1/agents`` (which permits any
authenticated principal in M0).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from control_plane.app import create_app
from control_plane.audit import build_default_audit_logger
from control_plane.settings import DEFAULT_DEV_TENANT_ID, Settings
from helix_agent.persistence.audit_log import InMemoryAuditLogStore
from helix_agent.protocol import AuditAction, AuditQuery
from tests.auth_fixtures import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    build_test_jwt_verifier,
    make_test_jwt,
)

_TENANT = DEFAULT_DEV_TENANT_ID


@pytest.fixture
def audit_store() -> InMemoryAuditLogStore:
    return InMemoryAuditLogStore()


def _admin_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + make_test_jwt(tenant_id=_TENANT, subject="admin-user", roles=("admin",))
    }


def _viewer_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + make_test_jwt(tenant_id=_TENANT, subject="viewer-user", roles=("viewer",))
    }


@pytest.fixture
async def admin_client(
    audit_store: InMemoryAuditLogStore,
) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        env="dev",
        auth_mode="dev",
        rate_limit_burst=10_000,
        rate_limit_per_second=10_000.0,
        oidc_issuer=TEST_ISSUER,
        oidc_audience=[TEST_AUDIENCE],
    )
    app = create_app(
        settings=settings,
        audit_logger=build_default_audit_logger(audit_store),
        jwt_verifier=build_test_jwt_verifier(),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://control-plane.test") as client:
        yield client


# ---------------------------------------------------------------------------
# /v1/service_accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_create_and_list_service_accounts(
    admin_client: AsyncClient, audit_store: InMemoryAuditLogStore
) -> None:
    create = await admin_client.post(
        "/v1/service_accounts",
        json={"name": "ingestion-bot", "description": "automated ingestion"},
        headers=_admin_headers(),
    )
    assert create.status_code == 201
    sa = create.json()["data"]
    assert sa["name"] == "ingestion-bot"

    listing = await admin_client.get("/v1/service_accounts", headers=_admin_headers())
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) == 1

    page = await audit_store.query(AuditQuery(tenant_id=_TENANT))
    assert any(
        r.action is AuditAction.SERVICE_ACCOUNT_CREATE and r.resource_id == sa["id"]
        for r in page.entries
    )


@pytest.mark.asyncio
async def test_duplicate_service_account_returns_409(admin_client: AsyncClient) -> None:
    await admin_client.post(
        "/v1/service_accounts",
        json={"name": "dup", "description": ""},
        headers=_admin_headers(),
    )
    second = await admin_client.post(
        "/v1/service_accounts",
        json={"name": "dup", "description": ""},
        headers=_admin_headers(),
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_viewer_cannot_create_service_account(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/v1/service_accounts",
        json={"name": "denied", "description": ""},
        headers=_viewer_headers(),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_delete_service_account(admin_client: AsyncClient) -> None:
    create = await admin_client.post(
        "/v1/service_accounts",
        json={"name": "to-delete", "description": ""},
        headers=_admin_headers(),
    )
    sa_id = create.json()["data"]["id"]
    deleted = await admin_client.delete(f"/v1/service_accounts/{sa_id}", headers=_admin_headers())
    assert deleted.status_code == 204


# ---------------------------------------------------------------------------
# /v1/service_accounts/{id}/api_keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_mint_api_key_and_then_use_it(
    admin_client: AsyncClient, audit_store: InMemoryAuditLogStore
) -> None:
    sa = (
        await admin_client.post(
            "/v1/service_accounts",
            json={"name": "robot", "description": ""},
            headers=_admin_headers(),
        )
    ).json()["data"]

    create_key = await admin_client.post(
        f"/v1/service_accounts/{sa['id']}/api_keys",
        json={"scopes": ["admin"], "expires_at": None},
        headers=_admin_headers(),
    )
    assert create_key.status_code == 201
    body = create_key.json()["data"]
    plaintext = body["plaintext"]
    assert plaintext.startswith("aforge_pat_")
    # Plaintext is only returned this once.
    assert "plaintext" in body
    # The key row mirrors the SA.
    assert body["api_key"]["service_account_id"] == sa["id"]

    # Now turn around and use the API key to authenticate to a non-admin route.
    response = await admin_client.get(
        "/v1/agents", headers={"Authorization": f"Bearer {plaintext}"}
    )
    assert response.status_code == 200

    page = await audit_store.query(AuditQuery(tenant_id=_TENANT))
    assert any(r.action is AuditAction.API_KEY_CREATE for r in page.entries)


@pytest.mark.asyncio
async def test_create_api_key_for_unknown_sa_returns_404(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        f"/v1/service_accounts/{uuid4()}/api_keys",
        json={"scopes": ["read"]},
        headers=_admin_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_revoked_api_key_no_longer_authenticates(
    admin_client: AsyncClient,
) -> None:
    sa = (
        await admin_client.post(
            "/v1/service_accounts",
            json={"name": "to-revoke", "description": ""},
            headers=_admin_headers(),
        )
    ).json()["data"]
    create_key = await admin_client.post(
        f"/v1/service_accounts/{sa['id']}/api_keys",
        json={"scopes": ["admin"]},
        headers=_admin_headers(),
    )
    body = create_key.json()["data"]
    key_id = body["api_key"]["id"]
    plaintext = body["plaintext"]

    # Pre-revoke: works.
    pre = await admin_client.get("/v1/agents", headers={"Authorization": f"Bearer {plaintext}"})
    assert pre.status_code == 200

    # Revoke.
    revoked = await admin_client.delete(f"/v1/api_keys/{key_id}", headers=_admin_headers())
    assert revoked.status_code == 204

    # Post-revoke: 401.
    post = await admin_client.get("/v1/agents", headers={"Authorization": f"Bearer {plaintext}"})
    assert post.status_code == 401


# ---------------------------------------------------------------------------
# /v1/role_bindings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_grant_and_revoke_role_binding(
    admin_client: AsyncClient,
) -> None:
    subject_id = uuid4()
    create = await admin_client.post(
        "/v1/role_bindings",
        json={
            "subject_type": "service_account",
            "subject_id": str(subject_id),
            "role": "operator",
        },
        headers=_admin_headers(),
    )
    assert create.status_code == 201
    binding = create.json()["data"]
    assert binding["role"] == "operator"

    listing = await admin_client.get("/v1/role_bindings", headers=_admin_headers())
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1

    deleted = await admin_client.delete(
        f"/v1/role_bindings/{binding['id']}", headers=_admin_headers()
    )
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_duplicate_role_binding_returns_409(admin_client: AsyncClient) -> None:
    subject_id = uuid4()
    payload = {
        "subject_type": "user",
        "subject_id": str(subject_id),
        "role": "viewer",
    }
    await admin_client.post("/v1/role_bindings", json=payload, headers=_admin_headers())
    second = await admin_client.post("/v1/role_bindings", json=payload, headers=_admin_headers())
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_viewer_cannot_grant_roles(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/v1/role_bindings",
        json={
            "subject_type": "user",
            "subject_id": str(uuid4()),
            "role": "admin",
        },
        headers=_viewer_headers(),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Cross-tenant guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_cannot_see_other_tenants_service_accounts(
    admin_client: AsyncClient,
) -> None:
    await admin_client.post(
        "/v1/service_accounts",
        json={"name": "tenant-a-sa", "description": ""},
        headers=_admin_headers(),
    )
    other_tenant = UUID("11111111-1111-1111-1111-111111111111")
    other_jwt = make_test_jwt(tenant_id=other_tenant, subject="other-admin", roles=("admin",))
    listing = await admin_client.get(
        "/v1/service_accounts",
        headers={"Authorization": f"Bearer {other_jwt}"},
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 0
