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
 *   - On mount lists selectable servers per ``source`` (``available`` = the
 *     tenant's opted-in/custom servers; ``catalog`` = published platform
 *     connectors, for a platform template) → loading → list, error, or empty.
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
import {
  Alert,
  Checkbox,
  Collapse,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { useTranslation } from "react-i18next";

import {
  listAvailableMcpServers,
  listMcpServerTools,
  type McpTool,
} from "../../../api/mcp-servers";
import {
  listPlatformCatalog,
  listCatalogTools,
} from "../../../api/mcp-catalog";

// ── Types ──────────────────────────────────────────────────────────────────

/** Where the picker sources selectable servers from:
 *   - ``available`` (default): the tenant's opted-in + custom servers
 *     (``/v1/mcp-servers/available``). For a tenant agent that runs now.
 *   - ``catalog``: published platform connectors (``/v1/platform/mcp-catalog``,
 *     ``enabled`` only). For a platform Agent template — a blueprint that
 *     references connectors by name, so it lists the catalog directly instead
 *     of requiring a per-tenant opt-in that doesn't apply to a template. */
export type McpPickerSource = "available" | "catalog";

interface McpToolPickerProps {
  servers: string[];
  allowTools: string[];
  onServersChange: (next: string[]) => void;
  onAllowToolsChange: (next: string[]) => void;
  source?: McpPickerSource;
}

/** Normalised row shown in the list, regardless of source. ``toolKey`` is the
 * argument the tool-list endpoint needs (server name for ``available``, catalog
 * id for ``catalog``). */
interface ServerRow {
  name: string;
  label: string;
  tagText: string;
  tagColor: string;
  toolKey: string;
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
  source = "available",
}: McpToolPickerProps) {
  const { t } = useTranslation();

  const [rows, setRows] = useState<ServerRow[]>([]);
  const [serversLoading, setServersLoading] = useState(true);
  const [serversError, setServersError] = useState<string | null>(null);

  // Per-server tool fetch state; keyed by server name
  const [toolStates, setToolStates] = useState<Record<string, ServerLoadState>>(
    {},
  );

  // ── Load selectable servers on mount (source-dependent) ──────────────────

  useEffect(() => {
    let alive = true;
    setServersLoading(true);
    const load: Promise<ServerRow[]> =
      source === "catalog"
        ? listPlatformCatalog().then((entries) =>
            entries
              .filter((e) => e.enabled)
              .map((e) => ({
                name: e.name,
                label: e.display_name || e.name,
                tagText: t("agent_form.mcp_source_platform"),
                tagColor: "blue",
                toolKey: e.id,
              })),
          )
        : listAvailableMcpServers().then((data) =>
            data.map((s) => ({
              name: s.name,
              label: s.name,
              tagText:
                s.source === "platform"
                  ? t("agent_form.mcp_source_platform")
                  : t("agent_form.mcp_source_tenant"),
              tagColor: s.source === "platform" ? "blue" : "green",
              toolKey: s.name,
            })),
          );
    load.then(
      (data) => {
        if (!alive) return;
        setRows(data);
        setServersLoading(false);
      },
      (err: unknown) => {
        if (!alive) return;
        setServersError(err instanceof Error ? err.message : "unknown error");
        setServersLoading(false);
      },
    );
    return () => {
      alive = false;
    };
  }, [source, t]);

  // ── Fetch tools for a server on first expand ─────────────────────────────

  const fetchTools = useCallback(
    (row: ServerRow) => {
      const current = toolStates[row.name];
      // Already loaded or in flight — skip.
      if (current?.kind === "loaded" || current?.kind === "loading") {
        return;
      }
      setToolStates((prev) => ({ ...prev, [row.name]: { kind: "loading" } }));
      const fetch: Promise<McpTool[]> =
        source === "catalog"
          ? listCatalogTools(row.toolKey).then((res) =>
              res.status === "ok"
                ? res.tools
                    .filter((tool) => !tool.disabled)
                    .map((tool) => ({
                      name: tool.name,
                      description: tool.description,
                    }))
                : Promise.reject(new Error(res.error ?? "unreachable")),
            )
          : listMcpServerTools(row.toolKey);
      fetch.then(
        (tools) => {
          setToolStates((prev) => ({
            ...prev,
            [row.name]: { kind: "loaded", tools },
          }));
        },
        () => {
          setToolStates((prev) => ({ ...prev, [row.name]: { kind: "error" } }));
        },
      );
    },
    [toolStates, source],
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

  if (rows.length === 0) {
    return (
      <div
        data-testid="af-mcp-empty"
        style={{
          color: "var(--hx-text-tertiary, #666)",
          fontSize: 13,
          padding: "4px 0",
        }}
      >
        {source === "catalog"
          ? t("agent_form.mcp_no_servers_catalog")
          : t("agent_form.mcp_no_servers_available")}
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
        <Typography.Text
          type="secondary"
          style={{ fontSize: 12, display: "block", marginBottom: 8 }}
        >
          {t("agent_form.mcp_servers_hint")}
        </Typography.Text>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {rows.map((server) => {
            const isChecked = checkedServers.has(server.name);
            return (
              <div key={server.name}>
                {/* Server checkbox row */}
                <Space size={6} align="center">
                  <Checkbox
                    data-testid={`af-mcp-server-${server.name}`}
                    checked={isChecked}
                    onChange={(e) =>
                      handleServerToggle(server.name, e.target.checked)
                    }
                  >
                    <span style={{ fontWeight: 500 }}>{server.label}</span>
                  </Checkbox>
                  <Tag color={server.tagColor} style={{ fontSize: 11 }}>
                    {server.tagText}
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
                          fetchTools(server);
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
        <Typography.Text
          type="secondary"
          style={{ fontSize: 11, display: "block", marginBottom: 6 }}
        >
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
                  onChange={(e) =>
                    handleToolToggle(tool.name, e.target.checked)
                  }
                >
                  <Typography.Text style={{ fontSize: 13 }}>
                    {tool.name}
                  </Typography.Text>
                </Checkbox>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
    );
  }
}
