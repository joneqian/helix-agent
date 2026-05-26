/**
 * ApprovalPendingBadge tests — Stream H.3 PR 6.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import "../../i18n";

import * as runsSdk from "../../api/runs";
import { ApprovalPendingBadge } from "../ApprovalPendingBadge";

const listRunsMock = vi.spyOn(runsSdk, "listRuns");

beforeEach(() => {
  listRunsMock.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ApprovalPendingBadge", () => {
  it("renders children only when total=0", async () => {
    listRunsMock.mockResolvedValue({ items: [], total: 0, cross_tenant: false });
    render(
      <ApprovalPendingBadge>
        <span data-testid="label">Runs</span>
      </ApprovalPendingBadge>,
    );
    await waitFor(() => {
      expect(listRunsMock).toHaveBeenCalledWith({ status: "paused", limit: 1 });
    });
    expect(screen.queryByTestId("approval-pending-badge")).toBeNull();
    expect(screen.getByTestId("label")).toBeInTheDocument();
  });

  it("renders the red dot badge when total>0", async () => {
    listRunsMock.mockResolvedValue({ items: [], total: 3, cross_tenant: false });
    render(
      <ApprovalPendingBadge>
        <span>Runs</span>
      </ApprovalPendingBadge>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("approval-pending-badge")).toBeInTheDocument();
    });
  });

  it("re-polls on visibilitychange when the tab becomes visible", async () => {
    listRunsMock.mockResolvedValue({ items: [], total: 0, cross_tenant: false });
    render(
      <ApprovalPendingBadge>
        <span>Runs</span>
      </ApprovalPendingBadge>,
    );
    await waitFor(() => expect(listRunsMock).toHaveBeenCalledTimes(1));
    await act(async () => {
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => "visible",
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(() => expect(listRunsMock).toHaveBeenCalledTimes(2));
  });

  it("swallows transient listRuns errors and keeps rendering children", async () => {
    listRunsMock.mockRejectedValue(new Error("network"));
    render(
      <ApprovalPendingBadge>
        <span data-testid="label">Runs</span>
      </ApprovalPendingBadge>,
    );
    await waitFor(() => expect(listRunsMock).toHaveBeenCalled());
    expect(screen.getByTestId("label")).toBeInTheDocument();
    expect(screen.queryByTestId("approval-pending-badge")).toBeNull();
  });
});
