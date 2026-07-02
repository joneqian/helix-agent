/**
 * Conversations browser E2E — conversation-centric IA
 * (``docs/design/conversation-centric-ia.md`` §3 primitive ③).
 *
 * Drives a login, navigates to /conversations, and verifies the stubbed
 * conversation row renders + the page passes axe. Also asserts the old
 * ``/runs`` path redirects into the browser so bookmarks keep working.
 */
import { test, expect, expectNoA11yViolations, SAMPLE_JWT } from "./fixtures";

test("/conversations shows the stubbed conversation row after login", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);
  await page.goto("/conversations");
  await expect(page.getByText("refund question")).toBeVisible();
  await expect(page.getByText("customer-support-bot")).toBeVisible();
  await expect(page.getByText("v3.4.2")).toBeVisible();
});

test("/runs redirects to /conversations", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await page.goto("/runs");
  await expect(page).toHaveURL(/\/conversations$/);
  await expect(page.getByText("refund question")).toBeVisible();
});

test("/conversations passes axe (serious + critical)", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await page.goto("/conversations");
  await expect(page.getByText("refund question")).toBeVisible();
  await expectNoA11yViolations(page, "/conversations");
});
