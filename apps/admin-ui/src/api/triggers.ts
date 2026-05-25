/**
 * Triggers SDK — backed by ``/v1/triggers``.
 *
 * Stream H.1b PR 3. cron / webhook triggers tenant-scoped (Stream N
 * threads ``tenant_id=*`` for system_admin).
 */
import { getJson, withTenantScope, type TenantScope } from "./client";

export type TriggerKind = "cron" | "webhook";

export interface TriggerRecord {
  id: string;
  tenant_id: string;
  user_id: string | null;
  agent_name: string;
  agent_version: string;
  name: string;
  kind: TriggerKind;
  config: Record<string, unknown>;
  enabled: boolean;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface TriggerList {
  items: TriggerRecord[];
  total: number;
  cross_tenant: boolean;
}

export interface ListTriggersParams {
  tenantScope?: TenantScope;
  kind?: TriggerKind;
  enabled?: boolean;
  agentName?: string;
  limit?: number;
  offset?: number;
}

export async function listTriggers(
  params: ListTriggersParams = {},
): Promise<TriggerList> {
  const { tenantScope, kind, enabled, agentName, limit, offset } = params;
  const query = withTenantScope(
    { kind, enabled, agent_name: agentName, limit, offset },
    tenantScope,
  );
  return getJson<TriggerList>("/v1/triggers", { params: query });
}
