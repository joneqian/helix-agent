/**
 * Artifacts SDK tests — Stream H.8 PR 1.
 *
 * ``filenameFromDisposition`` is the only pure logic in the SDK (the
 * rest is a thin axios pass-through covered by the page tests).
 */
import { describe, expect, it } from "vitest";

import { filenameFromDisposition } from "../artifacts";

describe("filenameFromDisposition", () => {
  it("prefers the RFC 5987 UTF-8 form", () => {
    const header =
      "attachment; filename=\"q2-report.md\"; filename*=UTF-8''%E5%AD%A3%E6%8A%A5.md";
    expect(filenameFromDisposition(header, "fallback")).toBe("季报.md");
  });

  it("falls back to the quoted ASCII form", () => {
    expect(filenameFromDisposition('attachment; filename="plain.txt"', "fallback")).toBe(
      "plain.txt",
    );
  });

  it("falls back to the artifact name when the header is missing", () => {
    expect(filenameFromDisposition(undefined, "my-artifact")).toBe("my-artifact");
  });

  it("survives a malformed UTF-8 escape by falling through", () => {
    const header = "attachment; filename=\"safe.bin\"; filename*=UTF-8''%ZZbad";
    expect(filenameFromDisposition(header, "fallback")).toBe("safe.bin");
  });
});
