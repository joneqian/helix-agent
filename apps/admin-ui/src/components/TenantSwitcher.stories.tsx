import type { Meta, StoryObj } from "@storybook/react";

import { TenantSwitcher } from "./TenantSwitcher";
import { AuthProvider } from "../auth/AuthContext";
import { TenantScopeProvider } from "../tenant/TenantScopeContext";
import { setStoredToken } from "../api/client";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function withAuth(token: string) {
  return (Story: React.ComponentType) => {
    setStoredToken(token);
    return (
      <AuthProvider>
        <TenantScopeProvider>
          <Story />
        </TenantScopeProvider>
      </AuthProvider>
    );
  };
}

const meta: Meta<typeof TenantSwitcher> = {
  title: "Stream H/TenantSwitcher",
  component: TenantSwitcher,
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof TenantSwitcher>;

export const TenantAdminDisabled: Story = {
  decorators: [
    withAuth(
      makeJwt({
        sub: "00000000-0000-0000-0000-0000000000aa",
        sub_type: "user",
        tenant_id: "00000000-0000-0000-0000-0000000000a1",
        roles: ["admin"],
      }),
    ),
  ],
};

export const SystemAdminEnabled: Story = {
  decorators: [
    withAuth(
      makeJwt({
        sub: "00000000-0000-0000-0000-0000000000bb",
        sub_type: "user",
        tenant_id: "00000000-0000-0000-0000-0000000000a1",
        roles: ["system_admin"],
      }),
    ),
  ],
};
