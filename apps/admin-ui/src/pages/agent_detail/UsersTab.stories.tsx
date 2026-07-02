import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";

import { UsersTab } from "./UsersTab";
import type { AgentDetailResponse } from "../../api/agents";
import { apiClient } from "../../api/client";
import "../../i18n";

const detail: AgentDetailResponse = {
  record: {
    id: "11111111-1111-1111-1111-111111111111",
    tenant_id: "22222222-2222-2222-2222-222222222222",
    name: "code-reviewer",
    version: "1.0.0",
    status: "active",
    spec_sha256: "a".repeat(64),
    created_by: "u",
    created_at: "2026-06-12T00:00:00Z",
    updated_at: "2026-06-12T00:00:00Z",
    spec: {},
  },
};

const items = [
  {
    user_id: "88888888-8888-8888-8888-888888888888",
    display_name: "Alice",
    conversation_count: 4,
    run_count: 9,
    error_count: 1,
    pending_count: 1,
    last_run_at: "2026-06-12T02:03:00Z",
    tokens: {
      input_tokens: 12_400,
      output_tokens: 3_400,
      cache_creation_tokens: 0,
      cache_read_tokens: 0,
      total_tokens: 15_800,
      llm_calls: 22,
      models: ["claude-sonnet-4-5"],
    },
  },
  {
    user_id: "99999999-9999-9999-9999-999999999999",
    display_name: null,
    conversation_count: 1,
    run_count: 1,
    error_count: 0,
    pending_count: 0,
    last_run_at: null,
    tokens: null,
  },
];

/** ``GET /v1/agents/{n}/{v}/users`` is an envelope endpoint. */
function withStub() {
  return (Story: ComponentType) => {
    apiClient.defaults.adapter = (config) =>
      Promise.resolve({
        data: {
          success: true,
          data: { items, total: items.length, cross_tenant: false },
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
        <Story />
      </MemoryRouter>
    );
  };
}

const meta: Meta<typeof UsersTab> = {
  title: "AgentDetail/UsersTab",
  component: UsersTab,
  args: { detail },
};
export default meta;

type Story = StoryObj<typeof UsersTab>;

export const Default: Story = { decorators: [withStub()] };
