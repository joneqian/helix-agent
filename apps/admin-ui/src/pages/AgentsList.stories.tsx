import type { Meta, StoryObj } from "@storybook/react";

import { AgentsList } from "./AgentsList";
import { AuthProvider } from "../auth/AuthContext";
import { TenantScopeProvider } from "../tenant/TenantScopeContext";
import { apiClient, setStoredToken } from "../api/client";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function withMockedList(items: unknown[], crossTenant = false) {
  return (Story: React.ComponentType) => {
    setStoredToken(makeJwt({ sub: "x", tenant_id: "t1", roles: ["admin"] }));
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
      <AuthProvider>
        <TenantScopeProvider>
          <Story />
        </TenantScopeProvider>
      </AuthProvider>
    );
  };
}

const sampleAgents = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    tenant_id: "22222222-2222-2222-2222-222222222222",
    name: "customer-support-bot",
    version: "3.4.2",
    status: "active",
    spec_sha256: "a".repeat(64),
    created_by: "alice@acme.com",
    created_at: "2026-04-12T09:00:00Z",
    updated_at: "2026-05-25T07:00:00Z",
  },
  {
    id: "33333333-3333-3333-3333-333333333333",
    tenant_id: "22222222-2222-2222-2222-222222222222",
    name: "ops-runbook",
    version: "1.2.0",
    status: "draft",
    spec_sha256: "b".repeat(64),
    created_by: "bob@acme.com",
    created_at: "2026-05-01T12:30:00Z",
    updated_at: "2026-05-22T16:45:00Z",
  },
];

const meta: Meta<typeof AgentsList> = {
  title: "Stream H/AgentsList",
  component: AgentsList,
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof AgentsList>;

export const PopulatedHomeTenant: Story = {
  decorators: [withMockedList(sampleAgents)],
};

export const CrossTenantView: Story = {
  decorators: [withMockedList(sampleAgents, true)],
};

export const Empty: Story = {
  decorators: [withMockedList([])],
};
