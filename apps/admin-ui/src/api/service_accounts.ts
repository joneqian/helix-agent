/**
 * Service Accounts SDK — backed by ``/v1/service_accounts`` (Stream C.3).
 *
 * Backend returns the standard ``{success, data, error}`` envelope, so
 * this SDK uses ``getJson`` / ``postJson`` / ``apiClient.delete``
 * (204).
 *
 * Stream H.4 PR 7 split: moved ``listServiceAccounts`` out of
 * ``api/api_keys.ts`` and added ``createServiceAccount`` +
 * ``deleteServiceAccount`` so the IAM surface is cohesive.
 */
import {
  apiClient,
  getJson,
  postJson,
  withTenantScope,
  type TenantScope,
} from "./client";

export interface ServiceAccountRecord {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

export interface ServiceAccountList {
  items: ServiceAccountRecord[];
  total: number;
  cross_tenant: boolean;
}

export interface ListServiceAccountsParams {
  tenantScope?: TenantScope;
}

export async function listServiceAccounts(
  params: ListServiceAccountsParams = {},
): Promise<ServiceAccountList> {
  const query = withTenantScope({}, params.tenantScope);
  return getJson<ServiceAccountList>("/v1/service_accounts", { params: query });
}

export interface CreateServiceAccountBody {
  name: string;
  description?: string;
}

export async function createServiceAccount(
  body: CreateServiceAccountBody,
): Promise<ServiceAccountRecord> {
  return postJson<ServiceAccountRecord>("/v1/service_accounts", body);
}

export async function deleteServiceAccount(serviceAccountId: string): Promise<void> {
  await apiClient.delete(
    `/v1/service_accounts/${encodeURIComponent(serviceAccountId)}`,
  );
}
