/**
 * Curation + Eval SDK — backed by ``/v1/curation/*`` + ``/v1/eval-datasets``.
 *
 * Stream H.1b PR 3. Curation candidates are produced by the curation
 * worker; reviewers promote them to eval datasets or dismiss. The
 * list endpoints accept ``tenant_id=*`` for system_admin aggregate.
 */
import { getJson, withTenantScope, type TenantScope } from "./client";

export type CandidateStatus = "pending" | "promoted" | "dismissed";

export interface CurationCandidate {
  id: string;
  tenant_id: string;
  agent_name: string;
  agent_version: string;
  thread_id: string;
  user_id: string | null;
  trajectory_key: string;
  outcome: string;
  signal: string;
  feedback_rating: number | null;
  status: CandidateStatus;
  eval_dataset_id: string | null;
  detected_at: string;
  reviewed_at: string | null;
}

export interface CurationCandidateList {
  items: CurationCandidate[];
  total: number;
  cross_tenant: boolean;
}

export interface ListCandidatesParams {
  tenantScope?: TenantScope;
  status?: CandidateStatus;
  agentName?: string;
  limit?: number;
  offset?: number;
}

export async function listCandidates(
  params: ListCandidatesParams = {},
): Promise<CurationCandidateList> {
  const { tenantScope, status, agentName, limit, offset } = params;
  const query = withTenantScope(
    { status, agent_name: agentName, limit, offset },
    tenantScope,
  );
  return getJson<CurationCandidateList>("/v1/curation/candidates", {
    params: query,
  });
}

export interface EvalDataset {
  id: string;
  tenant_id: string;
  agent_name: string;
  name: string;
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
  source: string;
  source_trajectory_key: string | null;
  source_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvalDatasetList {
  items: EvalDataset[];
  total: number;
  cross_tenant: boolean;
}

export interface ListEvalDatasetsParams {
  tenantScope?: TenantScope;
  agentName?: string;
  limit?: number;
  offset?: number;
}

export async function listEvalDatasets(
  params: ListEvalDatasetsParams = {},
): Promise<EvalDatasetList> {
  const { tenantScope, agentName, limit, offset } = params;
  const query = withTenantScope(
    { agent_name: agentName, limit, offset },
    tenantScope,
  );
  return getJson<EvalDatasetList>("/v1/eval-datasets", { params: query });
}
