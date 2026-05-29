"""``/v1/platform/credentials`` — platform credential runtime management (Stream P).

system_admin-only CRUD over the platform provider/tool secret-ref overlay
(Mini-ADR P-11). Every handler:

* gates on ``principal.is_system_admin`` inline (platform-level; no RBAC
  ``tenant`` resource — same precedent as ``role_bindings.py`` / ``tenants.py``);
* runs the store reads/writes inside ``bypass_rls_session()`` because the rows
  are tenant-less;
* stores **refs only** in the catalog — never plaintext. A pasted raw key
  (``PlatformSecretWrite.value``, Stream Q) is encrypted into the SecretStore
  and only its generated ``secret://`` ref reaches the catalog (Mini-ADR
  Q-4/Q-6); an operator-supplied ``secret_ref`` is ref-validated (Mini-ADR P-8).

Naming: the storage layer is ``platform_secrets`` (harness blocks ``credentials``
paths); the HTTP surface keeps the design's ``/v1/platform/credentials`` path.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator, model_validator

from control_plane.api._authz import _principal
from control_plane.api.tenant_config import (
    _embedding_provider,
    _get_agent_spec_store,
    _provider_usage_counts,
    _tool_usage_counts,
)
from control_plane.audit import emit
from control_plane.platform_secrets import PlatformSecretsService
from control_plane.tenant_scope import bypass_rls_session
from helix_agent.common.observability import current_trace_id_hex
from helix_agent.persistence import PlatformSecretStore
from helix_agent.protocol import (
    PROVIDER_CATALOG,
    TOOL_CATALOG,
    AuditAction,
    Principal,
    Provider,
    Tool,
    validate_secret_ref,
)
from helix_agent.runtime.audit.logger import AuditLogger
from helix_agent.runtime.secret_store import SecretStore


class PlatformSecretWrite(BaseModel):
    """Write payload for a platform provider/tool credential — Stream Q (Q-4).

    Accepts **exactly one** of:

    * ``secret_ref`` — a ``secret://`` / ``kms://`` reference the operator
      manages out of band (the original Stream P flow); or
    * ``value`` — a raw key pasted in the web UI. The write path encrypts it
      via the SecretStore and stores only the generated ref in the catalog, so
      the catalog never holds a value (Mini-ADR Q-4/Q-6).

    ``value`` is a :class:`~pydantic.SecretStr` so it never renders in logs.
    """

    model_config = ConfigDict(extra="forbid")
    secret_ref: str | None = None
    value: SecretStr | None = None
    enabled: bool = True

    @field_validator("secret_ref")
    @classmethod
    def _check_ref(cls, value: str | None) -> str | None:
        return validate_secret_ref(value) if value is not None else None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> PlatformSecretWrite:
        if (self.secret_ref is None) == (self.value is None):
            msg = "provide exactly one of 'secret_ref' or 'value'"
            raise ValueError(msg)
        return self


def _get_store(request: Request) -> PlatformSecretStore:
    return request.app.state.platform_secret_store  # type: ignore[no-any-return]


def _get_secret_store(request: Request) -> SecretStore:
    return request.app.state.secret_store  # type: ignore[no-any-return]


def _get_service(request: Request) -> PlatformSecretsService:
    return request.app.state.platform_secrets_service  # type: ignore[no-any-return]


def _get_audit(request: Request) -> AuditLogger:
    return request.app.state.audit_logger  # type: ignore[no-any-return]


async def _resolve_write_ref(
    payload: PlatformSecretWrite, secret_store: SecretStore, *, name: str
) -> str:
    """Return the ref to store in the catalog.

    A pasted raw ``value`` is encrypted into the SecretStore under ``name`` and
    surfaced as ``secret://<name>``; the value never reaches the catalog or the
    audit row (Mini-ADR Q-4/Q-7). An operator-supplied ``secret_ref`` is
    returned as-is.
    """
    if payload.value is not None:
        await secret_store.put(name, payload.value.get_secret_value())
        return f"secret://{name}"
    if payload.secret_ref is None:
        # Unreachable: the model validator enforces exactly one of value /
        # secret_ref. Guard explicitly (not ``assert`` — stripped under -O).
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_SECRET_WRITE",
                "message": "provide exactly one of 'secret_ref' or 'value'",
            },
        )
    return payload.secret_ref


def _require_system_admin(principal: Principal) -> None:
    if not principal.is_system_admin:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PLATFORM_SCOPE_FORBIDDEN",
                "message": "only a system admin may manage platform credentials",
            },
        )


def _env_provider_refs(request: Request) -> dict[Provider, str]:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return {}
    return dict(settings.effective_platform_provider_credentials)


def _env_tool_refs(request: Request) -> dict[Tool, str]:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return {}
    return dict(settings.effective_platform_tool_credentials)


def build_platform_config_router() -> APIRouter:
    router = APIRouter(prefix="/v1/platform/credentials", tags=["platform_config"])

    @router.get("")
    async def get_platform_credentials(
        principal: Annotated[Principal, Depends(_principal)],
        store: Annotated[PlatformSecretStore, Depends(_get_store)],
        request: Request,
    ) -> dict[str, object]:
        """Full catalog view: per provider/tool → source (env/db/unset),
        secret_ref (effective; DB wins), enabled, used_by_agents (cross-tenant).
        Refs + flags only — no secret values."""
        _require_system_admin(principal)
        env_provs = _env_provider_refs(request)
        env_tools = _env_tool_refs(request)
        agent_store = _get_agent_spec_store(request)
        embedding_provider = _embedding_provider(request)
        async with bypass_rls_session():
            db_provs = {row.provider: row for row in await store.list_providers()}
            db_tools = {row.tool: row for row in await store.list_tools()}
            specs = (
                await agent_store.list_all_tenants(status=None, limit=1000)
                if agent_store is not None
                else []
            )
        prov_counts = _provider_usage_counts(specs, embedding_provider=embedding_provider)
        tool_counts = _tool_usage_counts(specs)
        providers = [
            {
                "provider": provider,
                "source": "db"
                if provider in db_provs
                else ("env" if provider in env_provs else "unset"),
                "secret_ref": (
                    db_provs[provider].secret_ref
                    if provider in db_provs
                    else env_provs.get(provider)
                ),
                "enabled": (
                    db_provs[provider].enabled if provider in db_provs else provider in env_provs
                ),
                "used_by_agents": prov_counts.get(provider, 0),
            }
            for provider in PROVIDER_CATALOG
        ]
        tools = [
            {
                "tool": tool,
                "source": "db" if tool in db_tools else ("env" if tool in env_tools else "unset"),
                "secret_ref": (
                    db_tools[tool].secret_ref if tool in db_tools else env_tools.get(tool)
                ),
                "enabled": db_tools[tool].enabled if tool in db_tools else tool in env_tools,
                "used_by_agents": tool_counts.get(tool, 0),
            }
            for tool in TOOL_CATALOG
        ]
        return {
            "success": True,
            "data": {"providers": providers, "tools": tools},
            "error": None,
        }

    @router.put("/providers/{provider}")
    async def upsert_provider(
        provider: str,
        payload: PlatformSecretWrite,
        principal: Annotated[Principal, Depends(_principal)],
        store: Annotated[PlatformSecretStore, Depends(_get_store)],
        service: Annotated[PlatformSecretsService, Depends(_get_service)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
        secret_store: Annotated[SecretStore, Depends(_get_secret_store)],
    ) -> dict[str, object]:
        _require_system_admin(principal)
        if provider not in PROVIDER_CATALOG:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "UNKNOWN_PROVIDER",
                    "message": f"provider {provider!r} not in catalog",
                },
            )
        secret_ref = await _resolve_write_ref(
            payload, secret_store, name=f"helix-agent/platform/llm/{provider}"
        )
        async with bypass_rls_session():
            row = await store.upsert_provider(
                provider=cast(Provider, provider),
                secret_ref=secret_ref,
                enabled=payload.enabled,
                actor_id=principal.subject_id,
            )
        service.invalidate()
        await _emit_platform_audit(
            audit,
            principal=principal,
            action=AuditAction.PLATFORM_PROVIDER_CREDENTIAL_UPSERT,
            key=provider,
            details={"enabled": payload.enabled, "secret_ref": secret_ref},
        )
        return {"success": True, "data": row.model_dump(mode="json"), "error": None}

    @router.put("/tools/{tool}")
    async def upsert_tool(
        tool: str,
        payload: PlatformSecretWrite,
        principal: Annotated[Principal, Depends(_principal)],
        store: Annotated[PlatformSecretStore, Depends(_get_store)],
        service: Annotated[PlatformSecretsService, Depends(_get_service)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
        secret_store: Annotated[SecretStore, Depends(_get_secret_store)],
    ) -> dict[str, object]:
        _require_system_admin(principal)
        if tool not in TOOL_CATALOG:
            raise HTTPException(
                status_code=422,
                detail={"code": "UNKNOWN_TOOL", "message": f"tool {tool!r} not in catalog"},
            )
        secret_ref = await _resolve_write_ref(
            payload, secret_store, name=f"helix-agent/platform/tool/{tool}"
        )
        async with bypass_rls_session():
            row = await store.upsert_tool(
                tool=cast(Tool, tool),
                secret_ref=secret_ref,
                enabled=payload.enabled,
                actor_id=principal.subject_id,
            )
        service.invalidate()
        await _emit_platform_audit(
            audit,
            principal=principal,
            action=AuditAction.PLATFORM_TOOL_CREDENTIAL_UPSERT,
            key=tool,
            details={"enabled": payload.enabled, "secret_ref": secret_ref},
        )
        return {"success": True, "data": row.model_dump(mode="json"), "error": None}

    @router.delete("/providers/{provider}", status_code=204)
    async def delete_provider(
        provider: str,
        principal: Annotated[Principal, Depends(_principal)],
        store: Annotated[PlatformSecretStore, Depends(_get_store)],
        service: Annotated[PlatformSecretsService, Depends(_get_service)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
        request: Request,
    ) -> None:
        _require_system_admin(principal)
        if provider in _env_provider_refs(request):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PLATFORM_CREDENTIAL_IN_USE",
                    "message": "provider is defined in env config; remove it from settings instead",
                },
            )
        agent_store = _get_agent_spec_store(request)
        embedding_provider = _embedding_provider(request)
        async with bypass_rls_session():
            specs = (
                await agent_store.list_all_tenants(status=None, limit=1000)
                if agent_store is not None
                else []
            )
            in_use = _provider_usage_counts(specs, embedding_provider=embedding_provider).get(
                cast(Provider, provider), 0
            )
            if in_use > 0:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "PLATFORM_CREDENTIAL_IN_USE",
                        "message": f"{in_use} agent(s) reference this provider; disable instead",
                    },
                )
            deleted = await store.delete_provider(cast(Provider, provider))
        if not deleted:
            raise HTTPException(status_code=404, detail="platform provider credential not found")
        service.invalidate()
        await _emit_platform_audit(
            audit,
            principal=principal,
            action=AuditAction.PLATFORM_PROVIDER_CREDENTIAL_DELETE,
            key=provider,
            details={},
        )

    @router.delete("/tools/{tool}", status_code=204)
    async def delete_tool(
        tool: str,
        principal: Annotated[Principal, Depends(_principal)],
        store: Annotated[PlatformSecretStore, Depends(_get_store)],
        service: Annotated[PlatformSecretsService, Depends(_get_service)],
        audit: Annotated[AuditLogger, Depends(_get_audit)],
        request: Request,
    ) -> None:
        _require_system_admin(principal)
        if tool in _env_tool_refs(request):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PLATFORM_CREDENTIAL_IN_USE",
                    "message": "tool is defined in env config; remove it from settings instead",
                },
            )
        agent_store = _get_agent_spec_store(request)
        async with bypass_rls_session():
            specs = (
                await agent_store.list_all_tenants(status=None, limit=1000)
                if agent_store is not None
                else []
            )
            in_use = _tool_usage_counts(specs).get(cast(Tool, tool), 0)
            if in_use > 0:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "PLATFORM_CREDENTIAL_IN_USE",
                        "message": f"{in_use} agent(s) reference this tool; disable instead",
                    },
                )
            deleted = await store.delete_tool(cast(Tool, tool))
        if not deleted:
            raise HTTPException(status_code=404, detail="platform tool credential not found")
        service.invalidate()
        await _emit_platform_audit(
            audit,
            principal=principal,
            action=AuditAction.PLATFORM_TOOL_CREDENTIAL_DELETE,
            key=tool,
            details={},
        )

    return router


async def _emit_platform_audit(
    audit: AuditLogger,
    *,
    principal: Principal,
    action: AuditAction,
    key: str,
    details: dict[str, object],
) -> None:
    # Platform credentials are tenant-less; the audit row is filed under the
    # acting admin's home tenant (same convention as platform-scope role
    # bindings). Emitted outside the bypass block so it lands under the
    # request's normal RLS context.
    await emit(
        audit,
        tenant_id=principal.tenant_id,
        actor_id=principal.subject_id,
        action=action,
        resource_type="platform_credential",
        resource_id=key,
        trace_id=current_trace_id_hex(),
        details=details,
    )
