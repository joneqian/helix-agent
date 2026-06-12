/**
 * Approvals queue smoke — Stream HX-7 PR 3.
 *
 * The control-plane stub returns one pending approval; the page must
 * render the queue row, its run link, and the decision buttons, and
 * pass the axe check. Decisions themselves are unit-tested (the
 * vitest suite stubs the SDK); E2E proves the route + nav wiring.
 */
import { test, expect, expectNoA11yViolations, SAMPLE_JWT } from "./fixtures";

test("/approvals renders the pending queue", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);

  await page.goto("/approvals");
  await expect(page.getByTestId("approvals-table")).toBeVisible();
  await expect(page.getByText("approval-gated tool 'send_email'")).toBeVisible();
  await expect(
    page.getByTestId("approval-approve-44444444-4444-4444-4444-444444444444"),
  ).toBeVisible();
});

test("/approvals passes axe (serious + critical)", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await page.goto("/approvals");
  await expect(page.getByTestId("approvals-table")).toBeVisible();
  await expectNoA11yViolations(page, "/approvals");
});
