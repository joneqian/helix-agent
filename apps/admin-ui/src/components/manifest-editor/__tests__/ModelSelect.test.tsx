import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import "../../../i18n";
import type { ModelCatalog } from "../../../api/model_catalog";
import type { ModelFields } from "../form_model";
import { ModelSelect } from "../widgets/ModelSelect";

/**
 * In jsdom, Antd's Select renders each option twice: a visible, clickable
 * `.ant-select-item-option` div and a hidden ARIA `role="option"` mirror with
 * the same text. This helper opens the given combobox and clicks the real
 * `.ant-select-item-option-content` carrying the requested label.
 */
async function pickOption(
  user: ReturnType<typeof userEvent.setup>,
  combobox: HTMLElement,
  label: string,
): Promise<void> {
  await user.click(combobox);
  const item = await screen.findByText(
    (_content, el) =>
      el?.classList.contains("ant-select-item-option-content") === true &&
      el.textContent === label,
  );
  await user.click(item);
}

const CATALOG: ModelCatalog = {
  providers: [
    {
      provider: "deepseek",
      models: [
        {
          name: "deepseek-v4-pro",
          vision: false,
          embeddings: false,
          context_window: 1000000,
          deprecated: false,
        },
      ],
    },
    {
      provider: "openai",
      models: [
        {
          name: "gpt-5.5",
          vision: true,
          embeddings: false,
          context_window: 128000,
          deprecated: false,
        },
        {
          name: "text-embedding-3-large",
          vision: false,
          embeddings: true,
          context_window: null,
          deprecated: false,
        },
      ],
    },
  ],
};

function renderSelect(value: ModelFields, onChange = vi.fn()) {
  return {
    onChange,
    ...render(
      <ModelSelect value={value} catalog={CATALOG} onChange={onChange} />,
    ),
  };
}

describe("ModelSelect", () => {
  it("selecting a provider resets name + supports_vision", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderSelect({}, onChange);
    const provider = within(
      screen.getByTestId("model-select-provider"),
    ).getByRole("combobox");
    await pickOption(user, provider, "openai");
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: "openai",
        name: undefined,
        supports_vision: false,
      }),
    );
  });

  it("selecting a vision model auto-sets supports_vision from the catalog entry", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderSelect({ provider: "openai" }, onChange);
    const nameSel = within(screen.getByTestId("model-select-name")).getByRole(
      "combobox",
    );
    await pickOption(user, nameSel, "gpt-5.5");
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: "openai",
        name: "gpt-5.5",
        supports_vision: true,
      }),
    );
  });

  it("renders the temperature control with the current value", () => {
    renderSelect({ provider: "openai", name: "gpt-5.5", temperature: 0.7 });
    const row = screen.getByTestId("model-select-temperature");
    expect(row).toBeInTheDocument();
    expect(row).toHaveTextContent(/0\.7/);
  });

  it("temperature slider change calls onChange with the new temperature", () => {
    // rc-slider's onChange doesn't fire from synthetic pointer/keyboard events
    // in jsdom (it reads layout geometry it can't measure), so drive the
    // handle's keyDown directly — rc-slider's keyboard handler is wired here.
    const onChange = vi.fn();
    renderSelect(
      { provider: "openai", name: "gpt-5.5", temperature: 0.2 },
      onChange,
    );
    const slider = within(
      screen.getByTestId("model-select-temperature"),
    ).getByRole("slider");
    fireEvent.keyDown(slider, { key: "ArrowUp", keyCode: 38 });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ temperature: expect.any(Number) }),
    );
  });

  it("advanced panel exposes max_tokens and rate_limit_rpm inputs", async () => {
    const user = userEvent.setup();
    renderSelect({ provider: "openai", name: "gpt-5.5" });
    await user.click(
      within(screen.getByTestId("model-select-advanced")).getByText("Advanced"),
    );
    const advanced = screen.getByTestId("model-select-advanced");
    expect(within(advanced).getByText("max_tokens")).toBeInTheDocument();
    expect(within(advanced).getByText("rate_limit_rpm")).toBeInTheDocument();
  });

  it("renders translated vision label, not the raw i18n key", () => {
    renderSelect({
      provider: "deepseek",
      name: "deepseek-v4-pro",
      supports_vision: false,
    });
    expect(
      screen.queryByText("model_select.vision_off"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("model-select-vision")).toHaveTextContent(
      /视觉|Vision/,
    );
  });

  const optionContent = (label: string) => (_c: string, el: Element | null) =>
    el?.classList.contains("ant-select-item-option-content") === true &&
    el.textContent === label;

  it("visionOnly hides providers with no vision model", async () => {
    const user = userEvent.setup();
    render(
      <ModelSelect
        visionOnly
        value={{}}
        catalog={CATALOG}
        onChange={vi.fn()}
      />,
    );
    const provider = within(
      screen.getByTestId("model-select-provider"),
    ).getByRole("combobox");
    await user.click(provider);
    // openai has gpt-5.5 (vision) → shown; deepseek has no vision model → hidden.
    expect(
      await screen.findByText(optionContent("openai")),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(optionContent("deepseek")),
    ).not.toBeInTheDocument();
  });

  it("visionOnly shows only vision-capable models for a provider", async () => {
    const user = userEvent.setup();
    render(
      <ModelSelect
        visionOnly
        value={{ provider: "openai" }}
        catalog={CATALOG}
        onChange={vi.fn()}
      />,
    );
    const model = within(screen.getByTestId("model-select-name")).getByRole(
      "combobox",
    );
    await user.click(model);
    expect(
      await screen.findByText(optionContent("gpt-5.5")),
    ).toBeInTheDocument();
    // the embedding model is non-vision → excluded.
    expect(
      screen.queryByText(optionContent("text-embedding-3-large")),
    ).not.toBeInTheDocument();
  });
});
