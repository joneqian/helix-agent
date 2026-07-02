import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";

import { ConversationsList } from "./ConversationsList";
import { AuthProvider } from "../auth/AuthContext";
import { TenantScopeProvider } from "../tenant/TenantScopeContext";
import { apiClient, setStoredToken } from "../api/client";
import "../i18n";

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
      <MemoryRouter initialEntries={["/conversations"]}>
        <AuthProvider>
          <TenantScopeProvider>
            <Story />
          </TenantScopeProvider>
        </AuthProvider>
      </MemoryRouter>
    );
  };
}

function withMockedError() {
  return (Story: React.ComponentType) => {
    setStoredToken(makeJwt({ sub: "x", tenant_id: "t1", roles: ["admin"] }));
    apiClient.defaults.adapter = () =>
      Promise.reject({
        isAxiosError: true,
        response: {
          status: 500,
          data: { detail: { code: "DB_DOWN", message: "Postgres unreachable" } },
        },
        message: "DB_DOWN",
      });
    return (
      <MemoryRouter initialEntries={["/conversations"]}>
        <AuthProvider>
          <TenantScopeProvider>
            <Story />
          </TenantScopeProvider>
        </AuthProvider>
      </MemoryRouter>
    );
  };
}

const sampleConversations = [
  {
    thread_id: "33333333-3333-3333-3333-333333333333",
    tenant_id: "22222222-2222-2222-2222-222222222222",
    user_id: "88888888-8888-8888-8888-888888888888",
    agent_name: "customer-support-bot",
    agent_version: "3.4.2",
    title: "refund question",
    status: "active",
    created_at: "2026-05-26T08:00:00Z",
    updated_at: "2026-05-26T08:00:32Z",
    run_count: 3,
    error_count: 0,
    pending_count: 1,
    last_run_at: "2026-05-26T08:00:30Z",
    tokens: {
      input_tokens: 1200,
      output_tokens: 300,
      cache_creation_tokens: 0,
      cache_read_tokens: 0,
      total_tokens: 1500,
      llm_calls: 3,
      models: ["deepseek-chat"],
    },
  },
  {
    thread_id: "55555555-5555-5555-5555-555555555555",
    tenant_id: "22222222-2222-2222-2222-222222222222",
    user_id: "88888888-8888-8888-8888-888888888888",
    agent_name: "ops-runbook",
    agent_version: "1.2.0",
    title: null,
    status: "completed",
    created_at: "2026-05-26T07:55:11Z",
    updated_at: "2026-05-26T07:55:48Z",
    run_count: 1,
    error_count: 0,
    pending_count: 0,
    last_run_at: "2026-05-26T07:55:12Z",
    tokens: null,
  },
  {
    thread_id: "77777777-7777-7777-7777-777777777777",
    tenant_id: "22222222-2222-2222-2222-222222222222",
    user_id: null,
    agent_name: null, // agent deleted between thread end and list query
    agent_version: null,
    title: "billing dispute",
    status: "failed",
    created_at: "2026-05-26T07:50:01Z",
    updated_at: "2026-05-26T07:50:08Z",
    run_count: 2,
    error_count: 2,
    pending_count: 0,
    last_run_at: "2026-05-26T07:50:05Z",
    tokens: null,
  },
];

const meta: Meta<typeof ConversationsList> = {
  title: "Conversations/ConversationsList",
  component: ConversationsList,
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof ConversationsList>;

export const Populated: Story = {
  decorators: [withMockedList(sampleConversations)],
};

export const CrossTenant: Story = {
  decorators: [withMockedList(sampleConversations, true)],
};

export const Empty: Story = {
  decorators: [withMockedList([])],
};

export const ErrorState: Story = {
  decorators: [withMockedError()],
};
