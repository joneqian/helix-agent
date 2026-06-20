/**
 * Skill Marketplace e2e — Skill Marketplace Phase 3.
 *
 * Tenant happy path: open the marketplace → a tier-locked skill's CTA is
 * disabled → enable an entitled skill → the card flips to the "enabled" state.
 *
 * Network is fully mocked. The skills backend returns RAW payloads (no
 * ``{success,data,error}`` envelope), so the GET /v1/skills stub returns the
 * bare ``SkillList`` shape. Spec-level routes use ``route.fallback()`` so
 * unmatched requests fall through to the fixture's global stub.
 */
import { test, expect, expectNoA11yViolations, SAMPLE_JWT } from "./fixtures";

const platformSkill = (
  id: string,
  name: string,
  over: Record<string, unknown> = {},
) => ({
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
  ...over,
});

// RAW SkillList (skills router is un-enveloped).
const SKILLS = {
  items: [],
  platform_items: [
    platformSkill("sk1", "web_search", { required_tier: "free" }),
    platformSkill("sk2", "code_interpreter", {
      required_tier: "enterprise",
      entitled: false,
    }),
  ],
  next_cursor: null,
  cross_tenant: false,
};

const SUBSCRIPTION = {
  id: "sub-1",
  platform_skill_id: "sk1",
  enabled: true,
  created_at: "2026-06-01T10:00:00Z",
  created_by: "u1",
};

async function login(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/login");
  await expect(page.getByTestId("login-card")).toBeVisible();
  const tokenField = page.getByTestId("login-token");
  if (!(await tokenField.isVisible())) {
    await page.getByTestId("login-dev-toggle").click();
  }
  await tokenField.fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);
}

test.beforeEach(async ({ page }) => {
  // Subscribe — POST/DELETE /v1/skills/{id}/subscribe. Register before the
  // broader /v1/skills route so it wins.
  await page.route("**/v1/skills/*/subscribe", async (route) => {
    const method = route.request().method();
    if (method === "POST") {
      await route.fulfill({ json: SUBSCRIPTION });
      return;
    }
    if (method === "DELETE") {
      await route.fulfill({ json: { ...SUBSCRIPTION, enabled: false } });
      return;
    }
    await route.fallback();
  });
  // Merged skills view (page load).
  await page.route("**/v1/skills*", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: SKILLS });
      return;
    }
    await route.fallback();
  });
});

test("browse marketplace → locked skill disabled → enable entitled skill", async ({
  page,
}) => {
  await login(page);
  await page.goto("/skill-marketplace");

  await expect(page.getByTestId("sm-root")).toBeVisible();

  // The tier-locked (enterprise) skill's CTA is disabled.
  await expect(page.getByTestId("sm-locked-code_interpreter")).toBeDisabled();

  // Enable the entitled skill — the POST fires and the card flips to "enabled".
  const [req] = await Promise.all([
    page.waitForRequest(
      (r) =>
        r.url().includes("/v1/skills/sk1/subscribe") &&
        r.method() === "POST",
    ),
    page.getByTestId("sm-subscribe-web_search").click(),
  ]);
  expect(req.method()).toBe("POST");
  await expect(page.getByTestId("sm-unsubscribe-web_search")).toBeVisible();
});

test("skill-marketplace passes axe", async ({ page }) => {
  await login(page);
  await page.goto("/skill-marketplace");
  await expect(page.getByTestId("sm-root")).toBeVisible();
  await expectNoA11yViolations(page, "skill-marketplace");
});
