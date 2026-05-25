/**
 * TenantSwitcher — Stream H.1b (Stream N integration) + PR 2a (i18n).
 *
 * Topbar dropdown that drives :class:`TenantScopeContext`:
 *
 *   - tenant_admin: only their home tenant is shown (the switcher is
 *     effectively a read-only label; we still render the dropdown for
 *     visual consistency with system_admin).
 *   - system_admin: home tenant + "All tenants" (PR 2b of H.1b wires a
 *     server-side tenant list for "Switch to specific tenant…").
 *
 * The control-plane enforces this server-side via ``ensure_tenant_scope``
 * — selecting "All tenants" merely puts ``"*"`` on the wire; an
 * impersonated tenant_admin still gets 403 ``CROSS_TENANT_FORBIDDEN``.
 */
import { Select, Tag } from "antd";
import { Globe2, Building2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAuth } from "../auth/AuthContext";
import {
  SCOPE_ALL,
  SCOPE_HOME,
  useTenantScope,
  type TenantScopeValue,
} from "../tenant/TenantScopeContext";

interface ScopeOption {
  value: TenantScopeValue;
  label: string;
  hint?: string;
}

export function TenantSwitcher() {
  const { t } = useTranslation();
  const { identity } = useAuth();
  const { scope, setScope } = useTenantScope();

  const isSystemAdmin = identity?.isSystemAdmin ?? false;
  const homeLabel = identity?.homeTenantId
    ? `${t("tenant.home_label_prefix")} · ${identity.homeTenantId.slice(0, 8)}…`
    : t("tenant.home_tenant");

  const options: ScopeOption[] = [
    {
      value: SCOPE_HOME,
      label: homeLabel,
      hint: t("tenant.your_tenant"),
    },
  ];
  if (isSystemAdmin) {
    options.push({
      value: SCOPE_ALL,
      label: t("tenant.all_tenants"),
      hint: t("tenant.system_admin_hint"),
    });
  }

  return (
    <Select<TenantScopeValue>
      data-testid="tenant-switcher"
      aria-label={t("tenant.home_tenant")}
      value={scope}
      onChange={setScope}
      style={{ minWidth: 220 }}
      size="middle"
      labelInValue={false}
      optionLabelProp="label"
      disabled={options.length === 1}
      options={options.map((o) => ({
        value: o.value,
        label: (
          <span
            data-testid={`tenant-switcher-option-${o.value}`}
            style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
          >
            {o.value === SCOPE_ALL ? <Globe2 size={14} /> : <Building2 size={14} />}
            <span>{o.label}</span>
            {o.value === SCOPE_ALL && (
              <Tag color="purple" style={{ marginLeft: 4 }}>
                {t("tenant.cross_tag")}
              </Tag>
            )}
            {o.hint && (
              <span style={{ color: "var(--hx-text-tertiary)", fontSize: 11 }}>
                {o.hint}
              </span>
            )}
          </span>
        ),
      }))}
    />
  );
}
