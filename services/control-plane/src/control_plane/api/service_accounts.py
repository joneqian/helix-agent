"""``/v1/service_accounts`` admin endpoints — Stream C.3."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from control_plane.api._authz import require
from control_plane.audit import emit
from helix_agent.common.observability import current_trace_id_hex
from helix_agent.persistence.auth import (
    DuplicateServiceAccountError,
    ServiceAccountStore,
)
from helix_agent.protocol import AuditAction, Principal, ServiceAccount
from helix_agent.runtime.audit.logger import AuditLogger

logger = logging.getLogger("helix.control_plane.api.service_accounts")


class CreateServiceAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)


class ServiceAccountListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ServiceAccount]
    total: int


def _get_repo(request: Request) -> ServiceAccountStore:
    return request.app.state.service_account_repo  # type: ignore[no-any-return]


def _get_audit(request: Request) -> AuditLogger:
    return request.app.state.audit_logger  # type: ignore[no-any-return]


def build_service_accounts_router() -> APIRouter:
    router = APIRouter(prefix="/v1/service_accounts", tags=["service_accounts"])

    @router.post("", status_code=201)
    async def create_service_account(
        payload: CreateServiceAccountRequest,
        principal: Annotated[Principal, Depends(require("service_account", "write"))],
        repo: Annotated[ServiceAccountStore, Depends(_get_repo)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
    ) -> dict[str, object]:
        try:
            sa = await repo.create(
                tenant_id=principal.tenant_id,
                name=payload.name,
                description=payload.description,
                created_by=principal.subject_id,
            )
        except DuplicateServiceAccountError as exc:
            # ``name`` is a reserved LogRecord attribute — use a namespaced
            # key so the structured-log formatter never trips a KeyError.
            logger.info(
                "service_account.create.duplicate",
                extra={"sa_name": payload.name},
            )
            raise HTTPException(
                status_code=409,
                detail={"code": "SERVICE_ACCOUNT_DUPLICATE", "message": "name already taken"},
            ) from exc
        await emit(
            audit,
            tenant_id=principal.tenant_id,
            actor_id=principal.subject_id,
            action=AuditAction.SERVICE_ACCOUNT_CREATE,
            resource_type="service_account",
            resource_id=str(sa.id),
            trace_id=current_trace_id_hex(),
            details={"name": sa.name},
        )
        return {"success": True, "data": sa.model_dump(mode="json"), "error": None}

    @router.get("")
    async def list_service_accounts(
        principal: Annotated[Principal, Depends(require("service_account", "read"))],
        repo: Annotated[ServiceAccountStore, Depends(_get_repo)],
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, object]:
        items = await repo.list_by_tenant(tenant_id=principal.tenant_id, limit=limit, offset=offset)
        body = ServiceAccountListResponse(items=items, total=len(items))
        return {"success": True, "data": body.model_dump(mode="json"), "error": None}

    @router.delete("/{service_account_id}", status_code=204)
    async def delete_service_account(
        service_account_id: UUID,
        principal: Annotated[Principal, Depends(require("service_account", "delete"))],
        repo: Annotated[ServiceAccountStore, Depends(_get_repo)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
    ) -> None:
        removed = await repo.delete(
            tenant_id=principal.tenant_id, service_account_id=service_account_id
        )
        if not removed:
            raise HTTPException(status_code=404, detail="service_account not found")
        await emit(
            audit,
            tenant_id=principal.tenant_id,
            actor_id=principal.subject_id,
            action=AuditAction.SERVICE_ACCOUNT_DELETE,
            resource_type="service_account",
            resource_id=str(service_account_id),
            trace_id=current_trace_id_hex(),
        )

    return router
