/**
 * TraceToolbar tests — Stream H.3 PR 6.
 *
 * Three scenarios:
 *   - No trace_id → muted placeholder, no copy/link controls.
 *   - trace_id present + VITE_LANGFUSE_BASE_URL unset → chip + copy only.
 *   - trace_id present + VITE_LANGFUSE_BASE_URL set → external link
 *     renders + href is the trailing-slash-normalised URL.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "antd";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../i18n";

import { TraceToolbar } from "../run_detail/TraceToolbar";

function renderToolbar(traceId: string | null) {
  return render(
    <App>
      <TraceToolbar traceId={traceId} />
    </App>,
  );
}

beforeEach(() => {
  vi.unstubAllEnvs();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("TraceToolbar", () => {
  it("shows the no-trace placeholder when trace_id is null", () => {
    renderToolbar(null);
    expect(screen.getByTestId("trace-toolbar-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("trace-toolbar-id")).toBeNull();
    expect(screen.queryByTestId("trace-toolbar-langfuse")).toBeNull();
  });

  it("renders the chip + copy button when trace_id is present (no Langfuse url)", async () => {
    vi.stubEnv("VITE_LANGFUSE_BASE_URL", "");
    renderToolbar("abc123");
    expect(screen.getByTestId("trace-toolbar-id")).toHaveTextContent("abc123");
    expect(screen.getByTestId("trace-toolbar-copy")).toBeInTheDocument();
    // Without VITE_LANGFUSE_BASE_URL the link is hidden (the tooltip
    // hint is a plain text node, not the anchor).
    expect(screen.queryByTestId("trace-toolbar-langfuse")).toBeNull();
  });

  it("renders the Langfuse external link when VITE_LANGFUSE_BASE_URL is set", () => {
    vi.stubEnv("VITE_LANGFUSE_BASE_URL", "https://langfuse.example.com/");
    renderToolbar("abc123");
    const link = screen.getByTestId("trace-toolbar-langfuse");
    expect(link).toHaveAttribute(
      "href",
      "https://langfuse.example.com/trace/abc123",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("copies the trace_id to the clipboard when the copy button is clicked", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    renderToolbar("abc123");
    await user.click(screen.getByTestId("trace-toolbar-copy"));
    expect(writeText).toHaveBeenCalledWith("abc123");
  });
});
