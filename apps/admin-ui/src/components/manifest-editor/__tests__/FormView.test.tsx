import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../../i18n";

import * as catalog from "../catalog";
import { FormView } from "../FormView";
import type { AgentManifest } from "../form_model";

vi.spyOn(catalog, "loadModelCatalog").mockResolvedValue({
  providers: [
    {
      provider: "openai",
      models: [
        {
          name: "gpt-4o",
          vision: true,
          embeddings: false,
          context_window: 128000,
          deprecated: false,
        },
      ],
    },
  ],
});

const SEED: AgentManifest = {
  apiVersion: "helix/v1",
  kind: "Agent",
  metadata: { name: "bot" },
  spec: {
    model: { provider: "openai", name: "gpt-4o" },
    system_prompt: { template: "hi" },
    memory: { long_term: { retrieve_top_k: 5, write_back: true, recall_mode: "per_session" } },
    sandbox: { kind: "none" },
  },
};

describe("FormView", () => {
  it("renders the curated section testids", () => {
    render(<FormView formData={SEED} onChange={vi.fn()} />);
    expect(screen.getByTestId("af-basic")).toBeInTheDocument();
    expect(screen.getByTestId("af-model")).toBeInTheDocument();
    expect(screen.getByTestId("af-prompt")).toBeInTheDocument();
    expect(screen.getByTestId("af-memory")).toBeInTheDocument();
    expect(screen.getByTestId("af-tools")).toBeInTheDocument();
  });

  it("typing the name emits a merged manifest preserving non-curated fields", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FormView formData={SEED} onChange={onChange} />);
    const input = screen.getByTestId("af-name").querySelector("input") as HTMLInputElement;
    await user.type(input, "X");
    const last = onChange.mock.calls.at(-1)?.[0] as AgentManifest;
    expect(last.metadata?.name).toBe("botX");
    expect(last.apiVersion).toBe("helix/v1");
    expect(last.spec?.sandbox).toEqual({ kind: "none" });
  });

  it("toggling memory off sets spec.memory.long_term to null", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FormView formData={SEED} onChange={onChange} />);
    await user.click(screen.getByTestId("af-memory-toggle"));
    const last = onChange.mock.calls.at(-1)?.[0] as AgentManifest;
    expect(last.spec?.memory?.long_term).toBeNull();
  });

  it("checking web search adds a builtin web_search tool entry", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FormView formData={SEED} onChange={onChange} />);
    await user.click(screen.getByTestId("af-tool-web_search"));
    const last = onChange.mock.calls.at(-1)?.[0] as AgentManifest;
    expect(last.spec?.tools).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: "builtin", name: "web_search" })]),
    );
  });

  it("editing the prompt updates spec.system_prompt.template", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FormView formData={SEED} onChange={onChange} />);
    const ta = screen.getByTestId("af-prompt-input").querySelector("textarea") as HTMLTextAreaElement;
    await user.type(ta, "!");
    const last = onChange.mock.calls.at(-1)?.[0] as AgentManifest;
    expect(last.spec?.system_prompt?.template).toBe("hi!");
  });

  it("loads the model catalog", async () => {
    render(<FormView formData={SEED} onChange={vi.fn()} />);
    await waitFor(() => expect(catalog.loadModelCatalog).toHaveBeenCalled());
  });
});
