/**
 * SetupWizard tests — first-run platform bootstrap.
 *
 * Exercises the wizard through the ``apiClient`` adapter (same approach
 * as CreateTenantDrawer): assert the X-Setup-Token header is forwarded,
 * the password-mismatch guard blocks the POST, the success card renders,
 * and a 409 ALREADY_INITIALIZED steers the user to sign in.
 */
import { describe, expect, it, beforeEach, vi } from "vitest";
import { App } from "antd";
import { MemoryRouter } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../i18n";

import { SetupWizard } from "../SetupWizard";
import { apiClient } from "../../api/client";

interface PostCall {
  body: Record<string, unknown>;
  setupToken: string | undefined;
}

let postCalls: PostCall[];
type PostResponse = "ok" | "already";
let postResponse: PostResponse;

function installAdapter(): void {
  postCalls = [];
  postResponse = "ok";
  apiClient.defaults.adapter = (config) => {
    const url = config.url ?? "";
    const method = (config.method ?? "get").toLowerCase();
    if (url === "/v1/setup" && method === "post") {
      const body =
        typeof config.data === "string"
          ? JSON.parse(config.data)
          : (config.data ?? {});
      const headers = (config.headers ?? {}) as Record<string, unknown>;
      const setupToken = headers["X-Setup-Token"];
      postCalls.push({
        body,
        setupToken: typeof setupToken === "string" ? setupToken : undefined,
      });
      if (postResponse === "already") {
        return Promise.reject({
          isAxiosError: true,
          response: {
            status: 409,
            data: {
              detail: {
                code: "ALREADY_INITIALIZED",
                message: "platform already initialized",
              },
            },
          },
          config,
          message: "Request failed with status code 409",
        });
      }
      return Promise.resolve({
        data: {
          success: true,
          data: {
            tenant_id: "11111111-1111-1111-1111-111111111111",
            subject_id: "22222222-2222-2222-2222-222222222222",
          },
          error: null,
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    }
    return Promise.resolve({
      data: {},
      status: 200,
      statusText: "OK",
      headers: {},
      config,
      request: {},
    });
  };
}

function renderWizard(): void {
  render(
    <MemoryRouter initialEntries={["/setup"]}>
      <App>
        <SetupWizard />
      </App>
    </MemoryRouter>,
  );
}

async function fillValidForm(
  user: ReturnType<typeof userEvent.setup>,
  opts: { password?: string; confirm?: string } = {},
): Promise<void> {
  const password = opts.password ?? "hunter2hunter2";
  const confirm = opts.confirm ?? password;
  await user.type(screen.getByTestId("setup-admin-email"), "admin@example.com");
  await user.type(screen.getByTestId("setup-admin-password"), password);
  await user.type(screen.getByTestId("setup-admin-password-confirm"), confirm);
  await user.type(screen.getByTestId("setup-token"), "deploy-token");
}

beforeEach(() => {
  installAdapter();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

describe("SetupWizard", () => {
  it("renders the bootstrap form", () => {
    renderWizard();
    expect(screen.getByTestId("setup-form")).toBeInTheDocument();
    expect(screen.getByTestId("setup-submit")).toBeInTheDocument();
    // Platform name defaults to "Platform".
    expect(screen.getByTestId("setup-platform-name")).toHaveValue("Platform");
  });

  it("blocks submission when the passwords do not match", async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillValidForm(user, {
      password: "hunter2hunter2",
      confirm: "different-pass",
    });
    await user.click(screen.getByTestId("setup-submit"));

    expect(
      await screen.findByText(/do not match|不一致/),
    ).toBeInTheDocument();
    expect(postCalls).toHaveLength(0);
  });

  it("submits with the X-Setup-Token header on a valid form", async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillValidForm(user);
    await user.click(screen.getByTestId("setup-submit"));

    await waitFor(() => expect(postCalls).toHaveLength(1));
    expect(postCalls[0].setupToken).toBe("deploy-token");
    expect(postCalls[0].body.admin_email).toBe("admin@example.com");
    expect(postCalls[0].body.admin_password).toBe("hunter2hunter2");
    expect(postCalls[0].body.platform_tenant_display_name).toBe("Platform");
    // The confirm field is client-only — never sent to the backend.
    expect(postCalls[0].body).not.toHaveProperty("admin_password_confirm");
  });

  it("renders the success card after creating the admin", async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillValidForm(user);
    await user.click(screen.getByTestId("setup-submit"));

    expect(await screen.findByTestId("setup-go-login")).toBeInTheDocument();
  });

  it("steers to sign in when the platform is already initialized (409)", async () => {
    const user = userEvent.setup();
    renderWizard();
    postResponse = "already";
    await fillValidForm(user);
    await user.click(screen.getByTestId("setup-submit"));

    await waitFor(() => expect(postCalls).toHaveLength(1));
    expect(
      await screen.findByTestId("setup-already-login"),
    ).toBeInTheDocument();
  });
});
