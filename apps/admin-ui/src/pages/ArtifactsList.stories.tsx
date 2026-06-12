import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";

import { ArtifactsList } from "./ArtifactsList";
import { apiClient } from "../api/client";
import { TenantScopeProvider } from "../tenant/TenantScopeContext";
import "../i18n";

const HOME_RESPONSE = {
  artifacts: [],
  items: [
    { name: "q2-report.md", kind: "document", latest_version: 3 },
    { name: "etl.py", kind: "code", latest_version: 1 },
    { name: "sales.parquet", kind: "data", latest_version: 7 },
  ],
  cross_tenant: false,
};

const CROSS_RESPONSE = {
  artifacts: [],
  items: [
    {
      name: "q2-report.md",
      kind: "document",
      latest_version: 3,
      tenant_id: "22222222-2222-2222-2222-222222222222",
      user_id: "88888888-8888-8888-8888-888888888888",
    },
    {
      name: "etl.py",
      kind: "code",
      latest_version: 1,
      tenant_id: "33333333-3333-3333-3333-333333333333",
      user_id: "99999999-9999-9999-9999-999999999999",
    },
  ],
  cross_tenant: true,
};

const VERSIONS_RESPONSE = {
  name: "q2-report.md",
  versions: [
    {
      version: 3,
      path_in_workspace: "artifacts/q2-report.md",
      size_bytes: 18234,
      sha256: "c".repeat(64),
      created_in_thread: "44444444-4444-4444-4444-444444444444",
      created_at: "2026-06-12T02:00:00Z",
    },
    {
      version: 2,
      path_in_workspace: "artifacts/q2-report.md",
      size_bytes: null,
      sha256: null,
      created_in_thread: null,
      created_at: "2026-06-11T02:00:00Z",
    },
  ],
};

/** ``/v1/artifacts*`` are raw endpoints — respond with the body directly. */
function withStubs(list: unknown) {
  return (Story: ComponentType) => {
    apiClient.defaults.adapter = (config) => {
      const url = config.url ?? "";
      const data = /\/versions$/.test(url) ? VERSIONS_RESPONSE : list;
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
      <MemoryRouter>
        <TenantScopeProvider>
          <Story />
        </TenantScopeProvider>
      </MemoryRouter>
    );
  };
}

const meta: Meta<typeof ArtifactsList> = {
  title: "Pages/ArtifactsList",
  component: ArtifactsList,
};
export default meta;

type Story = StoryObj<typeof ArtifactsList>;

/** Home tenant — the caller's own artifacts with full row actions. */
export const Home: Story = { decorators: [withStubs(HOME_RESPONSE)] };

/** Cross-tenant aggregate — read-only, tenant/user columns, no actions. */
export const CrossTenant: Story = { decorators: [withStubs(CROSS_RESPONSE)] };

/** No artifacts yet. */
export const Empty: Story = {
  decorators: [withStubs({ artifacts: [], items: [], cross_tenant: false })],
};
