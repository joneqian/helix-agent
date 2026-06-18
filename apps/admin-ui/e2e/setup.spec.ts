/**
 * First-run setup wizard E2E — happy path.
 *
 * Mocks ``/v1/setup/status`` (un-initialized) so the SetupGate steers
 * the app to ``/setup``, then mocks ``/v1/setup`` so a filled form
 * resolves into the success card. Note: this opts out of the auto
 * control-plane stub's auth flow because the wizard runs anonymous.
 */
import { test, expect } from "./fixtures";

test("redirects to /setup and completes the wizard", async ({ page }) => {
  await page.route("**/v1/setup/status", async (route) => {
    await route.fulfill({
      json: {
        success: true,
        data: { initialized: false, setup_enabled: true },
        error: null,
      },
    });
  });
  await page.route("**/v1/setup", async (route) => {
    await route.fulfill({
      json: {
        success: true,
        data: {
          tenant_id: "11111111-1111-1111-1111-111111111111",
          subject_id: "22222222-2222-2222-2222-222222222222",
        },
        error: null,
      },
    });
  });

  // Any deep-link gets steered to /setup while un-initialized.
  await page.goto("/agents");
  await expect(page).toHaveURL(/\/setup$/);

  await page.getByTestId("setup-admin-email").fill("admin@example.com");
  await page.getByTestId("setup-admin-password").fill("hunter2hunter2");
  await page
    .getByTestId("setup-admin-password-confirm")
    .fill("hunter2hunter2");
  await page.getByTestId("setup-token").fill("deploy-token");
  await page.getByTestId("setup-submit").click();

  await expect(page.getByTestId("setup-go-login")).toBeVisible();
});
