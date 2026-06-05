/**
 * Usage page e2e — Stream Z3.
 *
 * Tenant usage surface: route-mock /v1/usage/cost + /v1/usage/tokens, assert
 * the billed-cost summary + cost table + token totals render, and pass axe.
 *
 * Network is fully mocked. Spec-level routes use ``route.fallback()`` so
 * unmatched requests fall through to the fixture's global stub.
 */
import { test, expect, expectNoA11yViolations, SAMPLE_JWT } from "./fixtures";

const COST = {
  success: true,
  data: {
    month: "2026-06",
    group_by: "agent",
    as_of: "2026-06-03T10:00:00Z",
    total_billed_cost_micros: 4_820_000,
    groups: [
      {
        key: "customer-support-bot",
        input_tokens: 1_204_500,
        output_tokens: 320_100,
        cache_creation_tokens: 40_000,
        cache_read_tokens: 980_000,
        billed_cost_micros: 3_120_000,
        unpriced: false,
      },
      {
        key: "research-assistant",
        input_tokens: 410_000,
        output_tokens: 120_000,
        cache_creation_tokens: 0,
        cache_read_tokens: 0,
        billed_cost_micros: 1_700_000,
        unpriced: true,
      },
    ],
  },
  error: null,
};

const TOKENS = {
  success: true,
  data: {
    month: "2026-06",
    as_of: "2026-06-03T11:30:00Z",
    realtime: true,
    total: {
      input_tokens: 1_614_500,
      output_tokens: 440_100,
      cache_creation_tokens: 40_000,
      cache_read_tokens: 980_000,
    },
    by_agent: [
      { key: "customer-support-bot", input_tokens: 1_204_500, output_tokens: 320_100, cache_creation_tokens: 40_000, cache_read_tokens: 980_000 },
    ],
    by_model: [
      { key: "claude-sonnet-4", input_tokens: 1_614_500, output_tokens: 440_100, cache_creation_tokens: 40_000, cache_read_tokens: 980_000 },
    ],
  },
  error: null,
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
  await page.route("**/v1/usage/cost*", async (route) => {
    await route.fulfill({ json: COST });
  });
  await page.route("**/v1/usage/tokens*", async (route) => {
    await route.fulfill({ json: TOKENS });
  });
});

test("usage page renders billed cost + token totals", async ({ page }) => {
  await login(page);
  await page.goto("/settings/usage");

  await expect(page.getByTestId("usage-root")).toBeVisible();
  await expect(page.getByTestId("usage-cost-table")).toBeVisible();
  // Total billed = 4_820_000 micros → $4.8200.
  await expect(page.getByTestId("usage-summary")).toContainText("$4.8200");
  await expect(page.getByTestId("usage-token-totals")).toBeVisible();
  // Unpriced tag surfaces on the research-assistant row.
  await expect(page.getByTestId("usage-unpriced-research-assistant")).toBeVisible();
});

test("usage page passes axe", async ({ page }) => {
  await login(page);
  await page.goto("/settings/usage");
  await expect(page.getByTestId("usage-cost-table")).toBeVisible();
  await expectNoA11yViolations(page, "settings-usage");
});
