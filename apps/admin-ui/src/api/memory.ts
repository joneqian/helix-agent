/**
 * Memory SDK — backed by ``/v1/memory`` (Stream K.K6).
 *
 * Stream H.1b PR 3 added list-only. Stream H.4 PR 2 fills in PATCH
 * (update content + kind, requires server-side embedder) and DELETE
 * (soft-delete with 30-day retention).
 *
 * Per-user scoping is enforced server-side — the caller's ``user_id``
 * is derived from their principal, not a query parameter. System_admin
 * via ``tenant_id=*`` cross-tenant aggregates across every user (note:
 * cross-tenant view intentionally drops the per-user binding so
 * platform admin sees the whole picture).
 */
import {
  apiClient,
  getJson,
  patchJson,
  withTenantScope,
  type TenantScope,
} from "./client";

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

export interface UpdateMemoryBody {
  content: string;
  /** Optional re-classification when the reviewer corrects the
   *  worker's auto-tag. Backend keeps the existing kind when omitted. */
  kind?: MemoryKind;
}

export async function updateMemory(
  memoryId: string,
  body: UpdateMemoryBody,
): Promise<MemoryItem> {
  return patchJson<MemoryItem>(
    `/v1/memory/${encodeURIComponent(memoryId)}`,
    body,
  );
}

/** DELETE returns 204 No Content — no body. */
export async function deleteMemory(memoryId: string): Promise<void> {
  await apiClient.delete(`/v1/memory/${encodeURIComponent(memoryId)}`);
}
