/**
 * SettingsRateCard tests — Stream H.9 PR 1 (design § 6.10.4).
 *
 * The rate-card SDK is stubbed. Covers: the H-22 frontend gate (no
 * fetch for non-admins), list render + include_expired param, the H-20
 * immutable-identity edit drawer (note + patch only sends mutable
 * fields), and delete confirm.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "antd";
import { MemoryRouter } from "react-router-dom";
import "../../i18n";

import * as rateCardSdk from "../../api/rate_card";
import { SettingsRateCard } from "../SettingsRateCard";

let mockIsSystemAdmin = true;
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    identity: { isSystemAdmin: mockIsSystemAdmin },
  }),
}));

const RECORD: rateCardSdk.RateCardRecord = {
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: null,
  provider: "anthropic",
  model: "claude-opus-4-8",
  input_token_micros: 5,
  output_token_micros: 25,
  cache_creation_token_micros: 6,
  cache_read_token_micros: 1,
  markup_bps: 1500,
  plan_tier: null,
  effective_from: "2026-06-01T00:00:00Z",
  effective_until: null,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <App>
        <SettingsRateCard />
      </App>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  mockIsSystemAdmin = true;
});

describe("SettingsRateCard", () => {
  it("gates non-system-admins without fetching (H-22)", async () => {
    mockIsSystemAdmin = false;
    const listSpy = vi.spyOn(rateCardSdk, "listRateCards");

    renderPage();

    await waitFor(() =>
      expect(screen.getByTestId("rate-card-forbidden")).toBeInTheDocument(),
    );
    expect(listSpy).not.toHaveBeenCalled();
  });

  it("renders rows and re-fetches with include_expired", async () => {
    const listSpy = vi.spyOn(rateCardSdk, "listRateCards").mockResolvedValue([RECORD]);

    renderPage();

    await waitFor(() => expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument());
    expect(screen.getByText("all plans")).toBeInTheDocument();
    expect(screen.getByText("1500 bps")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("rc-include-expired"));
    await waitFor(() =>
      expect(listSpy).toHaveBeenLastCalledWith(
        expect.objectContaining({ includeExpired: true }),
      ),
    );
  });

  it("edit drawer shows the immutable-identity note and patches only mutable fields (H-20)", async () => {
    vi.spyOn(rateCardSdk, "listRateCards").mockResolvedValue([RECORD]);
    const patchSpy = vi.spyOn(rateCardSdk, "patchRateCard").mockResolvedValue(RECORD);

    renderPage();
    await waitFor(() => expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId(`rc-edit-${RECORD.id}`));

    await waitFor(() => expect(screen.getByTestId("rc-identity-note")).toBeInTheDocument());

    await userEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    const [, patch] = patchSpy.mock.calls[0];
    // Mutable fields only — identity fields never appear in the payload.
    expect(patch).not.toHaveProperty("provider");
    expect(patch).not.toHaveProperty("model");
    expect(patch).not.toHaveProperty("plan_tier");
    expect(patch).not.toHaveProperty("effective_from");
    expect(patch).toHaveProperty("input_token_micros", 5);
  });

  it("deletes after confirm", async () => {
    vi.spyOn(rateCardSdk, "listRateCards").mockResolvedValue([RECORD]);
    const deleteSpy = vi.spyOn(rateCardSdk, "deleteRateCard").mockResolvedValue();

    renderPage();
    await waitFor(() => expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId(`rc-delete-${RECORD.id}`));
    await userEvent.click(await screen.findByText("Delete", { selector: "button span" }));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith(RECORD.id));
  });

  it("microsPerTokenToUsdPerMillion converts for the read-only hint (H-21)", () => {
    expect(rateCardSdk.microsPerTokenToUsdPerMillion(5)).toBe("$5 / 1M tokens");
    expect(rateCardSdk.microsPerTokenToUsdPerMillion(1500)).toBe("$1,500 / 1M tokens");
  });
});
