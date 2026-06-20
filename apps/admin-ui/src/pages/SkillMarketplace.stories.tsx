/**
 * Storybook stories for SkillMarketplace — Skill Marketplace Phase 3.
 *
 * The skills backend returns RAW payloads (no ``{success,data,error}``
 * envelope), so the fixture adapter returns the bare ``SkillList`` shape —
 * mirrors ``SkillsList.stories.tsx``.
 */
import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";

import { SkillMarketplace } from "./SkillMarketplace";
import type { SkillRecord } from "../api/skills";
import { TenantScopeProvider } from "../tenant/TenantScopeContext";
import { AuthProvider } from "../auth/AuthContext";
import { apiClient, setStoredToken } from "../api/client";
import "../i18n";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

const platformSkill = (
  id: string,
  name: string,
  opts: Partial<SkillRecord> = {},
): SkillRecord => ({
  id,
  name,
  status: "active",
  latest_version: 1,
  description: `${name} — a platform-curated skill.`,
  category: "general",
  pinned: false,
  last_used_at: null,
  state_changed_at: null,
  created_at: "2026-05-20T10:00:00Z",
  updated_at: "2026-05-26T10:00:00Z",
  source: "platform",
  entitled: true,
  required_tier: "free",
  subscribed: false,
  ...opts,
});

function withFixture(platformItems: SkillRecord[]) {
  return (Story: ComponentType) => {
    setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles: ["admin"] }));
    apiClient.defaults.adapter = (config) =>
      Promise.resolve({
        data: {
          items: [],
          platform_items: platformItems,
          next_cursor: null,
          cross_tenant: false,
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    return (
      <MemoryRouter initialEntries={["/skill-marketplace"]}>
        <AuthProvider>
          <TenantScopeProvider>
            <App>
              <Story />
            </App>
          </TenantScopeProvider>
        </AuthProvider>
      </MemoryRouter>
    );
  };
}

const meta: Meta<typeof SkillMarketplace> = {
  title: "Pages/SkillMarketplace",
  component: SkillMarketplace,
};

export default meta;

type Story = StoryObj<typeof SkillMarketplace>;

/** A mix of available, already-enabled, and tier-locked platform skills. */
export const Populated: Story = {
  decorators: [
    withFixture([
      platformSkill("sk1", "web_search", { required_tier: "free" }),
      platformSkill("sk2", "deep_research", {
        required_tier: "pro",
        subscribed: true,
        category: "research",
      }),
      platformSkill("sk3", "code_interpreter", {
        required_tier: "enterprise",
        entitled: false,
        category: "dev",
      }),
    ]),
  ],
};

/** No platform skills published yet — guided empty state. */
export const Empty: Story = {
  decorators: [withFixture([])],
};
