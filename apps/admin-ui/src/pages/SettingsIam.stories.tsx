import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";

import { SettingsServiceAccounts } from "./SettingsServiceAccounts";
import { SettingsRoleBindings } from "./SettingsRoleBindings";
import { TenantScopeProvider } from "../tenant/TenantScopeContext";
import { AuthProvider } from "../auth/AuthContext";
import { apiClient, setStoredToken } from "../api/client";
import "../i18n";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

interface FixtureOptions {
  items: unknown[];
  crossTenant?: boolean;
  systemAdmin?: boolean;
}

function withFixture({ items, crossTenant = false, systemAdmin = false }: FixtureOptions) {
  return (Story: React.ComponentType) => {
    const roles = systemAdmin ? ["admin", "system_admin"] : ["admin"];
    setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles }));
    apiClient.defaults.adapter = (config) =>
      Promise.resolve({
        data: {
          success: true,
          data: { items, total: items.length, cross_tenant: crossTenant },
          error: null,
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    return (
      <MemoryRouter>
        <AuthProvider>
          <TenantScopeProvider>
            <App>
              <Story />
            </App>
          </TenantScopeProvider>
        </AuthProvider>
      </MemoryRouter>
    );
  };
}

const sa = (id: string, name: string, active = true) => ({
  id,
  tenant_id: "t1",
  name,
  description: `${name} — auto-generated.`,
  is_active: active,
  created_by: "u1",
  created_at: "2026-05-20T10:00:00Z",
});

const rb = (
  id: string,
  role: "tenant_admin" | "developer" | "viewer" | "system_admin",
  platform = false,
) => ({
  id,
  tenant_id: platform ? null : "t1",
  subject_type: "user" as const,
  subject_id: `0000000${id.slice(-1)}-0000-0000-0000-000000000000`,
  role,
  platform_scope: platform,
  granted_by: "u1",
  granted_at: "2026-05-26T10:00:00Z",
});

export const ServiceAccountsEmpty: StoryObj<typeof SettingsServiceAccounts> = {
  decorators: [withFixture({ items: [] })],
};
ServiceAccountsEmpty.render = () => <SettingsServiceAccounts />;

export const ServiceAccountsPopulated: StoryObj<typeof SettingsServiceAccounts> = {
  decorators: [
    withFixture({
      items: [
        sa("sa-1", "sa_data_pipeline"),
        sa("sa-2", "sa_webhook_ingest"),
        sa("sa-3", "sa_legacy", false),
      ],
    }),
  ],
};
ServiceAccountsPopulated.render = () => <SettingsServiceAccounts />;

export const RoleBindingsTenantAdmin: StoryObj<typeof SettingsRoleBindings> = {
  decorators: [
    withFixture({
      items: [
        rb("rb1", "tenant_admin"),
        rb("rb2", "developer"),
        rb("rb3", "viewer"),
      ],
      systemAdmin: false,
    }),
  ],
};
RoleBindingsTenantAdmin.render = () => <SettingsRoleBindings />;

export const RoleBindingsSystemAdmin: StoryObj<typeof SettingsRoleBindings> = {
  decorators: [
    withFixture({
      items: [
        rb("rb1", "tenant_admin"),
        rb("rb2", "developer"),
        rb("rb4", "system_admin", true),
      ],
      systemAdmin: true,
    }),
  ],
};
RoleBindingsSystemAdmin.render = () => <SettingsRoleBindings />;

const meta: Meta = {
  title: "Pages/SettingsIam",
};

export default meta;
