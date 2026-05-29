"""Endpoint tests for ``/v1/platform/credentials`` — Stream P (P-11/P-12)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from control_plane.app import create_app
from control_plane.auth import JWTVerifier
from control_plane.settings import Settings
from helix_agent.common.lifecycle import Lifecycle
from helix_agent.protocol import Role
from tests.auth_fixtures import make_test_jwt


async def _seed_admin(app: object) -> UUID:
    sys_admin_id = uuid4()
    await app.state.role_binding_repo.create(  # type: ignore[attr-defined]
        subject_type="user",
        subject_id=sys_admin_id,
        tenant_id=None,
        role=Role.SYSTEM_ADMIN,
        platform_scope=True,
        granted_by="seed",
    )
    return sys_admin_id


def _headers(subject: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_test_jwt(tenant_id=uuid4(), subject=str(subject))}"}


@pytest.fixture
async def admin_client(
    settings: Settings,
    lifecycle: Lifecycle,
    jwt_verifier: JWTVerifier,
) -> AsyncIterator[tuple[AsyncClient, UUID]]:
    app = create_app(settings=settings, lifecycle=lifecycle, jwt_verifier=jwt_verifier)
    sys_admin_id = await _seed_admin(app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://control-plane.test") as client:
        yield client, sys_admin_id


@pytest.mark.asyncio
async def test_non_admin_forbidden(admin_client: tuple[AsyncClient, UUID]) -> None:
    client, _ = admin_client
    resp = await client.get("/v1/platform/credentials", headers=_headers(uuid4()))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "PLATFORM_SCOPE_FORBIDDEN"


@pytest.mark.asyncio
async def test_get_lists_full_catalog(admin_client: tuple[AsyncClient, UUID]) -> None:
    client, admin = admin_client
    resp = await client.get("/v1/platform/credentials", headers=_headers(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    provs = {p["provider"]: p for p in data["providers"]}
    assert "anthropic" in provs  # full catalog rendered
    assert provs["anthropic"]["source"] == "unset"  # nothing configured yet
    assert provs["anthropic"]["secret_ref"] is None
    assert {t["tool"] for t in data["tools"]} == {"web_search"}


@pytest.mark.asyncio
async def test_put_provider_then_get_reflects_db_source(
    admin_client: tuple[AsyncClient, UUID],
) -> None:
    client, admin = admin_client
    put = await client.put(
        "/v1/platform/credentials/providers/anthropic",
        json={"secret_ref": "kms://platform/anthropic", "enabled": True},
        headers=_headers(admin),
    )
    assert put.status_code == 200, put.text
    assert put.json()["data"]["secret_ref"] == "kms://platform/anthropic"

    got = await client.get("/v1/platform/credentials", headers=_headers(admin))
    row = next(p for p in got.json()["data"]["providers"] if p["provider"] == "anthropic")
    assert row["source"] == "db"
    assert row["secret_ref"] == "kms://platform/anthropic"
    assert row["enabled"] is True


@pytest.mark.asyncio
async def test_put_unknown_provider_422(admin_client: tuple[AsyncClient, UUID]) -> None:
    client, admin = admin_client
    resp = await client.put(
        "/v1/platform/credentials/providers/not-a-provider",
        json={"secret_ref": "kms://x"},
        headers=_headers(admin),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "UNKNOWN_PROVIDER"


@pytest.mark.asyncio
async def test_put_plaintext_ref_rejected(admin_client: tuple[AsyncClient, UUID]) -> None:
    client, admin = admin_client
    resp = await client.put(
        "/v1/platform/credentials/providers/anthropic",
        json={"secret_ref": "sk-ant-plaintext"},
        headers=_headers(admin),
    )
    assert resp.status_code == 422  # PlatformSecretUpsert ref validator


@pytest.mark.asyncio
async def test_delete_provider_204_then_404(admin_client: tuple[AsyncClient, UUID]) -> None:
    client, admin = admin_client
    await client.put(
        "/v1/platform/credentials/providers/openai",
        json={"secret_ref": "kms://openai", "enabled": True},
        headers=_headers(admin),
    )
    first = await client.delete(
        "/v1/platform/credentials/providers/openai", headers=_headers(admin)
    )
    assert first.status_code == 204
    second = await client.delete(
        "/v1/platform/credentials/providers/openai", headers=_headers(admin)
    )
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_delete_env_defined_provider_409(
    settings: Settings,
    lifecycle: Lifecycle,
    jwt_verifier: JWTVerifier,
) -> None:
    settings = settings.model_copy(
        update={
            "supported_providers": ["anthropic"],
            "platform_provider_credentials": {"anthropic": "secret://env-anthropic"},
        }
    )
    app = create_app(settings=settings, lifecycle=lifecycle, jwt_verifier=jwt_verifier)
    admin = await _seed_admin(app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://control-plane.test") as client:
        resp = await client.delete(
            "/v1/platform/credentials/providers/anthropic", headers=_headers(admin)
        )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "PLATFORM_CREDENTIAL_IN_USE"
