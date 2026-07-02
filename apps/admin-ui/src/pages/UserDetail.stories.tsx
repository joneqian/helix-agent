import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { UserDetail } from "./UserDetail";
import { apiClient } from "../api/client";
import "../i18n";

const USER_ID = "88888888-8888-8888-8888-888888888888";

const conversations = {
  items: [
    {
      thread_id: "44444444-4444-4444-4444-444444444444",
      tenant_id: "22222222-2222-2222-2222-222222222222",
      user_id: USER_ID,
      agent_name: "code-reviewer",
      agent_version: "1.0.0",
      title: "refund question",
      status: "active",
      created_at: "2026-06-12T01:00:00Z",
      updated_at: "2026-06-12T01:05:00Z",
      run_count: 3,
      error_count: 1,
      pending_count: 0,
      last_run_at: "2026-06-12T01:05:00Z",
      tokens: null,
    },
  ],
  total: 1,
  cross_tenant: false,
};

const memories = {
  items: [
    {
      id: "m1",
      tenant_id: "22222222-2222-2222-2222-222222222222",
      user_id: USER_ID,
      kind: "fact",
      content: "Prefers email contact",
      created_at: "2026-06-12T00:00:00Z",
      updated_at: "2026-06-12T00:00:00Z",
    },
  ],
  total: 1,
  cross_tenant: false,
};

const usage = {
  month: "2026-07",
  as_of: "2026-07-02T00:00:00Z",
  realtime: true,
  total: {
    input_tokens: 12_400,
    output_tokens: 3_400,
    cache_creation_tokens: 0,
    cache_read_tokens: 0,
  },
  by_agent: [],
  by_model: [
    {
      key: "claude-sonnet-4-5",
      input_tokens: 12_400,
      output_tokens: 3_400,
      cache_creation_tokens: 0,
      cache_read_tokens: 0,
    },
  ],
};

/** Route by URL — conversations/memory/usage are enveloped, artifacts raw. */
function withStub() {
  return (Story: ComponentType) => {
    apiClient.defaults.adapter = (config) => {
      const url = config.url ?? "";
      let data: unknown;
      if (url.includes("/v1/conversations")) {
        data = { success: true, data: conversations, error: null };
      } else if (url.includes("/v1/memory")) {
        data = { success: true, data: memories, error: null };
      } else if (url.includes("/v1/usage/tokens")) {
        data = { success: true, data: usage, error: null };
      } else {
        // /v1/artifacts is a raw (un-enveloped) endpoint.
        data = {
          items: [{ name: "report.md", kind: "document", latest_version: 2 }],
          artifacts: [{ name: "report.md", kind: "document", latest_version: 2 }],
          cross_tenant: false,
        };
      }
      return Promise.resolve({
        data,
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    };
    return (
      <MemoryRouter
        initialEntries={[
          {
            pathname: `/agents/code-reviewer/1.0.0/users/${USER_ID}`,
            state: { displayName: "Alice" },
          },
        ]}
      >
        <Routes>
          <Route path="/agents/:name/:version/users/:userId" element={<Story />} />
        </Routes>
      </MemoryRouter>
    );
  };
}

const meta: Meta<typeof UserDetail> = {
  title: "Conversations/UserDetail",
  component: UserDetail,
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof UserDetail>;

export const Default: Story = { decorators: [withStub()] };
