import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { App } from "antd";
import { MemoryRouter } from "react-router-dom";

import { SettingsRateCard } from "./SettingsRateCard";
import { apiClient } from "../api/client";
import "../i18n";

const RECORDS = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    tenant_id: null,
    provider: "anthropic",
    model: "claude-opus-4-8",
    input_token_micros: 5,
    output_token_micros: 25,
    cache_creation_token_micros: 6,
    cache_read_token_micros: 1,
    markup_bps: 1500,
    plan_tier: null,
    effective_from: "2026-06-01T00:00:00Z",
    effective_until: null,
  },
  {
    id: "11111111-1111-1111-1111-111111111112",
    tenant_id: null,
    provider: "openai",
    model: "gpt-5.5",
    input_token_micros: 3,
    output_token_micros: 12,
    cache_creation_token_micros: 0,
    cache_read_token_micros: 0,
    markup_bps: 2000,
    plan_tier: "pro",
    effective_from: "2026-05-01T00:00:00Z",
    effective_until: "2026-07-01T00:00:00Z",
  },
];

/** Rate-card endpoints are enveloped — respond ``{success,data,error}``. */
function withStubs(Story: ComponentType) {
  apiClient.defaults.adapter = (config) =>
    Promise.resolve({
      data: { success: true, data: RECORDS, error: null },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
      request: {},
    });
  return (
    <MemoryRouter>
      <App>
        <Story />
      </App>
    </MemoryRouter>
  );
}

const meta: Meta<typeof SettingsRateCard> = {
  title: "Pages/SettingsRateCard",
  component: SettingsRateCard,
  decorators: [withStubs],
};
export default meta;

type Story = StoryObj<typeof SettingsRateCard>;

/** NOTE: the story renders the forbidden state unless the auth context
 *  reports system_admin — Storybook has no real login, so this story is
 *  primarily for the gate + table layout's visual baseline. */
export const Default: Story = {};
