/**
 * MarkdownView tests — assistant/history text renders as markdown, and
 * untrusted raw HTML from model output is stripped (no injection).
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { MarkdownView } from "../MarkdownView";

describe("MarkdownView", () => {
  it("renders headings, bold and lists as elements", () => {
    const { container } = render(
      <MarkdownView>{"## 标题\n\n**粗体** 文本\n\n- 一\n- 二"}</MarkdownView>,
    );
    expect(container.querySelector("h2")?.textContent).toContain("标题");
    expect(container.querySelector("strong")?.textContent).toBe("粗体");
    expect(container.querySelectorAll("li")).toHaveLength(2);
  });

  it("renders links with a safe target/rel", () => {
    render(<MarkdownView>{"[deer](https://example.com)"}</MarkdownView>);
    const link = screen.getByRole("link", { name: "deer" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noreferrer");
  });

  it("does not execute raw HTML from untrusted output", () => {
    const { container } = render(
      <MarkdownView>{"hi <script>alert(1)</script> there"}</MarkdownView>,
    );
    expect(container.querySelector("script")).toBeNull();
  });
});
