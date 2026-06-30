import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "antd";
import type { ReactElement } from "react";
import "../../../i18n";
import * as sdk from "../../../api/platform_tool_budget_config";
import { PlatformToolBudgetSection } from "../PlatformToolBudgetSection";

// Wrap in antd <App> so the section's ``App.useApp()`` message API has context.
function renderSection(node: ReactElement) {
  return render(<App>{node}</App>);
}

beforeEach(() =>
  vi
    .spyOn(sdk, "getPlatformToolBudgetConfig")
    .mockResolvedValue({ enabled: null, effective: true }),
);
afterEach(() => vi.restoreAllMocks());

describe("PlatformToolBudgetSection", () => {
  it("shows the friendly explanation", async () => {
    renderSection(<PlatformToolBudgetSection />);
    await screen.findByTestId("ptb-root");
    expect(screen.getByTestId("ptb-help")).toBeInTheDocument();
  });

  it("reflects the effective toggle from the backend", async () => {
    renderSection(<PlatformToolBudgetSection />);
    await screen.findByTestId("ptb-root");
    expect(screen.getByTestId("ptb-toggle")).toBeChecked();
  });

  it("tags env default when no platform override is set", async () => {
    renderSection(<PlatformToolBudgetSection />);
    await screen.findByTestId("ptb-root");
    expect(screen.getByTestId("ptb-env-default")).toBeInTheDocument();
  });

  it("PUTs the new value when toggled off", async () => {
    const user = userEvent.setup();
    const put = vi
      .spyOn(sdk, "putPlatformToolBudgetConfig")
      .mockResolvedValue({ enabled: false, effective: false });
    renderSection(<PlatformToolBudgetSection />);
    await screen.findByTestId("ptb-root");
    await user.click(screen.getByTestId("ptb-toggle"));
    await waitFor(() => expect(put).toHaveBeenCalledWith(false));
  });

  it("renders the disabled state + drops the env-default tag when overridden off", async () => {
    vi.spyOn(sdk, "getPlatformToolBudgetConfig").mockResolvedValueOnce({
      enabled: false,
      effective: false,
    });
    renderSection(<PlatformToolBudgetSection />);
    await screen.findByTestId("ptb-root");
    expect(screen.getByTestId("ptb-toggle")).not.toBeChecked();
    expect(screen.queryByTestId("ptb-env-default")).not.toBeInTheDocument();
  });
});
