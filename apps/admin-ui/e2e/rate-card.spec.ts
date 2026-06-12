/**
 * Rate Card page E2E — Stream H.9 PR 1.
 *
 * Smoke: /settings/rate-card is routed; with the fixture's non-admin
 * identity the H-22 gate renders (the row-rendering path is covered by
 * vitest with a mocked admin identity — the fixture JWT reports
 * ``is_system_admin: false``).
 */
import { test, expect, SAMPLE_JWT } from "./fixtures";

test("/settings/rate-card renders the system_admin gate for non-admins", async ({ page }) => {
  await page.route("**/v1/platform/rate-card*", async (route) => {
    await route.fulfill({ json: { success: true, data: [], error: null } });
  });

  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);

  await page.goto("/settings/rate-card");
  await expect(page.getByTestId("rate-card-root")).toBeVisible();
  await expect(page.getByTestId("rate-card-forbidden")).toBeVisible();
});
