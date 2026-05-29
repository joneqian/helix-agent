import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";

import { SettingsCreateTenant } from "./SettingsCreateTenant";
import { AuthProvider } from "../auth/AuthContext";
import { apiClient, setStoredToken } from "../api/client";
import "../i18n";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function withAuth(roles: string[]) {
  return (Story: ComponentType) => {
    setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles }));
    // Any POST /v1/tenants returns a fresh tenant record.
    apiClient.defaults.adapter = (config) =>
      Promise.resolve({
        data: {
          success: true,
          data: { tenant_id: "11111111-1111-1111-1111-111111111111", display_name: "Acme Inc", plan: "free" },
          error: null,
        },
        status: 201,
        statusText: "Created",
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

const meta: Meta<typeof SettingsCreateTenant> = {
  title: "Pages/SettingsCreateTenant",
  component: SettingsCreateTenant,
};

export default meta;

type Story = StoryObj<typeof SettingsCreateTenant>;

export const SystemAdmin: Story = {
  decorators: [withAuth(["system_admin"])],
};

export const NotSystemAdmin: Story = {
  decorators: [withAuth(["admin"])],
};
