/**
 * Memory SDK — backed by ``/v1/memory`` (Stream K.K6).
 *
 * Stream H.1b PR 3. Per-user scoping is enforced server-side — the
 * caller's ``user_id`` is derived from their principal, not a query
 * parameter. System_admin via ``tenant_id=*`` cross-tenant aggregates
 * across every user.
 */
import { getJson, withTenantScope, type TenantScope } from "./client";

export type MemoryKind = "fact" | "episodic";

export interface MemoryItem {
  id: string;
  tenant_id: string;
  user_id: string;
  kind: MemoryKind;
  content: string;
  created_at: string;
}

export interface MemoryList {
  items: MemoryItem[];
  total: number;
  cross_tenant: boolean;
}

export interface ListMemoriesParams {
  tenantScope?: TenantScope;
  kind?: MemoryKind;
  limit?: number;
}

export async function listMemories(
  params: ListMemoriesParams = {},
): Promise<MemoryList> {
  const { tenantScope, kind, limit } = params;
  const query = withTenantScope({ kind, limit }, tenantScope);
  return getJson<MemoryList>("/v1/memory", { params: query });
}
