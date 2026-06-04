/**
 * Settings — Billing Chargeback page (Stream Z3, system_admin only).
 *
 * The ONE place the full cost split (base / markup / billed / margin) is
 * shown — a platform-admin cross-tenant view. Mirrors ``SettingsMcpCatalog``
 * gating: non-admins see a notice (testid ``chargeback-not-admin``) and the
 * fetch only runs when ``isSystemAdmin``.
 *
 * The tenant-facing usage page (``SettingsUsage``) deliberately never carries
 * base/markup/margin — that separation is the monetization no-leak rule.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  DatePicker,
  Input,
  Skeleton,
  Statistic,
  Table,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { Receipt } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { useAuth } from "../auth/AuthContext";
import {
  getChargeback,
  type Chargeback,
  type ChargebackTenantRow,
} from "../api/billing-admin";
import { formatMicros } from "../utils/money";

const { Text } = Typography;

const MONTH_FMT = "YYYY-MM";

function errText(err: unknown): string {
  return err instanceof ApiError
    ? `${err.code}: ${err.message}`
    : err instanceof Error
      ? err.message
      : "unknown error";
}

export function SettingsBillingChargeback() {
  const { t } = useTranslation();
  const auth = useAuth();
  const isSystemAdmin = auth.identity?.isSystemAdmin ?? false;

  const [month, setMonth] = useState<Dayjs>(() => dayjs());
  const [tenantFilter, setTenantFilter] = useState("");
  const [data, setData] = useState<Chargeback | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch the whole month's chargeback (all tenants); the ``tenantFilter`` is
  // applied client-side below. This avoids one API call per keystroke (a UUID
  // typed char-by-char would otherwise fire many requests, most with an invalid
  // partial UUID → backend 422).
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getChargeback({ month: month.format(MONTH_FMT) }));
    } catch (err) {
      setError(errText(err));
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    if (isSystemAdmin) {
      void refresh();
    }
  }, [isSystemAdmin, refresh]);

  // Client-side tenant filter (substring on tenant_id) — no refetch per keystroke.
  const filteredTenants = useMemo(() => {
    const needle = tenantFilter.trim().toLowerCase();
    const rows = data?.tenants ?? [];
    if (needle.length === 0) {
      return rows;
    }
    return rows.filter((r) => r.tenant_id.toLowerCase().includes(needle));
  }, [data, tenantFilter]);

  const moneyCol = useCallback(
    (v: number) => (
      <Text style={{ fontFamily: "var(--hx-font-mono)" }}>{formatMicros(v)}</Text>
    ),
    [],
  );

  const columns: TableColumnsType<ChargebackTenantRow> = useMemo(
    () => [
      {
        title: t("chargeback.col_tenant"),
        dataIndex: "tenant_id",
        key: "tenant_id",
        render: (id: string) => (
          <Text code style={{ fontSize: 12 }}>
            {id}
          </Text>
        ),
      },
      {
        title: t("chargeback.col_input_tokens"),
        dataIndex: "input_tokens",
        key: "input_tokens",
        width: 130,
        align: "right",
        render: (v: number) => v.toLocaleString(),
      },
      {
        title: t("chargeback.col_output_tokens"),
        dataIndex: "output_tokens",
        key: "output_tokens",
        width: 130,
        align: "right",
        render: (v: number) => v.toLocaleString(),
      },
      {
        title: t("chargeback.col_base"),
        dataIndex: "base_cost_micros",
        key: "base_cost_micros",
        width: 130,
        align: "right",
        render: moneyCol,
      },
      {
        title: t("chargeback.col_markup"),
        dataIndex: "markup_cost_micros",
        key: "markup_cost_micros",
        width: 130,
        align: "right",
        render: moneyCol,
      },
      {
        title: t("chargeback.col_billed"),
        dataIndex: "billed_cost_micros",
        key: "billed_cost_micros",
        width: 130,
        align: "right",
        render: moneyCol,
      },
      {
        title: t("chargeback.col_margin"),
        dataIndex: "margin_micros",
        key: "margin_micros",
        width: 130,
        align: "right",
        render: moneyCol,
      },
      {
        title: t("chargeback.col_unpriced"),
        dataIndex: "unpriced_buckets",
        key: "unpriced_buckets",
        width: 110,
        align: "right",
        render: (v: number) => v.toLocaleString(),
      },
    ],
    [t, moneyCol],
  );

  return (
    <div data-testid="chargeback-root">
      <PageHeader
        icon={<Receipt size={18} strokeWidth={1.5} />}
        title={t("chargeback.page_title")}
        subtitle={t("chargeback.subtitle")}
        actions={
          isSystemAdmin && (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Input
                placeholder={t("chargeback.tenant_filter")}
                value={tenantFilter}
                onChange={(e) => setTenantFilter(e.target.value)}
                allowClear
                style={{ width: 280 }}
                data-testid="chargeback-tenant-filter"
              />
              <DatePicker
                picker="month"
                value={month}
                allowClear={false}
                onChange={(value) => value && setMonth(value)}
                data-testid="chargeback-month"
              />
            </div>
          )
        }
      />

      {!isSystemAdmin ? (
        <Alert
          type="warning"
          showIcon
          message={t("chargeback.not_admin_title")}
          description={t("chargeback.not_admin_body")}
          data-testid="chargeback-not-admin"
        />
      ) : (
        <>
          {error !== null && (
            <Alert
              type="error"
              showIcon
              message={t("chargeback.failed_to_load")}
              description={error}
              style={{ marginBottom: 12 }}
              data-testid="chargeback-error"
            />
          )}

          {loading && data === null ? (
            <Skeleton active paragraph={{ rows: 6 }} />
          ) : (
            <>
              <div
                style={{
                  display: "flex",
                  gap: 24,
                  flexWrap: "wrap",
                  padding: 16,
                  marginBottom: 16,
                  background: "var(--hx-surface-raised)",
                  border: "1px solid var(--hx-border-subtle)",
                  borderRadius: 6,
                }}
                data-testid="chargeback-summary"
              >
                <Statistic
                  title={t("chargeback.total_base")}
                  value={formatMicros(data?.total_base_cost_micros ?? 0)}
                  valueStyle={{ fontFamily: "var(--hx-font-mono)" }}
                />
                <Statistic
                  title={t("chargeback.total_billed")}
                  value={formatMicros(data?.total_billed_cost_micros ?? 0)}
                  valueStyle={{ fontFamily: "var(--hx-font-mono)" }}
                />
                <Statistic
                  title={t("chargeback.total_margin")}
                  value={formatMicros(data?.total_margin_micros ?? 0)}
                  valueStyle={{ fontFamily: "var(--hx-font-mono)" }}
                />
                {data?.as_of != null && (
                  <Statistic
                    title={t("chargeback.as_of")}
                    value={new Date(data.as_of).toLocaleString()}
                    valueStyle={{ fontSize: 14 }}
                  />
                )}
              </div>

              <Table<ChargebackTenantRow>
                columns={columns}
                dataSource={filteredTenants}
                rowKey={(r) => r.tenant_id}
                loading={loading}
                pagination={false}
                locale={{ emptyText: t("chargeback.empty") }}
                scroll={{ x: "max-content" }}
                data-testid="chargeback-table"
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
