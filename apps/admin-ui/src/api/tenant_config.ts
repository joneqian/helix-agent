/**
 * Tenant Config SDK — backed by ``/v1/tenants/{tenant_id}/config``
 * (Stream C.7).
 *
 * **Tenant-scoped only** (same shape as tenant_quotas). Backend
 * returns the standard ``{success, data, error}`` envelope.
 *
 * ETag concurrency: backend has none in M0 — PUT is last-writer-wins.
 * M1 will add ``If-Match``; until then the UI surfaces a soft
 * "Reload to see latest" hint after every save, not a 412.
 */
import { getJson, putJson } from "./client";

export type TenantPlan = "free" | "pro" | "enterprise";

export interface TenantConfigRecord {
  tenant_id: string;
  display_name: string;
  plan: TenantPlan;
  model_credentials_ref: Record<string, string>;
  mcp_allowlist: string[];
  rate_limit_override: Record<string, unknown>;
  pii_fields: string[];
  http_tool_allowlist: string[];
  mcp_servers: Record<string, unknown>[];
  audit_retention_days: number;
  event_log_retention_days: number;
  created_at: string;
  updated_at: string;
  updated_by: string;
}

export interface TenantConfigPatchBody {
  display_name?: string;
  plan?: TenantPlan;
  model_credentials_ref?: Record<string, string>;
  mcp_allowlist?: string[];
  rate_limit_override?: Record<string, unknown>;
  pii_fields?: string[];
  http_tool_allowlist?: string[];
  mcp_servers?: Record<string, unknown>[];
  audit_retention_days?: number;
  event_log_retention_days?: number;
}

export async function getTenantConfig(tenantId: string): Promise<TenantConfigRecord> {
  return getJson<TenantConfigRecord>(
    `/v1/tenants/${encodeURIComponent(tenantId)}/config`,
  );
}

export async function upsertTenantConfig(
  tenantId: string,
  body: TenantConfigPatchBody,
): Promise<TenantConfigRecord> {
  return putJson<TenantConfigRecord>(
    `/v1/tenants/${encodeURIComponent(tenantId)}/config`,
    body,
  );
}
