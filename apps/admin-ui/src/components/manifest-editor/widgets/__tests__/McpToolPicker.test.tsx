import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "../../../../i18n";

import { McpToolPicker } from "../McpToolPicker";
import * as serversSdk from "../../../../api/mcp-servers";
import * as catalogSdk from "../../../../api/mcp-catalog";

const availableMock = vi.spyOn(serversSdk, "listAvailableMcpServers");
const catalogMock = vi.spyOn(catalogSdk, "listPlatformCatalog");

beforeEach(() => {
  availableMock.mockReset();
  catalogMock.mockReset();
});

const noop = () => {};

describe("McpToolPicker source", () => {
  it("default (available) lists opted-in servers from /available", async () => {
    availableMock.mockResolvedValue([
      { name: "amap-maps", source: "platform" },
      { name: "my-custom", source: "tenant" },
    ]);
    render(
      <McpToolPicker
        servers={[]}
        allowTools={[]}
        onServersChange={noop}
        onAllowToolsChange={noop}
      />,
    );
    expect(
      await screen.findByTestId("af-mcp-server-amap-maps"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("af-mcp-server-my-custom")).toBeInTheDocument();
    expect(catalogMock).not.toHaveBeenCalled();
  });

  it("catalog source lists published connectors (enabled only) by name", async () => {
    catalogMock.mockResolvedValue([
      {
        id: "c1",
        name: "amap-maps",
        display_name: "高德地图",
        transport: "streamable-http",
        auth_type: "none",
        category: "location",
        required_tier: "free",
        enabled: true,
      },
      {
        id: "c2",
        name: "draft-conn",
        display_name: "Draft",
        transport: "streamable-http",
        auth_type: "none",
        category: "other",
        required_tier: "free",
        enabled: false,
      },
    ] as never);
    render(
      <McpToolPicker
        source="catalog"
        servers={[]}
        allowTools={[]}
        onServersChange={noop}
        onAllowToolsChange={noop}
      />,
    );
    // Enabled connector shows with its display name; disabled one is filtered out.
    await screen.findByTestId("af-mcp-server-amap-maps");
    expect(screen.getByText("高德地图")).toBeInTheDocument();
    expect(
      screen.queryByTestId("af-mcp-server-draft-conn"),
    ).not.toBeInTheDocument();
    expect(availableMock).not.toHaveBeenCalled();
  });

  it("catalog empty state points to the MCP Catalog page", async () => {
    catalogMock.mockResolvedValue([]);
    render(
      <McpToolPicker
        source="catalog"
        servers={[]}
        allowTools={[]}
        onServersChange={noop}
        onAllowToolsChange={noop}
      />,
    );
    const empty = await screen.findByTestId("af-mcp-empty");
    expect(empty.textContent).toMatch(/MCP 目录|MCP Catalog/);
  });

  it("available empty state points to the MCP Servers page", async () => {
    availableMock.mockResolvedValue([]);
    render(
      <McpToolPicker
        servers={[]}
        allowTools={[]}
        onServersChange={noop}
        onAllowToolsChange={noop}
      />,
    );
    const empty = await screen.findByTestId("af-mcp-empty");
    expect(empty.textContent).toMatch(/MCP 服务器|MCP Servers/);
  });

  it("checking a server emits onServersChange", async () => {
    const user = userEvent.setup();
    const onServers = vi.fn();
    availableMock.mockResolvedValue([
      { name: "amap-maps", source: "platform" },
    ]);
    render(
      <McpToolPicker
        servers={[]}
        allowTools={[]}
        onServersChange={onServers}
        onAllowToolsChange={noop}
      />,
    );
    await user.click(await screen.findByTestId("af-mcp-server-amap-maps"));
    await waitFor(() => expect(onServers).toHaveBeenCalledWith(["amap-maps"]));
  });
});
