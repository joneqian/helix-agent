/**
 * OIDC code-flow E2E — Stream H.1b PR 4.
 *
 * Skipped unless ``E2E_OIDC=1`` is set in the environment and the dev
 * server was started with ``VITE_OIDC_ISSUER`` etc. configured to a
 * working IdP. Local developers running ``docs/dev/oidc-keycloak.md``
 * can opt in with::
 *
 *   E2E_OIDC=1 pnpm e2e
 *
 * In CI the gate stays off — the workflow doesn't stand up Keycloak.
 * Real-IdP coverage moves to a separate matrix variant later.
 */
import { test, expect } from "./fixtures";

const enabled = process.env.E2E_OIDC === "1";

test.describe("OIDC code-flow", () => {
  test.skip(!enabled, "Set E2E_OIDC=1 with a Keycloak / Auth0 / Okta IdP available");

  test("Login page shows the SSO button when OIDC is configured", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByTestId("login-sso")).toBeVisible();
    // The dev-login toggle should also be present, but collapsed.
    await expect(page.getByTestId("login-dev-toggle")).toBeVisible();
    await expect(page.getByTestId("login-dev-form")).not.toBeVisible();
  });
});
