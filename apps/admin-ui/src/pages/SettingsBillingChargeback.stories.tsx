/**
 * Storybook stories for SettingsBillingChargeback — Stream Z3.
 *
 * Mirrors SettingsMcpCatalog.stories: parameterised on roles to exercise the
 * system_admin gate; {success,data,error} envelope via the axios adapter.
 */
import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";

import { SettingsBillingChargeback } from "./SettingsBillingChargeback";
import type { Chargeback } from "../api/billing-admin";
import { AuthProvider } from "../auth/AuthContext";
import { apiClient, setStoredToken } from "../api/client";
import "../i18n";

const CHARGEBACK: Chargeback = {
  month: "2026-06",
  as_of: "2026-06-03T10:00:00Z",
  total_base_cost_micros: 12_400_000,
  total_billed_cost_micros: 18_600_000,
  total_margin_micros: 6_200_000,
  tenants: [
    {
      tenant_id: "acme-corp",
      input_tokens: 4_204_500,
      output_tokens: 920_100,
      cache_creation_tokens: 80_000,
      cache_read_tokens: 1_980_000,
      base_cost_micros: 8_400_000,
      markup_cost_micros: 4_200_000,
      billed_cost_micros: 12_600_000,
      margin_micros: 4_200_000,
      unpriced_buckets: 0,
    },
    {
      tenant_id: "globex",
      input_tokens: 2_010_000,
      output_tokens: 510_000,
      cache_creation_tokens: 0,
      cache_read_tokens: 0,
      base_cost_micros: 4_000_000,
      markup_cost_micros: 2_000_000,
      billed_cost_micros: 6_000_000,
      margin_micros: 2_000_000,
      unpriced_buckets: 3,
    },
  ],
};

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function withFixture(roles: string[], isSystemAdmin: boolean, data: Chargeback) {
  return (Story: ComponentType) => {
    setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles }));
    apiClient.defaults.adapter = (config) => {
      const url = config.url ?? "";
      const body = url.endsWith("/me")
        ? {
            success: true,
            data: {
              subject_id: "u1",
              subject_type: "user",
              tenant_id: "t1",
              auth_method: "jwt",
              roles,
              scopes: [],
              is_system_admin: isSystemAdmin,
              allowed_tenants: ["t1"],
            },
            error: null,
          }
        : { success: true, data, error: null };
      return Promise.resolve({
        data: body,
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
          <App>
            <Story />
          </App>
        </AuthProvider>
      </MemoryRouter>
    );
  };
}

const meta: Meta<typeof SettingsBillingChargeback> = {
  title: "Pages/SettingsBillingChargeback",
  component: SettingsBillingChargeback,
};

export default meta;

type Story = StoryObj<typeof SettingsBillingChargeback>;

/** system_admin with a populated cross-tenant cost split. */
export const SystemAdmin: Story = {
  decorators: [withFixture(["system_admin"], true, CHARGEBACK)],
};

/** system_admin, no chargeback data for the month. */
export const Empty: Story = {
  decorators: [withFixture(["system_admin"], true, { ...CHARGEBACK, tenants: [] })],
};

/** Non-admin — system-admin-only notice. */
export const NotSystemAdmin: Story = {
  decorators: [withFixture(["admin"], false, CHARGEBACK)],
};
