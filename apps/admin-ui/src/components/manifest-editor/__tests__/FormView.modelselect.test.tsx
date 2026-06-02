import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "../../../i18n";
import * as catalogSdk from "../../../api/model_catalog";
import { __resetCatalogCacheForTest } from "../catalog";
import { FormView } from "../FormView";

const SCHEMA = {
  type: "object",
  properties: {
    spec: {
      type: "object",
      properties: {
        model: {
          type: "object",
          properties: {
            provider: { type: "string" },
            name: { type: "string" },
            supports_vision: { type: "boolean" },
          },
        },
      },
    },
  },
} as const;

beforeEach(() => {
  __resetCatalogCacheForTest();
  vi.spyOn(catalogSdk, "fetchModelCatalog").mockResolvedValue({
    providers: [
      { provider: "deepseek", models: [{ name: "deepseek-v4-pro", vision: false, embeddings: false, context_window: 1000000, deprecated: false }] },
    ],
  });
});
afterEach(() => vi.restoreAllMocks());

describe("FormView model picker", () => {
  it("renders the ModelSelect field for spec.model once the catalog loads", async () => {
    render(<FormView schema={SCHEMA as unknown as Record<string, unknown>} formData={{ spec: { model: { provider: "deepseek" } } }} onChange={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("model-select-field")).toBeInTheDocument());
  });
});
