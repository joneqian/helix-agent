/**
 * ApprovalPendingBadge tests — Stream H.3 PR 6.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import "../../i18n";

import * as approvalsSdk from "../../api/approvals";
import { ApprovalPendingBadge } from "../ApprovalPendingBadge";

const listApprovalsMock = vi.spyOn(approvalsSdk, "listApprovals");

beforeEach(() => {
  listApprovalsMock.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ApprovalPendingBadge", () => {
  it("renders children only when total=0", async () => {
    listApprovalsMock.mockResolvedValue({ items: [], total: 0, limit: 1, offset: 0 });
    render(
      <ApprovalPendingBadge>
        <span data-testid="label">Runs</span>
      </ApprovalPendingBadge>,
    );
    await waitFor(() => {
      expect(listApprovalsMock).toHaveBeenCalledWith({ status: "pending", limit: 1 });
    });
    expect(screen.queryByTestId("approval-pending-badge")).toBeNull();
    expect(screen.getByTestId("label")).toBeInTheDocument();
  });

  it("renders the red dot badge when total>0", async () => {
    listApprovalsMock.mockResolvedValue({ items: [], total: 3, limit: 1, offset: 0 });
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
    listApprovalsMock.mockResolvedValue({ items: [], total: 0, limit: 1, offset: 0 });
    render(
      <ApprovalPendingBadge>
        <span>Runs</span>
      </ApprovalPendingBadge>,
    );
    await waitFor(() => expect(listApprovalsMock).toHaveBeenCalledTimes(1));
    await act(async () => {
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => "visible",
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(() => expect(listApprovalsMock).toHaveBeenCalledTimes(2));
  });

  it("swallows transient listApprovals errors and keeps rendering children", async () => {
    listApprovalsMock.mockRejectedValue(new Error("network"));
    render(
      <ApprovalPendingBadge>
        <span data-testid="label">Runs</span>
      </ApprovalPendingBadge>,
    );
    await waitFor(() => expect(listApprovalsMock).toHaveBeenCalled());
    expect(screen.getByTestId("label")).toBeInTheDocument();
    expect(screen.queryByTestId("approval-pending-badge")).toBeNull();
  });
});
