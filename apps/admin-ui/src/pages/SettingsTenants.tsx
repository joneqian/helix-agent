/**
 * Settings — Tenants page (Stream U, PR D).
 *
 * Lists every tenant on the platform (``GET /v1/tenants``). Platform-level
 * read — only system_admins see the table (mirrors the backend gate). Each
 * row's "Manage" action switches the current tenant scope into that tenant
 * (persisted by :func:`TenantScopeProvider`) and jumps to its per-tenant
 * config page, where config / quotas / credentials are edited.
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Breadcrumb, Button, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Building, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { listTenants, type TenantSummary } from "../api/tenants";
import { useAuth } from "../auth/AuthContext";
import { useTenantScope } from "../tenant/TenantScopeContext";

export function SettingsTenants() {
  const { t } = useTranslation();
  const auth = useAuth();
  const isSystemAdmin = auth.identity?.isSystemAdmin ?? false;
  const { setScope } = useTenantScope();
  const navigate = useNavigate();

  const [rows, setRows] = useState<TenantSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isSystemAdmin) {
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    listTenants()
      .then((data) => {
        if (!alive) return;
        setRows(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "unknown error");
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [isSystemAdmin]);

  const manage = useCallback(
    (id: string) => {
      setScope(id);
      navigate("/settings/tenant-config");
    },
    [setScope, navigate],
  );

  const columns: ColumnsType<TenantSummary> = [
    { title: t("settings_tenants.col_display_name"), dataIndex: "display_name", key: "display_name" },
    { title: t("settings_tenants.col_plan"), dataIndex: "plan", key: "plan" },
    {
      title: t("settings_tenants.col_tenant_id"),
      dataIndex: "tenant_id",
      key: "tenant_id",
      render: (id: string) => (
        <Typography.Text code copyable>
          {id}
        </Typography.Text>
      ),
    },
    {
      title: t("settings_tenants.col_created"),
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: t("settings_tenants.col_actions"),
      key: "actions",
      render: (_: unknown, r: TenantSummary) => (
        <Button
          size="small"
          data-testid={`st-manage-${r.tenant_id}`}
          onClick={() => manage(r.tenant_id)}
        >
          {t("settings_tenants.manage")}
        </Button>
      ),
    },
  ];

  return (
    <div data-testid="st-root">
      <div className="hx-page-header">
        <Breadcrumb
          separator={<ChevronRight size={12} strokeWidth={1.5} />}
          items={[{ title: t("common.home") }, { title: t("settings_tenants.page_title") }]}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, marginBottom: 16 }}>
          <Building size={20} strokeWidth={1.5} />
          <h1 style={{ margin: 0 }}>{t("settings_tenants.page_title")}</h1>
        </div>
        <p style={{ color: "var(--hx-text-secondary)", fontSize: 13, margin: "0 0 12px" }}>
          {t("settings_tenants.subtitle")}
        </p>
      </div>

      {!isSystemAdmin ? (
        <Alert
          type="warning"
          showIcon
          message={t("settings_tenants.not_admin_title")}
          description={t("settings_tenants.not_admin_body")}
          data-testid="st-not-admin"
        />
      ) : (
        <>
          {error !== null && (
            <Alert
              type="error"
              showIcon
              data-testid="st-error"
              message={t("settings_tenants.failed_to_load")}
              description={error}
              style={{ marginBottom: 16 }}
            />
          )}
          <Table<TenantSummary>
            data-testid="st-table"
            rowKey="tenant_id"
            loading={loading}
            dataSource={rows}
            pagination={false}
            locale={{ emptyText: t("settings_tenants.empty") }}
            columns={columns}
          />
        </>
      )}
    </div>
  );
}
