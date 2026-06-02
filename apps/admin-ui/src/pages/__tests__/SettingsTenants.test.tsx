/**
 * Tenants page tests — system_admin gate + list render + Manage action.
 *
 * Manage switches the tenant scope into the row's tenant (persisted to
 * sessionStorage by TenantScopeProvider) and navigates to the per-tenant
 * config page. The non-admin path renders the gate alert and never hits the
 * list API.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../i18n";

import { SettingsTenants } from "../SettingsTenants";
import { AuthProvider } from "../../auth/AuthContext";
import { TenantScopeProvider } from "../../tenant/TenantScopeContext";
import { setStoredToken } from "../../api/client";
import { listTenants } from "../../api/tenants";

const mockNavigate = vi.fn();

vi.mock("../../api/tenants", () => ({
  listTenants: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return { ...actual, useNavigate: () => mockNavigate };
});

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function renderPage(): void {
  render(
    <MemoryRouter>
      <AuthProvider>
        <TenantScopeProvider>
          <App>
            <SettingsTenants />
          </App>
        </TenantScopeProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  setStoredToken(null);
  window.sessionStorage.clear();
  vi.clearAllMocks();
});

describe("SettingsTenants", () => {
  it("lists tenants for a system_admin", async () => {
    setStoredToken(
      makeJwt({ sub: "u1", tenant_id: "t1", roles: ["admin", "system_admin"] }),
    );
    vi.mocked(listTenants).mockResolvedValue([
      {
        tenant_id: "11111111-1111-1111-1111-111111111111",
        display_name: "乐毅大公司",
        plan: "free",
        created_at: "2026-06-02T00:00:00Z",
      },
    ]);
    renderPage();

    expect(await screen.findByText("乐毅大公司")).toBeInTheDocument();
  });

  it("Manage switches scope and navigates to tenant config", async () => {
    const user = userEvent.setup();
    setStoredToken(
      makeJwt({ sub: "u1", tenant_id: "t1", roles: ["admin", "system_admin"] }),
    );
    vi.mocked(listTenants).mockResolvedValue([
      {
        tenant_id: "11111111-1111-1111-1111-111111111111",
        display_name: "乐毅大公司",
        plan: "free",
        created_at: "2026-06-02T00:00:00Z",
      },
    ]);
    renderPage();

    await screen.findByText("乐毅大公司");
    await user.click(
      screen.getByTestId("st-manage-11111111-1111-1111-1111-111111111111"),
    );

    expect(mockNavigate).toHaveBeenCalledWith("/settings/tenant-config");
    expect(window.sessionStorage.getItem("helix.admin.tenantScope")).toBe(
      "11111111-1111-1111-1111-111111111111",
    );
  });

  it("gates non-admins and never lists", async () => {
    setStoredToken(makeJwt({ sub: "u1", tenant_id: "t1", roles: ["admin"] }));
    renderPage();

    expect(await screen.findByTestId("st-not-admin")).toBeInTheDocument();
    expect(listTenants).not.toHaveBeenCalled();
  });
});
