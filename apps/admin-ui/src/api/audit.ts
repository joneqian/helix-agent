/**
 * Audit SDK — Stream H.4 PR 4.
 *
 * Backed by ``GET /v1/audit`` + ``GET /v1/audit/{id}`` (Stream H.4 PR 3).
 * Backend returns raw payloads (``JSONResponse(content={...})``), not
 * the ``{success, data, error}`` envelope — so this SDK goes through
 * ``apiClient`` directly (mirrors ``runs.ts`` + ``curation.ts``).
 *
 * Cursor pagination is **opaque base64** — callers pass ``next_cursor``
 * back verbatim, never parse it.
 */
import { apiClient, withTenantScope, type TenantScope } from "./client";

export type AuditResult = "success" | "denied" | "error";

export type ActorType = "user" | "service_account" | "system" | "agent";

export interface AuditEntry {
  id: number | null;
  tenant_id: string;
  actor_type: ActorType;
  actor_id: string;
  on_behalf_of: string | null;
  /** e.g. ``manifest:read``, ``role_binding:create``, ``audit:read``. */
  action: string;
  resource_type: string;
  resource_id: string | null;
  result: AuditResult;
  reason: string | null;
  ip: string | null;
  user_agent: string | null;
  request_id: string | null;
  trace_id: string | null;
  /** Already redactor-cleaned at write time; safe to render verbatim. */
  details: Record<string, unknown>;
  occurred_at: string | null;
}

export interface AuditList {
  items: AuditEntry[];
  next_cursor: string | null;
  has_more: boolean;
  /** ``"cross_tenant"`` for system_admin wildcard view; UUID otherwise. */
  applied_scope: string;
}

export interface ListAuditParams {
  tenantScope?: TenantScope;
  actorId?: string;
  action?: string;
  resourceType?: string;
  resourceId?: string;
  result?: AuditResult;
  /** ISO-8601 datetime; sent as a query string. */
  fromTs?: string;
  toTs?: string;
  cursor?: string | null;
  limit?: number;
}

export async function listAudit(params: ListAuditParams = {}): Promise<AuditList> {
  const {
    tenantScope,
    actorId,
    action,
    resourceType,
    resourceId,
    result,
    fromTs,
    toTs,
    cursor,
    limit,
  } = params;
  const query = withTenantScope(
    {
      actor_id: actorId,
      action,
      resource_type: resourceType,
      resource_id: resourceId,
      result,
      from_ts: fromTs,
      to_ts: toTs,
      cursor: cursor ?? undefined,
      limit,
    },
    tenantScope,
  );
  const response = await apiClient.get<AuditList>("/v1/audit", { params: query });
  return response.data;
}

export async function getAuditEntry(auditId: number): Promise<AuditEntry> {
  const response = await apiClient.get<AuditEntry>(`/v1/audit/${auditId}`);
  return response.data;
}
