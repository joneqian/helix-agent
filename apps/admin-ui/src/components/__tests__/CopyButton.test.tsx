import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../i18n";

import { CopyButton } from "../CopyButton";

describe("CopyButton", () => {
  it("writes the text to the clipboard on click", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    render(<CopyButton text='{"a":1}' testId="copy-btn" />);
    await user.click(screen.getByTestId("copy-btn"));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith('{"a":1}'));
  });

  it("swallows clipboard failures without throwing", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    render(<CopyButton text="x" testId="copy-btn" />);
    await user.click(screen.getByTestId("copy-btn"));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    // No throw → button still in the document.
    expect(screen.getByTestId("copy-btn")).toBeInTheDocument();
  });
});
