/**
 * AgentDetail per-agent tabs E2E — Stream H.6 PR 2.
 *
 * Smoke: each of the four per-agent tabs (Conversations / Skills /
 * Triggers / Memory) is wired in the AgentDetail Tabs bar and renders
 * its real component
 * (no more ``agent-detail-tab-placeholder``). Per-tab routes are
 * registered *after* the fixture defaults so they win (Playwright runs
 * the most-recently-added handler first).
 */
import { test, expect, SAMPLE_JWT } from "./fixtures";

const AGENT_NAME = "customer-support-bot";
const AGENT_VERSION = "3.4.2";
const TENANT = "22222222-2222-2222-2222-222222222222";

const DETAIL_ENVELOPE = {
  success: true,
  error: null,
  data: {
    record: {
      id: "33333333-3333-3333-3333-333333333333",
      tenant_id: TENANT,
      name: AGENT_NAME,
      version: AGENT_VERSION,
      status: "active",
      spec_sha256: "a".repeat(64),
      created_by: "alice@acme.com",
      created_at: "2026-04-12T09:00:00Z",
      updated_at: "2026-05-25T07:00:00Z",
      spec: {},
    },
  },
};

const SKILLS_RESPONSE = {
  items: [
    {
      id: "55555555-5555-5555-5555-555555555555",
      tenant_id: TENANT,
      name: "summarise-tickets",
      status: "active",
      latest_version: 2,
      description: "",
      category: "data",
      visibility: "tenant",
      pinned: false,
      last_used_at: null,
      state_changed_at: "2026-06-12T00:00:00Z",
      created_at: "2026-06-12T00:00:00Z",
      updated_at: "2026-06-12T00:00:00Z",
    },
  ],
  platform_items: [],
  next_cursor: null,
  cross_tenant: false,
};

const TRIGGERS_RESPONSE = {
  items: [
    {
      id: "66666666-6666-6666-6666-666666666666",
      tenant_id: TENANT,
      user_id: null,
      agent_name: AGENT_NAME,
      agent_version: AGENT_VERSION,
      name: "nightly-digest",
      kind: "cron",
      config: { expr: "0 9 * * *" },
      enabled: true,
      source: "api",
      created_at: "2026-06-12T00:00:00Z",
      updated_at: "2026-06-12T00:00:00Z",
    },
  ],
  total: 1,
  cross_tenant: false,
};

const MEMORY_RESPONSE = {
  success: true,
  error: null,
  data: {
    items: [
      {
        id: "77777777-7777-7777-7777-777777777777",
        tenant_id: TENANT,
        user_id: "88888888-8888-8888-8888-888888888888",
        kind: "fact",
        content: "prefers terse answers",
        created_at: "2026-06-12T00:00:00Z",
      },
    ],
    total: 1,
    cross_tenant: false,
  },
};

// Conversation-centric IA M2 — the per-agent users rollup.
const USERS_RESPONSE = {
  success: true,
  error: null,
  data: {
    items: [
      {
        user_id: "88888888-8888-8888-8888-888888888888",
        display_name: "Alice",
        conversation_count: 2,
        run_count: 3,
        error_count: 0,
        pending_count: 0,
        last_run_at: "2026-06-12T01:05:00Z",
        tokens: null,
      },
    ],
    total: 1,
    cross_tenant: false,
  },
};

test("the four per-agent tabs render real content, not the placeholder", async ({ page }) => {
  await page.route(`**/v1/agents/${AGENT_NAME}/${AGENT_VERSION}`, async (route) => {
    await route.fulfill({ json: DETAIL_ENVELOPE });
  });
  await page.route("**/v1/skills*", async (route) => {
    await route.fulfill({ json: SKILLS_RESPONSE });
  });
  await page.route("**/v1/triggers*", async (route) => {
    await route.fulfill({ json: TRIGGERS_RESPONSE });
  });
  await page.route("**/v1/memory*", async (route) => {
    await route.fulfill({ json: MEMORY_RESPONSE });
  });
  await page.route(`**/v1/agents/${AGENT_NAME}/${AGENT_VERSION}/users*`, async (route) => {
    await route.fulfill({ json: USERS_RESPONSE });
  });

  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);

  // Conversations — fixture default /v1/conversations* renders the row.
  await page.goto(`/agents/${AGENT_NAME}/${AGENT_VERSION}/conversations`);
  await expect(page.getByTestId("conversations-tab-root")).toBeVisible();
  await expect(page.getByText("refund question")).toBeVisible();
  await expect(page.getByTestId("agent-detail-tab-placeholder")).toHaveCount(0);

  // Users (M2) — the rollup row renders and drills into the user detail.
  await page.goto(`/agents/${AGENT_NAME}/${AGENT_VERSION}/users`);
  await expect(page.getByTestId("users-tab-root")).toBeVisible();
  await expect(page.getByText("Alice")).toBeVisible();
  await page.getByText("Alice").click();
  await expect(page.getByTestId("user-detail-root")).toBeVisible();
  await expect(page.getByTestId("user-conversations-table")).toBeVisible();

  // Skills — the agent-authored row renders.
  await page.goto(`/agents/${AGENT_NAME}/${AGENT_VERSION}/skills`);
  await expect(page.getByTestId("skills-tab-root")).toBeVisible();
  await expect(page.getByText("summarise-tickets")).toBeVisible();

  // Triggers — version-bound trigger renders with its enabled badge.
  await page.goto(`/agents/${AGENT_NAME}/${AGENT_VERSION}/triggers`);
  await expect(page.getByTestId("triggers-tab-root")).toBeVisible();
  await expect(page.getByText("nightly-digest")).toBeVisible();

  // Memory (M3) — the per-agent tab is gone; the user detail's Memory
  // pane renders the per-user item instead.
  await page.goto(
    `/agents/${AGENT_NAME}/${AGENT_VERSION}/users/88888888-8888-8888-8888-888888888888`,
  );
  await page.getByRole("tab", { name: /Memory|记忆/ }).click();
  await expect(page.getByTestId("user-memory-pane")).toBeVisible();
  await expect(page.getByText("prefers terse answers")).toBeVisible();
});
