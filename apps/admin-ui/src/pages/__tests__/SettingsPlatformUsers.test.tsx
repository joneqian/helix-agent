/**
 * Platform Admins page tests (Stream N self-service).
 *
 * Covers the system_admin gate (non-admin sees the notice), the list
 * render, granting by subject UUID (with the invalid-UUID guard), and
 * revoking through the role-bindings API. SDK calls are spied directly.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { App } from "antd";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../i18n";

import { SettingsPlatformUsers } from "../SettingsPlatformUsers";
import * as sdk from "../../api/role_bindings";
import type { RoleBindingList } from "../../api/role_bindings";
import { AuthProvider } from "../../auth/AuthContext";
import { setStoredToken } from "../../api/client";

const SELF = "00000000-0000-0000-0000-000000000001";

const LIST: RoleBindingList = {
  items: [
    {
      id: "b1",
      tenant_id: null,
      subject_type: "user",
      subject_id: SELF,
      role: "system_admin",
      platform_scope: true,
      granted_by: "bootstrap",
      granted_at: "2026-06-10T08:00:00Z",
    },
  ],
  total: 1,
  cross_tenant: false,
};

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.`;
}

function renderPage(roles: string[]) {
  setStoredToken(makeJwt({ sub: SELF, tenant_id: "t1", roles }));
  vi.spyOn(sdk, "listRoleBindings").mockResolvedValue(LIST);
  return render(
    <MemoryRouter>
      <AuthProvider>
        <App>
          <SettingsPlatformUsers />
        </App>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("SettingsPlatformUsers", () => {
  it("shows the notice for a non-system-admin", async () => {
    renderPage(["admin"]);
    expect(await screen.findByTestId("pu-not-admin")).toBeInTheDocument();
    expect(screen.queryByTestId("pu-table")).not.toBeInTheDocument();
  });

  it("lists existing platform admins and tags the caller", async () => {
    renderPage(["system_admin"]);
    const table = await screen.findByTestId("pu-table");
    await waitFor(() =>
      expect(sdk.listRoleBindings).toHaveBeenCalledWith({ platformScope: true }),
    );
    expect(table).toHaveTextContent(SELF);
    // The caller's own row carries the "You" tag.
    expect(screen.getByText("You")).toBeInTheDocument();
  });

  it("grants a new platform admin by subject UUID", async () => {
    const user = userEvent.setup();
    const create = vi.spyOn(sdk, "createRoleBinding").mockResolvedValue({
      ...LIST.items[0],
      id: "b2",
      subject_id: "00000000-0000-0000-0000-000000000002",
    });
    renderPage(["system_admin"]);
    await screen.findByTestId("pu-table");
    await user.type(
      screen.getByTestId("pu-grant-subject"),
      "00000000-0000-0000-0000-000000000002",
    );
    await user.click(screen.getByTestId("pu-grant-submit"));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith({
        subject_type: "user",
        subject_id: "00000000-0000-0000-0000-000000000002",
        role: "system_admin",
        platform_scope: true,
      }),
    );
  });

  it("rejects an invalid (non-UUID) subject without calling the API", async () => {
    const user = userEvent.setup();
    const create = vi.spyOn(sdk, "createRoleBinding");
    renderPage(["system_admin"]);
    await screen.findByTestId("pu-table");
    await user.type(screen.getByTestId("pu-grant-subject"), "not-a-uuid");
    await user.click(screen.getByTestId("pu-grant-submit"));
    await screen.findByText(/valid UUID/i);
    expect(create).not.toHaveBeenCalled();
  });

  it("revokes a platform admin through the API", async () => {
    const user = userEvent.setup();
    const del = vi.spyOn(sdk, "deleteRoleBinding").mockResolvedValue(undefined);
    renderPage(["system_admin"]);
    await screen.findByTestId("pu-table");
    await user.click(screen.getByTestId("pu-revoke-b1"));
    // Popconfirm confirm button shares the "Delete" label; it mounts last.
    const deleteButtons = await screen.findAllByRole("button", {
      name: "Delete",
    });
    await user.click(deleteButtons[deleteButtons.length - 1]);
    await waitFor(() => expect(del).toHaveBeenCalledWith("b1"));
  });
});
