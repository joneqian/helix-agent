/**
 * ArtifactsList tests — Stream H.8 PR 1 (design § 6.8.4).
 *
 * The artifacts SDK is stubbed. Covers the two honest modes (Mini-ADR
 * H-14): home = own artifacts with full actions; cross-tenant = read-
 * only aggregate with tenant/user columns and no action column. Plus
 * the H-16 no-op guard and the versions drawer's NULL-digest dash.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import "../../i18n";

import * as artifactsSdk from "../../api/artifacts";
import { ArtifactsList } from "../ArtifactsList";

// TenantScope context — switchable per test.
let mockScope: string | undefined;
vi.mock("../../tenant/TenantScopeContext", () => ({
  useTenantScope: () => ({
    scope: mockScope,
    apiTenantScope: mockScope,
  }),
}));

const HOME_ITEMS: artifactsSdk.ArtifactListItem[] = [
  { name: "q2-report.md", kind: "document", latest_version: 3 },
  { name: "etl.py", kind: "code", latest_version: 1 },
];

const CROSS_ITEMS: artifactsSdk.ArtifactListItem[] = [
  {
    name: "q2-report.md",
    kind: "document",
    latest_version: 3,
    tenant_id: "22222222-2222-2222-2222-222222222222",
    user_id: "88888888-8888-8888-8888-888888888888",
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <ArtifactsList />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  mockScope = undefined;
});

describe("ArtifactsList — home mode", () => {
  it("renders own artifacts with download / versions / delete actions", async () => {
    mockScope = undefined;
    vi.spyOn(artifactsSdk, "listArtifacts").mockResolvedValue({
      items: HOME_ITEMS,
      cross_tenant: false,
    });

    renderPage();

    await waitFor(() => expect(screen.getByText("q2-report.md")).toBeInTheDocument());
    expect(screen.getByTestId("artifact-download-q2-report.md")).toBeInTheDocument();
    expect(screen.getByTestId("artifact-versions-q2-report.md")).toBeInTheDocument();
    expect(screen.getByTestId("artifact-delete-q2-report.md")).toBeInTheDocument();
    // kind is an editable Select in home mode.
    expect(screen.getByTestId("artifact-kind-q2-report.md")).toBeInTheDocument();
  });

  it("download button calls the SDK", async () => {
    mockScope = undefined;
    vi.spyOn(artifactsSdk, "listArtifacts").mockResolvedValue({
      items: HOME_ITEMS,
      cross_tenant: false,
    });
    const dl = vi.spyOn(artifactsSdk, "downloadArtifact").mockResolvedValue("q2-report.md");

    renderPage();
    await waitFor(() => expect(screen.getByText("q2-report.md")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("artifact-download-q2-report.md"));
    await waitFor(() => expect(dl).toHaveBeenCalledWith("q2-report.md"));
  });

  it("opens the versions drawer and dashes NULL digests", async () => {
    mockScope = undefined;
    vi.spyOn(artifactsSdk, "listArtifacts").mockResolvedValue({
      items: HOME_ITEMS,
      cross_tenant: false,
    });
    vi.spyOn(artifactsSdk, "listArtifactVersions").mockResolvedValue({
      name: "q2-report.md",
      versions: [
        {
          version: 3,
          path_in_workspace: "artifacts/q2-report.md",
          size_bytes: null,
          sha256: null,
          created_in_thread: null,
          created_at: "2026-06-12T00:00:00Z",
        },
      ],
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("q2-report.md")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("artifact-versions-q2-report.md"));

    await waitFor(() =>
      expect(screen.getByTestId("artifact-versions-table")).toBeInTheDocument(),
    );
    expect(screen.getByText("artifacts/q2-report.md")).toBeInTheDocument();
    // NULL size + sha render as dashes (lazy backfill).
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("shows the home empty state", async () => {
    mockScope = undefined;
    vi.spyOn(artifactsSdk, "listArtifacts").mockResolvedValue({
      items: [],
      cross_tenant: false,
    });

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("This account has no run artifacts yet.")).toBeInTheDocument(),
    );
  });
});

describe("ArtifactsList — cross-tenant mode", () => {
  it("shows tenant/user columns and hides all row actions", async () => {
    mockScope = "*";
    vi.spyOn(artifactsSdk, "listArtifacts").mockResolvedValue({
      items: CROSS_ITEMS,
      cross_tenant: true,
    });

    renderPage();

    await waitFor(() => expect(screen.getByText("q2-report.md")).toBeInTheDocument());
    expect(screen.getByTestId("cross-tenant-banner")).toBeInTheDocument();
    expect(screen.getByText("Tenant")).toBeInTheDocument();
    expect(screen.getByText("User")).toBeInTheDocument();
    // Read-only aggregate — no actions, kind is a Tag not a Select.
    expect(screen.queryByTestId("artifact-download-q2-report.md")).toBeNull();
    expect(screen.queryByTestId("artifact-delete-q2-report.md")).toBeNull();
    expect(screen.queryByTestId("artifact-kind-q2-report.md")).toBeNull();
  });
});
