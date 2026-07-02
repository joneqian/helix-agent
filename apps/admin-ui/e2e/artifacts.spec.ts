/**
 * Artifact governance E2E — conversation-centric IA M3 (H.8-F1).
 *
 * The former top-level /artifacts page is gone; the governance surface
 * (download / versions / delete / re-classify) lives on the user
 * detail's Artifacts tab, targeted at one member via ``?user_id=``.
 * The artifacts route is registered here (the shared fixture has no
 * /v1/artifacts default); most-recently-added handlers win.
 */
import { test, expect, SAMPLE_JWT } from "./fixtures";

const USER_ID = "88888888-8888-8888-8888-888888888888";

const ARTIFACTS_RESPONSE = {
  artifacts: [],
  items: [
    { name: "q2-report.md", kind: "document", latest_version: 3 },
    { name: "etl.py", kind: "code", latest_version: 1 },
  ],
  cross_tenant: false,
};

test("user-detail artifacts tab renders rows with governance actions", async ({ page }) => {
  await page.route("**/v1/artifacts*", async (route) => {
    await route.fulfill({ json: ARTIFACTS_RESPONSE });
  });

  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);

  await page.goto(`/agents/customer-support-bot/3.4.2/users/${USER_ID}`);
  await expect(page.getByTestId("user-detail-root")).toBeVisible();
  await page.getByRole("tab", { name: /Artifacts|产物/ }).click();

  await expect(page.getByTestId("user-artifacts-table")).toBeVisible();
  await expect(page.getByText("q2-report.md")).toBeVisible();
  await expect(page.getByTestId("artifact-download-q2-report.md")).toBeVisible();
  await expect(page.getByTestId("artifact-versions-etl.py")).toBeVisible();
  await expect(page.getByTestId("artifact-delete-q2-report.md")).toBeVisible();
});

test("top-level /artifacts route is gone (404 catch-all)", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await page.goto("/artifacts");
  await expect(page.getByText("404")).toBeVisible();
});
