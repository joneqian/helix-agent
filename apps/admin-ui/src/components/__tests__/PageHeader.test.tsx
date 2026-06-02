/**
 * PageHeader tests — shared compact page header (no breadcrumb).
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { PageHeader } from "../PageHeader";

describe("PageHeader", () => {
  it("renders the title", () => {
    render(
      <MemoryRouter>
        <PageHeader title="Runs" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Runs" })).toBeInTheDocument();
  });

  it("renders the subtitle when provided", () => {
    render(
      <MemoryRouter>
        <PageHeader title="Runs" subtitle="All runs across tenants" />
      </MemoryRouter>,
    );
    expect(screen.getByText("All runs across tenants")).toBeInTheDocument();
  });

  it("renders actions when provided", () => {
    render(
      <MemoryRouter>
        <PageHeader
          title="Runs"
          actions={<button data-testid="header-action">New</button>}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("header-action")).toBeInTheDocument();
  });

  it("renders a back link to the parent list when backTo is set", () => {
    render(
      <MemoryRouter>
        <PageHeader title="Run detail" backTo={{ label: "Runs", to: "/runs" }} />
      </MemoryRouter>,
    );
    const back = screen.getByTestId("page-header-back");
    expect(back).toBeInTheDocument();
    expect(back).toHaveAttribute("href", "/runs");
    expect(back).toHaveTextContent("Runs");
  });

  it("does not render a back link without backTo", () => {
    render(
      <MemoryRouter>
        <PageHeader title="Runs" />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("page-header-back")).toBeNull();
  });
});
