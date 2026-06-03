/**
 * McpToolPicker — controlled component for selecting MCP servers + tools in
 * the agent form (Stream V-G).
 *
 * Props (controlled):
 *   servers      — selected server names (MCPToolSpec.servers)
 *   allowTools   — selected tool names (MCPToolSpec.allow_tools, flat list)
 *   onServersChange    — called when the server selection changes
 *   onAllowToolsChange — called when the tool selection changes
 *
 * Behavior:
 *   - On mount calls listAvailableMcpServers() → shows loading → list, error,
 *     or empty state.
 *   - Each available server is a Checkbox (testid af-mcp-server-{name}),
 *     checked when name ∈ servers.  A source Tag (platform/tenant) is shown.
 *   - Checking/unchecking a server updates onServersChange(next).
 *   - Each CHECKED server is expandable (antd Collapse, testid
 *     af-mcp-tools-{name}): on first expand calls listMcpServerTools(name).
 *   - Tool checkboxes inside the expanded section (testid af-mcp-tool-{name}).
 *   - allow_tools is a flat list of bare tool names across servers.  Checking
 *     a tool adds its bare name; unchecking removes it.
 *   - Tools cached per server in component state after first fetch.
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Checkbox, Collapse, Space, Spin, Tag, Tooltip, Typography } from "antd";
import { useTranslation } from "react-i18next";

import {
  listAvailableMcpServers,
  listMcpServerTools,
  type AvailableMcpServer,
  type McpTool,
} from "../../../api/mcp-servers";

// ── Types ──────────────────────────────────────────────────────────────────

interface McpToolPickerProps {
  servers: string[];
  allowTools: string[];
  onServersChange: (next: string[]) => void;
  onAllowToolsChange: (next: string[]) => void;
}

type ServerLoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; tools: McpTool[] }
  | { kind: "error" };

// ── Component ──────────────────────────────────────────────────────────────

export function McpToolPicker({
  servers,
  allowTools,
  onServersChange,
  onAllowToolsChange,
}: McpToolPickerProps) {
  const { t } = useTranslation();

  // Available servers from /v1/mcp-servers/available
  const [available, setAvailable] = useState<AvailableMcpServer[]>([]);
  const [serversLoading, setServersLoading] = useState(true);
  const [serversError, setServersError] = useState<string | null>(null);

  // Per-server tool fetch state; keyed by server name
  const [toolStates, setToolStates] = useState<Record<string, ServerLoadState>>({});

  // ── Load available servers on mount ─────────────────────────────────────

  useEffect(() => {
    setServersLoading(true);
    listAvailableMcpServers().then(
      (data) => {
        setAvailable(data);
        setServersLoading(false);
      },
      (err: unknown) => {
        setServersError(err instanceof Error ? err.message : "unknown error");
        setServersLoading(false);
      },
    );
  }, []);

  // ── Fetch tools for a server on first expand ─────────────────────────────

  const fetchTools = useCallback(
    (name: string) => {
      const current = toolStates[name];
      // Already loaded or in flight — skip.
      if (current?.kind === "loaded" || current?.kind === "loading") {
        return;
      }
      setToolStates((prev) => ({ ...prev, [name]: { kind: "loading" } }));
      listMcpServerTools(name).then(
        (tools) => {
          setToolStates((prev) => ({ ...prev, [name]: { kind: "loaded", tools } }));
        },
        () => {
          setToolStates((prev) => ({ ...prev, [name]: { kind: "error" } }));
        },
      );
    },
    [toolStates],
  );

  // ── Server checkbox handler ───────────────────────────────────────────────

  const handleServerToggle = useCallback(
    (name: string, checked: boolean) => {
      if (checked) {
        onServersChange([...servers, name]);
      } else {
        onServersChange(servers.filter((s) => s !== name));
      }
    },
    [servers, onServersChange],
  );

  // ── Tool checkbox handler ─────────────────────────────────────────────────

  const handleToolToggle = useCallback(
    (toolName: string, checked: boolean) => {
      if (checked) {
        onAllowToolsChange([...allowTools, toolName]);
      } else {
        onAllowToolsChange(allowTools.filter((t) => t !== toolName));
      }
    },
    [allowTools, onAllowToolsChange],
  );

  // ── Loading state ────────────────────────────────────────────────────────

  if (serversLoading) {
    return (
      <div style={{ padding: "8px 0" }}>
        <Space size={4}>
          <Spin size="small" />
          <span>{t("agent_form.mcp_servers_loading")}</span>
        </Space>
      </div>
    );
  }

  // ── Error state ──────────────────────────────────────────────────────────

  if (serversError !== null) {
    return (
      <Alert
        type="error"
        showIcon
        message={t("agent_form.mcp_servers_load_failed")}
        description={serversError}
        style={{ marginBottom: 8 }}
      />
    );
  }

  // ── Empty state ──────────────────────────────────────────────────────────

  if (available.length === 0) {
    return (
      <div
        style={{
          color: "var(--hx-text-tertiary, #666)",
          fontSize: 13,
          padding: "4px 0",
        }}
      >
        {t("agent_form.mcp_no_servers")}
      </div>
    );
  }

  // ── Render ───────────────────────────────────────────────────────────────

  const checkedServers = new Set(servers);

  return (
    <div>
      {/* Servers section */}
      <div style={{ marginBottom: 6 }}>
        <Typography.Text strong style={{ display: "block", marginBottom: 2 }}>
          {t("agent_form.mcp_servers_label")}
        </Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
          {t("agent_form.mcp_servers_hint")}
        </Typography.Text>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {available.map((server) => {
            const isChecked = checkedServers.has(server.name);
            return (
              <div key={server.name}>
                {/* Server checkbox row */}
                <Space size={6} align="center">
                  <Checkbox
                    data-testid={`af-mcp-server-${server.name}`}
                    checked={isChecked}
                    onChange={(e) => handleServerToggle(server.name, e.target.checked)}
                  >
                    <span style={{ fontWeight: 500 }}>{server.name}</span>
                  </Checkbox>
                  <Tag
                    color={server.source === "platform" ? "blue" : "green"}
                    style={{ fontSize: 11 }}
                  >
                    {server.source === "platform"
                      ? t("agent_form.mcp_source_platform")
                      : t("agent_form.mcp_source_tenant")}
                  </Tag>
                </Space>

                {/* Tools section — only shown when server is checked */}
                {isChecked && (
                  <div style={{ marginLeft: 24, marginTop: 4 }}>
                    <Collapse
                      size="small"
                      data-testid={`af-mcp-tools-${server.name}`}
                      onChange={(keys) => {
                        if (keys.length > 0) {
                          fetchTools(server.name);
                        }
                      }}
                      items={[
                        {
                          key: "tools",
                          label: (
                            <Typography.Text style={{ fontSize: 12 }}>
                              {t("agent_form.mcp_tools_label")}
                            </Typography.Text>
                          ),
                          children: renderToolsPanel(server.name),
                        },
                      ]}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );

  // ── Inner renderer for the tools Collapse panel ──────────────────────────

  function renderToolsPanel(serverName: string) {
    const state = toolStates[serverName] ?? { kind: "idle" };

    if (state.kind === "idle" || state.kind === "loading") {
      return (
        <Space size={4}>
          <Spin size="small" />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {t("agent_form.mcp_tools_loading")}
          </Typography.Text>
        </Space>
      );
    }

    if (state.kind === "error") {
      return (
        <Alert
          type="warning"
          showIcon
          message={t("agent_form.mcp_tools_unreachable")}
          style={{ fontSize: 12 }}
        />
      );
    }

    // state.kind === "loaded"
    const tools = state.tools;

    return (
      <div>
        <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 6 }}>
          {t("agent_form.mcp_tools_hint")}
        </Typography.Text>
        {tools.length === 0 ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            —
          </Typography.Text>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {tools.map((tool) => (
              <Tooltip
                key={tool.name}
                title={tool.description || undefined}
                placement="right"
              >
                <Checkbox
                  data-testid={`af-mcp-tool-${tool.name}`}
                  checked={allowTools.includes(tool.name)}
                  onChange={(e) => handleToolToggle(tool.name, e.target.checked)}
                >
                  <Typography.Text style={{ fontSize: 13 }}>{tool.name}</Typography.Text>
                </Checkbox>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
    );
  }
}
