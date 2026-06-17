import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";

import { SettingsPlatformUsers } from "./SettingsPlatformUsers";
import type { RoleBindingList } from "../api/role_bindings";
import { AuthProvider } from "../auth/AuthContext";
import { apiClient, setStoredToken } from "../api/client";
import "../i18n";

const LIST: RoleBindingList = {
  items: [
    {
      id: "b1",
      tenant_id: null,
      subject_type: "user",
      subject_id: "00000000-0000-0000-0000-000000000001",
      role: "system_admin",
      platform_scope: true,
      granted_by: "bootstrap",
      granted_at: "2026-06-10T08:00:00Z",
    },
    {
      id: "b2",
      tenant_id: null,
      subject_type: "user",
      subject_id: "00000000-0000-0000-0000-000000000002",
      role: "system_admin",
      platform_scope: true,
      granted_by: "00000000-0000-0000-0000-000000000001",
      granted_at: "2026-06-14T12:30:00Z",
    },
  ],
  total: 2,
  cross_tenant: false,
};

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function withAuth(roles: string[]) {
  return (Story: ComponentType) => {
    setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles }));
    apiClient.defaults.adapter = (config) =>
      Promise.resolve({
        data: { success: true, data: LIST, error: null },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    return (
      <MemoryRouter>
        <AuthProvider>
          <App>
            <Story />
          </App>
        </AuthProvider>
      </MemoryRouter>
    );
  };
}

const meta: Meta<typeof SettingsPlatformUsers> = {
  title: "Pages/SettingsPlatformUsers",
  component: SettingsPlatformUsers,
};

export default meta;

type Story = StoryObj<typeof SettingsPlatformUsers>;

export const SystemAdmin: Story = {
  decorators: [withAuth(["system_admin"])],
};

export const NotSystemAdmin: Story = {
  decorators: [withAuth(["admin"])],
};
