import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";

import { SettingsAudit } from "./SettingsAudit";
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
  hasMore?: boolean;
  appliedScope?: string;
  error?: boolean;
}

function withFixture({ items, hasMore = false, appliedScope = "t1", error = false }: FixtureOptions) {
  return (Story: React.ComponentType) => {
    setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles: ["admin"] }));
    apiClient.defaults.adapter = (config) => {
      if (error) {
        return Promise.reject({
          isAxiosError: true,
          response: { status: 500, data: { detail: { code: "INTERNAL", message: "boom" } } },
          message: "Request failed",
          config,
        });
      }
      return Promise.resolve({
        data: {
          items,
          next_cursor: hasMore ? "next-cursor" : null,
          has_more: hasMore,
          applied_scope: appliedScope,
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    };
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

const meta: Meta<typeof SettingsAudit> = {
  title: "Pages/SettingsAudit",
  component: SettingsAudit,
};

export default meta;

type Story = StoryObj<typeof SettingsAudit>;

const entry = (
  id: number,
  action: string,
  result: "success" | "denied" | "error",
  resource_type: string,
) => ({
  id,
  tenant_id: "t1",
  actor_type: "user" as const,
  actor_id: `user-alice-${id}`,
  on_behalf_of: null,
  action,
  resource_type,
  resource_id: `${resource_type}-${id}`,
  result,
  reason: result !== "success" ? "policy denied" : null,
  ip: "10.42.7.91",
  user_agent: "Mozilla/5.0",
  request_id: null,
  trace_id: `trace-${id}`,
  details: { actor_role: "tenant_admin", redacted_keys: ["api_key", "secret_token"] },
  occurred_at: "2026-05-26T10:00:00Z",
});

export const Empty: Story = {
  decorators: [withFixture({ items: [] })],
};

export const Populated: Story = {
  decorators: [
    withFixture({
      items: [
        entry(1, "memory:update", "success", "memory_item"),
        entry(2, "role_binding:create", "error", "role_binding"),
        entry(3, "skill:status_change", "denied", "skill"),
        entry(4, "trigger:fire", "success", "trigger"),
      ],
    }),
  ],
};

export const HasMore: Story = {
  decorators: [
    withFixture({
      items: [entry(1, "memory:update", "success", "memory_item"), entry(2, "audit:read", "success", "audit")],
      hasMore: true,
    }),
  ],
};

export const CrossTenant: Story = {
  decorators: [
    withFixture({
      items: [
        entry(1, "memory:update", "success", "memory_item"),
        entry(2, "role_binding:create", "denied", "role_binding"),
      ],
      appliedScope: "cross_tenant",
    }),
  ],
};

export const ErrorState: Story = {
  decorators: [withFixture({ items: [], error: true })],
};
