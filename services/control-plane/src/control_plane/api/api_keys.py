"""``/v1/service_accounts/{id}/api_keys`` + ``/v1/api_keys`` endpoints — Stream C.3."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from control_plane.api._authz import require
from control_plane.audit import emit
from control_plane.auth.api_key_verifier import mint_api_key
from helix_agent.common.observability import current_trace_id_hex
from helix_agent.persistence.auth import (
    ApiKeyStore,
    DuplicateApiKeyPrefixError,
    ServiceAccountStore,
)
from helix_agent.protocol import ApiKeyCreated, ApiKeyScope, AuditAction, Principal
from helix_agent.runtime.audit.logger import AuditLogger

logger = logging.getLogger("helix.control_plane.api.api_keys")


class CreateApiKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scopes: list[ApiKeyScope] = Field(default_factory=list)
    expires_at: datetime | None = None


def _get_keys(request: Request) -> ApiKeyStore:
    return request.app.state.api_key_repo  # type: ignore[no-any-return]


def _get_accounts(request: Request) -> ServiceAccountStore:
    return request.app.state.service_account_repo  # type: ignore[no-any-return]


def _get_audit(request: Request) -> AuditLogger:
    return request.app.state.audit_logger  # type: ignore[no-any-return]


def build_api_keys_router() -> APIRouter:
    router = APIRouter(tags=["api_keys"])

    @router.post(
        "/v1/service_accounts/{service_account_id}/api_keys",
        status_code=201,
    )
    async def create_api_key(
        service_account_id: UUID,
        payload: CreateApiKeyRequest,
        principal: Annotated[Principal, Depends(require("api_key", "write"))],
        keys: Annotated[ApiKeyStore, Depends(_get_keys)],
        accounts: Annotated[ServiceAccountStore, Depends(_get_accounts)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
    ) -> dict[str, object]:
        sa = await accounts.get(
            tenant_id=principal.tenant_id, service_account_id=service_account_id
        )
        if sa is None:
            raise HTTPException(status_code=404, detail="service_account not found")
        if not sa.is_active:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SERVICE_ACCOUNT_INACTIVE",
                    "message": "cannot mint API keys for an inactive service account",
                },
            )

        generated = mint_api_key(tenant_id=principal.tenant_id)
        # Retry once on prefix collision (probability ≈ 1/2^28; cheap belt).
        for attempt in range(2):
            try:
                key = await keys.create(
                    tenant_id=principal.tenant_id,
                    service_account_id=sa.id,
                    prefix=generated.prefix,
                    secret_hash=generated.secret_hash,
                    scopes=payload.scopes,
                    expires_at=payload.expires_at,
                    created_by=principal.subject_id,
                )
                break
            except DuplicateApiKeyPrefixError:
                if attempt == 1:
                    logger.warning("api_key.prefix_collision_retry_failed")
                    raise HTTPException(
                        status_code=500,
                        detail={"code": "INTERNAL_ERROR", "message": "regenerate API key"},
                    ) from None
                generated = mint_api_key(tenant_id=principal.tenant_id)
        await emit(
            audit,
            tenant_id=principal.tenant_id,
            actor_id=principal.subject_id,
            action=AuditAction.API_KEY_CREATE,
            resource_type="api_key",
            resource_id=str(key.id),
            trace_id=current_trace_id_hex(),
            details={
                "service_account_id": str(sa.id),
                "scopes": [s.value for s in payload.scopes],
            },
        )
        created = ApiKeyCreated.from_key(api_key=key, plaintext=generated.plaintext)
        return {"success": True, "data": created.model_dump(mode="json"), "error": None}

    @router.get("/v1/service_accounts/{service_account_id}/api_keys")
    async def list_api_keys(
        service_account_id: UUID,
        principal: Annotated[Principal, Depends(require("api_key", "read"))],
        keys: Annotated[ApiKeyStore, Depends(_get_keys)],
    ) -> dict[str, object]:
        items = await keys.list_by_service_account(
            tenant_id=principal.tenant_id, service_account_id=service_account_id
        )
        return {
            "success": True,
            "data": {"items": [k.model_dump(mode="json") for k in items], "total": len(items)},
            "error": None,
        }

    @router.delete("/v1/api_keys/{api_key_id}", status_code=204)
    async def revoke_api_key(
        api_key_id: UUID,
        principal: Annotated[Principal, Depends(require("api_key", "delete"))],
        keys: Annotated[ApiKeyStore, Depends(_get_keys)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
    ) -> None:
        ok = await keys.revoke(tenant_id=principal.tenant_id, api_key_id=api_key_id)
        if not ok:
            raise HTTPException(status_code=404, detail="api_key not found")
        await emit(
            audit,
            tenant_id=principal.tenant_id,
            actor_id=principal.subject_id,
            action=AuditAction.API_KEY_REVOKE,
            resource_type="api_key",
            resource_id=str(api_key_id),
            trace_id=current_trace_id_hex(),
        )

    return router
