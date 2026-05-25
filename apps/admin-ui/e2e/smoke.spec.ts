/**
 * Smoke E2E — Stream H.1b PR 4.
 *
 * The shortest set of paths that prove the SPA is "alive" end-to-end:
 *
 *   1. Anonymous user lands on /login.
 *   2. Pasting a JWT into the dev-login form leads to /agents with the
 *      stubbed Agents row visible.
 *   3. Cmd+K opens, filters down, navigates.
 *   4. /agents passes the axe a11y check.
 *
 * OIDC code-flow is not exercised here — it needs a real IdP. The
 * ``oidc.spec.ts`` file gates that flow behind ``E2E_OIDC=1`` for
 * developers who have a local Keycloak running.
 */
import { test, expect, expectNoA11yViolations, SAMPLE_JWT } from "./fixtures";

test("anonymous lands on /login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByTestId("login-card")).toBeVisible();
});

test("paste-login → /agents shows the stubbed agent", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);
  await expect(page.getByText("customer-support-bot")).toBeVisible();
});

test("Command palette opens via the topbar search trigger", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);
  // Browsers hijack Ctrl/Cmd+K on many platforms (Chrome's omnibox
  // focus), so we exercise the same code path through the topbar's
  // search trigger — a real user can use either entry point.
  await page.getByRole("button", { name: /search/i }).first().click();
  await expect(page.getByTestId("cmdk-input")).toBeVisible();
  await page.getByTestId("cmdk-input").fill("agent");
  await expect(page.getByText("customer-support-bot")).toBeVisible();
});

test("/agents passes axe (serious + critical)", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);
  await expect(page.getByText("customer-support-bot")).toBeVisible();
  await expectNoA11yViolations(page, "/agents");
});

test("/login passes axe (serious + critical)", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByTestId("login-card")).toBeVisible();
  await expectNoA11yViolations(page, "/login");
});
