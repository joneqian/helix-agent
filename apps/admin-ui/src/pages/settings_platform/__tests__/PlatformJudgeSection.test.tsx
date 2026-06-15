import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../../i18n";
import * as sdk from "../../../api/platform_judge_config";
import type { PlatformJudgeConfigView } from "../../../api/platform_judge_config";
import { ApiError } from "../../../api/client";
import { PlatformJudgeSection } from "../PlatformJudgeSection";

const VIEW: PlatformJudgeConfigView = {
  judge: { provider: "deepseek", model: "deepseek-chat" },
  available: [
    { provider: "deepseek", model: "deepseek-chat" },
    { provider: "glm", model: "glm-4-flash" },
  ],
};

beforeEach(() => vi.spyOn(sdk, "getPlatformJudgeConfig").mockResolvedValue(VIEW));
afterEach(() => vi.restoreAllMocks());

async function pick(
  user: ReturnType<typeof userEvent.setup>,
  wrapperTestId: string,
  optionText: string,
): Promise<void> {
  await user.click(within(screen.getByTestId(wrapperTestId)).getByRole("combobox"));
  const opts = await screen.findAllByText(optionText);
  const visible =
    opts.find((el) => el.className?.includes("ant-select-item-option-content")) ?? opts[0];
  await user.click(visible);
}

describe("PlatformJudgeSection", () => {
  it("always shows the friendly explanation of what a judge is", async () => {
    render(<PlatformJudgeSection />);
    await screen.findByTestId("pj-root");
    expect(screen.getByTestId("pj-help")).toBeInTheDocument();
  });

  it("shows the current judge selection", async () => {
    render(<PlatformJudgeSection />);
    await waitFor(() => expect(screen.getByTestId("pj-root")).toBeInTheDocument());
    expect(screen.getByTestId("pj-root")).toHaveTextContent("deepseek-chat");
  });

  it("saves a new judge selection via PUT", async () => {
    const user = userEvent.setup();
    const put = vi
      .spyOn(sdk, "putPlatformJudgeConfig")
      .mockResolvedValue({ judge: { provider: "glm", model: "glm-4-flash" } });
    render(<PlatformJudgeSection />);
    await screen.findByTestId("pj-root");
    await pick(user, "pj-provider", "glm");
    await pick(user, "pj-model", "glm-4-flash");
    await user.click(screen.getByTestId("pj-save"));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith({ judge_provider: "glm", judge_model: "glm-4-flash" }),
    );
  });

  it("clears the judge (PUT nulls) and shows the unconfigured note when unset", async () => {
    const user = userEvent.setup();
    const put = vi.spyOn(sdk, "putPlatformJudgeConfig").mockResolvedValue({ judge: null });
    render(<PlatformJudgeSection />);
    await screen.findByTestId("pj-root");
    await user.click(screen.getByTestId("pj-clear"));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith({ judge_provider: null, judge_model: null }),
    );
    expect(await screen.findByTestId("pj-unconfigured")).toBeInTheDocument();
  });

  it("disables Clear when already unset", async () => {
    vi.spyOn(sdk, "getPlatformJudgeConfig").mockResolvedValueOnce({
      judge: null,
      available: VIEW.available,
    });
    render(<PlatformJudgeSection />);
    await screen.findByTestId("pj-root");
    expect(screen.getByTestId("pj-unconfigured")).toBeInTheDocument();
    expect(screen.getByTestId("pj-clear")).toBeDisabled();
    expect(screen.getByTestId("pj-save")).toBeDisabled();
  });

  it("surfaces a 422 error code as a message", async () => {
    const user = userEvent.setup();
    vi.spyOn(sdk, "putPlatformJudgeConfig").mockRejectedValue(
      new ApiError("provider key missing", "JUDGE_PROVIDER_KEY_MISSING", 422),
    );
    render(<PlatformJudgeSection />);
    await screen.findByTestId("pj-root");
    // a valid selection is preserved from VIEW, so Save is enabled
    await user.click(screen.getByTestId("pj-save"));
    expect(await screen.findByTestId("pj-error")).toBeInTheDocument();
  });
});
