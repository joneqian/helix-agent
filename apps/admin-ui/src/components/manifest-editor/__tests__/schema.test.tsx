import { afterEach, describe, expect, it, vi } from "vitest";
import * as sdk from "../../../api/manifest_schema";
import { loadAgentSchema, __resetSchemaCacheForTest } from "../schema";

afterEach(() => {
  __resetSchemaCacheForTest();
  vi.restoreAllMocks();
});

describe("loadAgentSchema", () => {
  it("fetches the schema and caches it across calls", async () => {
    const fake = { type: "object", properties: {} };
    const spy = vi.spyOn(sdk, "fetchAgentSchema").mockResolvedValue(fake);

    const first = await loadAgentSchema();
    const second = await loadAgentSchema();

    expect(first).toBe(fake);
    expect(second).toBe(fake);
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
