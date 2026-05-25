/**
 * Skills SDK — backed by ``/v1/skills``.
 *
 * Stream H.1b PR 3. Skills are tenant-scoped; system_admin views via
 * ``tenant_id=*``. Each skill carries versions (list / get one /
 * export); for PR 3 the UI only consumes the top-level list.
 */
import { getJson, withTenantScope, type TenantScope } from "./client";

export interface SkillRecord {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  category: string;
  current_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface SkillList {
  items: SkillRecord[];
  total: number;
  cross_tenant: boolean;
}

export interface ListSkillsParams {
  tenantScope?: TenantScope;
  category?: string;
  limit?: number;
  offset?: number;
}

export async function listSkills(
  params: ListSkillsParams = {},
): Promise<SkillList> {
  const { tenantScope, category, limit, offset } = params;
  const query = withTenantScope({ category, limit, offset }, tenantScope);
  return getJson<SkillList>("/v1/skills", { params: query });
}

export async function getSkill(skillId: string): Promise<SkillRecord> {
  return getJson<SkillRecord>(`/v1/skills/${skillId}`);
}
