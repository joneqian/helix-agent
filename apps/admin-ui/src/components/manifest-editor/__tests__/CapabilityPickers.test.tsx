import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../../i18n";

import { CapabilityPickers } from "../CapabilityPickers";
import type { AgentManifest } from "../form_model";

vi.mock("../../../api/knowledge", () => ({
  listBases: vi.fn().mockResolvedValue([
    { id: "1", name: "hr", chunk_max_tokens: 0, chunk_overlap_tokens: 0, created_at: null },
  ]),
}));
vi.mock("../../../api/skills", () => ({
  listSkills: vi.fn().mockResolvedValue({
    items: [{ id: "s1", name: "pptx" }],
    platform_items: [{ id: "s2", name: "sql" }],
    next_cursor: null,
    cross_tenant: false,
  }),
}));
vi.mock("../../../api/agents", () => ({
  listAgents: vi.fn().mockResolvedValue({
    items: [{ id: "a1", name: "deep-researcher", version: "1.0.0", status: "active" }],
    total: 1,
    cross_tenant: false,
  }),
}));

const SEED: AgentManifest = { apiVersion: "helix/v1", kind: "Agent", metadata: { name: "bot" }, spec: {} };

describe("CapabilityPickers", () => {
  it("renders the knowledge / skills / subagents sections", () => {
    render(<CapabilityPickers formData={SEED} onChange={vi.fn()} />);
    expect(screen.getByTestId("af-knowledge")).toBeInTheDocument();
    expect(screen.getByTestId("af-skills")).toBeInTheDocument();
    expect(screen.getByTestId("af-subagents")).toBeInTheDocument();
  });

  it("loads the picker option lists", async () => {
    const { listBases } = await import("../../../api/knowledge");
    render(<CapabilityPickers formData={SEED} onChange={vi.fn()} />);
    await waitFor(() => expect(listBases).toHaveBeenCalled());
  });

  it("adding a sub-agent appends an empty row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<CapabilityPickers formData={SEED} onChange={onChange} />);
    await user.click(screen.getByTestId("af-subagent-add"));
    const last = onChange.mock.calls.at(-1)?.[0] as AgentManifest;
    expect(last.spec?.subagents).toEqual([{ name: "", agent_ref: "", description: "" }]);
  });

  it("editing a sub-agent name patches that row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const seeded: AgentManifest = {
      ...SEED,
      spec: { subagents: [{ name: "", agent_ref: "", description: "" }] },
    };
    render(<CapabilityPickers formData={seeded} onChange={onChange} />);
    await user.type(screen.getByTestId("af-subagent-name-0"), "r");
    const last = onChange.mock.calls.at(-1)?.[0] as AgentManifest;
    expect(last.spec?.subagents?.[0].name).toBe("r");
  });

  it("removing the last sub-agent drops the block", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const seeded: AgentManifest = {
      ...SEED,
      spec: { subagents: [{ name: "x", agent_ref: "y@1", description: "z" }] },
    };
    render(<CapabilityPickers formData={seeded} onChange={onChange} />);
    await user.click(screen.getByTestId("af-subagent-remove-0"));
    const last = onChange.mock.calls.at(-1)?.[0] as AgentManifest;
    expect(last.spec?.subagents).toBeUndefined();
  });
});
