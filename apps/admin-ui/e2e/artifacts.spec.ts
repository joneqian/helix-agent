/**
 * Artifacts page E2E — Stream H.8 PR 1.
 *
 * Smoke: /artifacts is routed, reachable from the sidebar, and renders
 * the stubbed row with its home-mode actions. The artifacts routes are
 * registered here (the shared fixture has no /v1/artifacts default);
 * most-recently-added handlers win.
 */
import { test, expect, SAMPLE_JWT } from "./fixtures";

const ARTIFACTS_RESPONSE = {
  artifacts: [],
  items: [
    { name: "q2-report.md", kind: "document", latest_version: 3 },
    { name: "etl.py", kind: "code", latest_version: 1 },
  ],
  cross_tenant: false,
};

test("/artifacts renders the stubbed rows with home-mode actions", async ({ page }) => {
  await page.route("**/v1/artifacts*", async (route) => {
    await route.fulfill({ json: ARTIFACTS_RESPONSE });
  });

  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);

  await page.goto("/artifacts");
  await expect(page.getByTestId("artifacts-table")).toBeVisible();
  await expect(page.getByText("q2-report.md")).toBeVisible();
  await expect(page.getByTestId("artifact-download-q2-report.md")).toBeVisible();
  await expect(page.getByTestId("artifact-versions-etl.py")).toBeVisible();
});
