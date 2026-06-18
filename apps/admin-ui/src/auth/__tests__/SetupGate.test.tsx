/**
 * SetupGate tests — first-run routing gate.
 *
 * The gate probes ``getSetupStatus`` once and steers:
 *   - initialized=false → redirect non-/setup paths to /setup
 *   - initialized=true  → leave the app alone (children render)
 *   - probe failure     → pass through (don't trap the user)
 */
import { describe, expect, it, beforeEach, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";

import { SetupGate } from "../SetupGate";
import { getSetupStatus } from "../../api/setup";

vi.mock("../../api/setup", () => ({
  getSetupStatus: vi.fn(),
}));

const mockGetSetupStatus = vi.mocked(getSetupStatus);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SetupGate>
        <Routes>
          <Route path="/setup" element={<div data-testid="setup-page" />} />
          <Route path="/agents" element={<div data-testid="home-page" />} />
          <Route path="/" element={<div data-testid="root-page" />} />
        </Routes>
      </SetupGate>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockGetSetupStatus.mockReset();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

describe("SetupGate", () => {
  it("redirects to /setup when the platform is not initialized", async () => {
    mockGetSetupStatus.mockResolvedValue({
      initialized: false,
      setup_enabled: true,
    });
    renderAt("/agents");

    expect(await screen.findByTestId("setup-page")).toBeInTheDocument();
    expect(screen.queryByTestId("home-page")).not.toBeInTheDocument();
  });

  it("does not redirect when the platform is already initialized", async () => {
    mockGetSetupStatus.mockResolvedValue({
      initialized: true,
      setup_enabled: false,
    });
    renderAt("/agents");

    expect(await screen.findByTestId("home-page")).toBeInTheDocument();
    expect(screen.queryByTestId("setup-page")).not.toBeInTheDocument();
  });

  it("bounces away from /setup once initialized", async () => {
    mockGetSetupStatus.mockResolvedValue({
      initialized: true,
      setup_enabled: false,
    });
    renderAt("/setup");

    expect(await screen.findByTestId("root-page")).toBeInTheDocument();
    expect(screen.queryByTestId("setup-page")).not.toBeInTheDocument();
  });

  it("passes through when the probe fails (backend unreachable)", async () => {
    mockGetSetupStatus.mockRejectedValue(new Error("network down"));
    renderAt("/agents");

    await waitFor(() =>
      expect(screen.getByTestId("home-page")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("setup-page")).not.toBeInTheDocument();
  });
});
