"""Per-tenant runtime configuration schemas — Stream C.7.

Distinct from :class:`helix_agent.protocol.agent_spec.TenantConfig`
(which is an *agent manifest* fragment). The schemas here back the
``tenant_config`` table from migration 0007 and the C.7 admin
``GET / PUT /v1/tenants/{tid}/config`` endpoints.

Subsystems/15 § 6 + STREAM-C-DESIGN § 2.8 set the contract:

* ``model_credentials_ref`` is ``{<provider>: "kms://..."}``. The
  control plane stores only the URI; F.6 ``SecretStore`` resolves it
  on the LLM-call hot path.
* ``mcp_allowlist`` controls which MCP servers the tenant may
  connect to (Stream E).
* ``rate_limit_override`` is consumed by :class:`TenantRateLimitMiddleware`
  in M1; in M0 it lands here as forward-compatible storage.
* ``pii_fields`` feeds the Stream D PII redactor.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "MemoryRecallMode",
    "TenantConfigPatch",
    "TenantConfigRecord",
    "TenantPlan",
    "TriggerFireScanMode",
]

# Capability Uplift Sprint #1 — Mini-ADR U-2.
# ``warn`` is the platform-wide default: a fire-time injection match
# emits ``TRIGGER_PROMPT_INJECTION_WARN`` and the run still starts.
# High-compliance tenants opt in to ``block``: a match emits
# ``TRIGGER_PROMPT_INJECTION_BLOCKED`` and the run does not start.
TriggerFireScanMode = Literal["warn", "block"]

# Capability Uplift Sprint #6 — Mini-ADR U-5.
# ``hybrid`` is the platform-wide default: ``MemoryStore.retrieve()``
# runs vector + Postgres full-text and fuses via Reciprocal Rank Fusion
# (k=60). Tenants can opt out to ``vector`` to keep the legacy pure-
# pgvector cosine path (e.g. for workloads where the eval baseline
# regressed against expectations).
MemoryRecallMode = Literal["hybrid", "vector"]


class TenantPlan(StrEnum):
    """Pricing tier label. M0 informational only; M1 derives default quotas."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


_RETENTION_MIN_DAYS = 1
_RETENTION_MAX_DAYS = 3650

# Capability Uplift Sprint #4 — Mini-ADR U-28.
# Curator threshold bounds. Defaults 30 / 90 derive from external
# skill-marketplace observations; M1-K J.7b-1 will revisit after 2-4
# weeks of real agent-self-create data. The 365 / 730 day ceilings
# guard against accidental "effectively disabled" settings — anything
# longer than 1-2 years and the Curator stops being useful infrastructure.
_SKILL_STALE_MIN_DAYS = 1
_SKILL_STALE_MAX_DAYS = 365
_SKILL_ARCHIVE_MIN_DAYS = 2
_SKILL_ARCHIVE_MAX_DAYS = 730


class TenantConfigRecord(BaseModel):
    """One row of ``tenant_config`` as exposed by the admin API."""

    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    display_name: str
    plan: TenantPlan = TenantPlan.FREE
    model_credentials_ref: dict[str, str] = Field(default_factory=dict)
    mcp_allowlist: list[str] = Field(default_factory=list)
    rate_limit_override: dict[str, Any] = Field(default_factory=dict)
    pii_fields: list[str] = Field(default_factory=list)
    # E.8: glob patterns the HTTP tool may call (e.g. ``"https://api.github.com/*"``).
    # Default ``[]`` ↔ deny-all so a freshly-provisioned tenant is safe.
    http_tool_allowlist: list[str] = Field(default_factory=list)
    # E.9: MCP server configs.
    # Shape: ``[{"name": str, "command": [str, ...], "env": {str: str}}]``.
    # NOT used to launch servers in M0 — STREAM-E-DESIGN Mini-ADR E-17:
    # ``command`` is operator-controlled (subprocess RCE risk), so the
    # platform's MCP servers come from ``mcp_servers_config_file``. The
    # M1 role of this per-tenant field is enablement / filtering over
    # the platform pool, not command specification.
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    # D.3: per-tenant retention. Bounded ranges mirror the DB CHECK
    # constraints in migration 0010 so admin clients fail fast rather
    # than tripping a 23514 at write time.
    audit_retention_days: int = Field(default=90, ge=_RETENTION_MIN_DAYS, le=_RETENTION_MAX_DAYS)
    event_log_retention_days: int = Field(
        default=30, ge=_RETENTION_MIN_DAYS, le=_RETENTION_MAX_DAYS
    )
    # Capability Uplift Sprint #1 — Mini-ADR U-2.
    trigger_fire_scan_mode: TriggerFireScanMode = "warn"
    # Capability Uplift Sprint #6 — Mini-ADR U-5.
    memory_recall_mode: MemoryRecallMode = "hybrid"
    # Capability Uplift Sprint #4 — Mini-ADR U-28. Curator state-
    # machine thresholds. Cross-field invariant ``archive_days > stale_days``
    # is enforced by the model validator below + a DB CHECK in migration
    # 0044.
    skill_stale_days: int = Field(default=30, ge=_SKILL_STALE_MIN_DAYS, le=_SKILL_STALE_MAX_DAYS)
    skill_archive_days: int = Field(
        default=90, ge=_SKILL_ARCHIVE_MIN_DAYS, le=_SKILL_ARCHIVE_MAX_DAYS
    )
    created_at: datetime
    updated_at: datetime
    updated_by: str

    @model_validator(mode="after")
    def _skill_archive_strictly_greater_than_stale(self) -> TenantConfigRecord:
        if self.skill_archive_days <= self.skill_stale_days:
            msg = (
                f"skill_archive_days ({self.skill_archive_days}) must be strictly "
                f"greater than skill_stale_days ({self.skill_stale_days})"
            )
            raise ValueError(msg)
        return self


class TenantConfigPatch(BaseModel):
    """Admin ``PUT /v1/tenants/{tid}/config`` payload.

    All fields are optional so admins can update one knob at a time.
    Empty containers are *meaningful* values (e.g. clear the
    allowlist); to leave a field untouched, omit the key entirely.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    display_name: str | None = None
    plan: TenantPlan | None = None
    model_credentials_ref: dict[str, str] | None = None
    mcp_allowlist: list[str] | None = None
    rate_limit_override: dict[str, Any] | None = None
    pii_fields: list[str] | None = None
    http_tool_allowlist: list[str] | None = None
    mcp_servers: list[dict[str, Any]] | None = None
    audit_retention_days: int | None = Field(
        default=None, ge=_RETENTION_MIN_DAYS, le=_RETENTION_MAX_DAYS
    )
    event_log_retention_days: int | None = Field(
        default=None, ge=_RETENTION_MIN_DAYS, le=_RETENTION_MAX_DAYS
    )
    # Capability Uplift Sprint #1 — Mini-ADR U-2.
    trigger_fire_scan_mode: TriggerFireScanMode | None = None
    # Capability Uplift Sprint #6 — Mini-ADR U-5.
    memory_recall_mode: MemoryRecallMode | None = None
    # Capability Uplift Sprint #4 — Mini-ADR U-28. Curator threshold
    # patch. The cross-field invariant is enforced by the service
    # layer when applying the patch (it has the merged record), not
    # here — a patch that only carries one of the two days fields is
    # legal in isolation.
    skill_stale_days: int | None = Field(
        default=None, ge=_SKILL_STALE_MIN_DAYS, le=_SKILL_STALE_MAX_DAYS
    )
    skill_archive_days: int | None = Field(
        default=None, ge=_SKILL_ARCHIVE_MIN_DAYS, le=_SKILL_ARCHIVE_MAX_DAYS
    )
