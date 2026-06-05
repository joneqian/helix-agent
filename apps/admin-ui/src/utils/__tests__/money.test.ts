/**
 * formatMicros tests — Stream Z3.
 */
import { describe, expect, it } from "vitest";

import { formatMicros } from "../money";

describe("formatMicros", () => {
  it("formats whole dollars with 4dp", () => {
    expect(formatMicros(1_200_000)).toBe("$1.2000");
  });

  it("formats zero as $0.0000", () => {
    expect(formatMicros(0)).toBe("$0.0000");
  });

  it("formats one dollar exactly", () => {
    expect(formatMicros(1_000_000)).toBe("$1.0000");
  });

  it("renders tiny sub-cent costs with 4dp precision", () => {
    // 250 micros = $0.00025.
    expect(formatMicros(250)).toBe("$0.0003");
    // 1 micro = $0.000001 → rounds to $0.0000 at 4dp.
    expect(formatMicros(1)).toBe("$0.0000");
  });

  it("adds thousands separators for large values", () => {
    // 1,234,567 USD.
    expect(formatMicros(1_234_567_000_000)).toBe("$1,234,567.0000");
  });

  it("handles non-finite input without throwing", () => {
    expect(formatMicros(Number.NaN)).toBe("$0.0000");
    expect(formatMicros(Number.POSITIVE_INFINITY)).toBe("$0.0000");
  });
});
