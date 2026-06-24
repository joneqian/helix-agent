/**
 * MCP Catalog e2e — Stream W.
 *
 * Tenant happy path: open the "Add MCP server" drawer → browse the catalog →
 * toggle a platform server on (opt-in selection, P4 platform-server model).
 *
 * Network is fully mocked. CRITICAL: spec-level routes use ``route.fallback()``
 * (NOT ``route.continue()``) so unmatched requests fall through to the
 * fixture's global stub instead of hitting an absent backend (ECONNREFUSED).
 * Every endpoint the page touches is mocked: tenant catalog list, the
 * existing mcp-servers list, the enable toggle, and available.
 */
import { test, expect, expectNoA11yViolations, SAMPLE_JWT } from "./fixtures";

const CATALOG = {
  success: true,
  data: [
    {
      id: "cat-1",
      name: "github",
      display_name: "GitHub",
      description: "Issues, PRs and repo search.",
      category: "dev-tools",
      icon: "",
      transport: "sse",
      url_template: "https://mcp.github.com/sse",
      auth_type: "bearer",
      auth_schema: {
        fields: [{ key: "token", label: "Personal access token", kind: "secret", required: true }],
      },
      required_tier: "free",
      enabled: true,
      created_at: "2026-05-01T10:00:00Z",
      updated_at: "2026-05-01T10:00:00Z",
      updated_by: "u1",
      entitled: true,
      tenant_enabled: false,
    },
    {
      id: "cat-2",
      name: "linear",
      display_name: "Linear",
      description: "Requires the Enterprise plan.",
      category: "dev-tools",
      icon: "",
      transport: "streamable_http",
      url_template: "https://mcp.linear.app/{workspace}/mcp",
      auth_type: "bearer",
      auth_schema: {
        fields: [
          { key: "workspace", label: "Workspace", kind: "param", required: true },
          { key: "token", label: "API key", kind: "secret", required: true },
        ],
      },
      required_tier: "enterprise",
      enabled: true,
      created_at: "2026-05-10T08:00:00Z",
      updated_at: "2026-05-10T08:00:00Z",
      updated_by: "u1",
      entitled: false,
      tenant_enabled: false,
    },
  ],
  error: null,
};

const EMPTY_SERVERS = { success: true, data: [], error: null };

const ENABLE_OK = {
  success: true,
  data: { name: "github", tenant_enabled: true },
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
  // The tenant catalog list — register before the broader mcp-servers route.
  await page.route("**/v1/mcp-servers/catalog", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: CATALOG });
      return;
    }
    await route.fallback();
  });
  // Enable toggle — POST /v1/mcp-servers/catalog/{id}/enable.
  await page.route("**/v1/mcp-servers/catalog/*/enable", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 200, json: ENABLE_OK });
      return;
    }
    await route.fallback();
  });
  // Existing tenant servers list (page load).
  await page.route("**/v1/mcp-servers", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: EMPTY_SERVERS });
      return;
    }
    await route.fallback();
  });
  // Available servers — referenced elsewhere; keep mocked to avoid fallthrough.
  await page.route("**/v1/mcp-servers/available", async (route) => {
    await route.fulfill({ json: EMPTY_SERVERS });
  });
});

test("browse catalog → toggle an entitled platform server on", async ({ page }) => {
  await login(page);
  await page.goto("/settings/mcp-servers");

  await expect(page.getByTestId("ms-root")).toBeVisible();

  // Open the catalog browser.
  await page.getByTestId("ms-add").click();
  await expect(page.getByTestId("cb-root")).toBeVisible();

  // The locked (enterprise) connector shows a disabled lock badge, no toggle.
  await expect(page.getByTestId("cb-locked-linear")).toBeDisabled();
  await expect(page.getByTestId("cb-toggle-linear")).toHaveCount(0);

  // Toggle the entitled connector on → POST .../cat-1/enable.
  const [req] = await Promise.all([
    page.waitForRequest(
      (r) =>
        r.url().includes("/v1/mcp-servers/catalog/cat-1/enable") &&
        r.method() === "POST",
    ),
    page.getByTestId("cb-toggle-github").click(),
  ]);
  expect(req.method()).toBe("POST");
});

test("settings/mcp-servers add-from-catalog passes axe", async ({ page }) => {
  await login(page);
  await page.goto("/settings/mcp-servers");
  await expect(page.getByTestId("ms-root")).toBeVisible();
  await page.getByTestId("ms-add").click();
  await expect(page.getByTestId("cb-root")).toBeVisible();
  await expectNoA11yViolations(page, "settings-mcp-servers add-from-catalog");
});
