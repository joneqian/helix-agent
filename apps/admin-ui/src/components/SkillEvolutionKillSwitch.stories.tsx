import type { Meta, StoryObj } from "@storybook/react";
import { App } from "antd";

import { SkillEvolutionKillSwitch } from "./SkillEvolutionKillSwitch";
import { AuthProvider } from "../auth/AuthContext";
import { apiClient, setStoredToken } from "../api/client";
import "../i18n";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function stub(state: unknown, roles: string[]) {
  setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles }));
  apiClient.defaults.adapter = (config) =>
    Promise.resolve({
      data: state,
      status: 200,
      statusText: "OK",
      headers: {},
      config,
      request: {},
    });
}

const meta: Meta<typeof SkillEvolutionKillSwitch> = {
  title: "Components/SkillEvolutionKillSwitch",
  component: SkillEvolutionKillSwitch,
  decorators: [
    (Story) => (
      <App>
        <AuthProvider>
          <Story />
        </AuthProvider>
      </App>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SkillEvolutionKillSwitch>;

export const TenantAdminActive: Story = {
  render: () => {
    stub({ global: null, tenant: null, effective_halted: false }, ["admin"]);
    return <SkillEvolutionKillSwitch />;
  },
};

export const Halted: Story = {
  render: () => {
    stub(
      {
        global: null,
        tenant: {
          id: "k1",
          scope: "tenant",
          tenant_id: "t1",
          engaged: true,
          reason: "runaway",
          engaged_by_user_id: null,
          engaged_at: null,
          released_by_user_id: null,
          released_at: null,
          updated_at: "2026-06-08T00:00:00Z",
        },
        effective_halted: true,
      },
      ["admin"],
    );
    return <SkillEvolutionKillSwitch />;
  },
};
