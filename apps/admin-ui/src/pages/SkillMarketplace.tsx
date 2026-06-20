/**
 * Skill Marketplace — Skill Marketplace Phase 3 (tenant-scoped).
 *
 * A browse-and-subscribe shelf for the platform-curated skill library. Reads
 * the ``platform_items`` slice of the X-6 merged ``GET /v1/skills`` view (each
 * row carries ``entitled`` + ``subscribed``) and renders a card wall mirroring
 * the MCP ``CatalogBrowser`` visual.
 *
 * Subscribing is **semantic A**: an accounting/UX marker that does NOT gate
 * runtime binding (the tier check stays the real gate). An agent can already
 * bind any entitled platform skill via name@version regardless; the
 * marketplace is the explicit "I picked this" surface.
 *
 * Locked rows (``entitled === false``) show a tier lock and can't be
 * subscribed. Cross-tenant scope (``tenant_id=*``) returns no platform items
 * server-side, so the page guides the operator to pick a tenant.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, App, Badge, Button, Card, Empty, Spin, Tag, Typography } from "antd";
import { Check, Lock, Store } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  listSkills,
  subscribeSkill,
  unsubscribeSkill,
  type SkillRecord,
} from "../api/skills";
import { ApiError } from "../api/client";
import { SCOPE_ALL, useTenantScope } from "../tenant/TenantScopeContext";
import { PageHeader } from "../components/PageHeader";

const { Text, Paragraph } = Typography;

type RequiredTier = "free" | "pro" | "enterprise";

const TIER_COLOR: Record<RequiredTier, string> = {
  free: "default",
  pro: "blue",
  enterprise: "gold",
};

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`;
  if (err instanceof Error) return err.message;
  return "unknown error";
}

export function SkillMarketplace() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const { scope, apiTenantScope } = useTenantScope();

  const [items, setItems] = useState<SkillRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Per-card in-flight guard so a row's button disables while its
  // subscribe/unsubscribe request is pending.
  const [busyId, setBusyId] = useState<string | null>(null);

  const crossTenant = scope === SCOPE_ALL;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listSkills({ tenantScope: apiTenantScope });
      setItems(result.platform_items ?? []);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [apiTenantScope]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setSubscribed = useCallback((id: string, subscribed: boolean) => {
    setItems((prev) =>
      prev.map((s) => (s.id === id ? { ...s, subscribed } : s)),
    );
  }, []);

  const onSubscribe = useCallback(
    async (skill: SkillRecord) => {
      setBusyId(skill.id);
      try {
        await subscribeSkill(skill.id);
        setSubscribed(skill.id, true);
        message.success(t("skill_marketplace.subscribed_ok", { name: skill.name }));
      } catch (err) {
        message.error(errorMessage(err));
      } finally {
        setBusyId(null);
      }
    },
    [message, t, setSubscribed],
  );

  const onUnsubscribe = useCallback(
    async (skill: SkillRecord) => {
      setBusyId(skill.id);
      try {
        await unsubscribeSkill(skill.id);
        setSubscribed(skill.id, false);
        message.success(t("skill_marketplace.unsubscribed_ok", { name: skill.name }));
      } catch (err) {
        message.error(errorMessage(err));
      } finally {
        setBusyId(null);
      }
    },
    [message, t, setSubscribed],
  );

  const header = (
    <PageHeader
      title={t("skill_marketplace.page_title")}
      icon={<Store size={20} strokeWidth={1.5} />}
      subtitle={t("skill_marketplace.subtitle")}
    />
  );

  const body = useMemo(() => {
    if (crossTenant) {
      return (
        <Alert
          type="info"
          showIcon
          message={t("skill_marketplace.cross_tenant_title")}
          description={t("skill_marketplace.cross_tenant_hint")}
          data-testid="sm-cross-tenant"
        />
      );
    }
    if (loading) {
      return (
        <div style={{ textAlign: "center", padding: "32px 0" }} data-testid="sm-loading">
          <Spin />
        </div>
      );
    }
    if (error !== null) {
      return (
        <Alert
          type="error"
          showIcon
          message={t("skill_marketplace.failed_to_load")}
          description={error}
          data-testid="sm-error"
        />
      );
    }
    if (items.length === 0) {
      return <Empty description={t("skill_marketplace.empty")} data-testid="sm-empty" />;
    }
    return (
      <div
        data-testid="sm-root"
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        {items.map((skill) => {
          const tier = (skill.required_tier ?? "free") as RequiredTier;
          const locked = skill.entitled === false;
          const subscribed = skill.subscribed === true;
          const busy = busyId === skill.id;
          const card = (
            <Card
              key={skill.id}
              size="small"
              hoverable={!locked}
              data-testid={`sm-card-${skill.name}`}
              style={locked ? { opacity: 0.6 } : undefined}
              styles={{ body: { padding: 14 } }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div style={{ minWidth: 0 }}>
                  <Text strong>{skill.name}</Text>
                  {skill.category && <Tag style={{ marginLeft: 8 }}>{skill.category}</Tag>}
                  <Tag color={TIER_COLOR[tier]} style={{ marginLeft: 4 }}>
                    {t(`skill_marketplace.tier_${tier}`)}
                  </Tag>
                  {skill.description && (
                    <Paragraph
                      type="secondary"
                      style={{ marginTop: 6, marginBottom: 0, fontSize: 12 }}
                      ellipsis={{ rows: 2 }}
                    >
                      {skill.description}
                    </Paragraph>
                  )}
                </div>
                <div style={{ flexShrink: 0, alignSelf: "center" }}>
                  {locked ? (
                    <Button
                      size="small"
                      disabled
                      icon={<Lock size={13} strokeWidth={1.5} />}
                      data-testid={`sm-locked-${skill.name}`}
                    >
                      {t("skill_marketplace.requires_tier", {
                        tier: t(`skill_marketplace.tier_${tier}`),
                      })}
                    </Button>
                  ) : subscribed ? (
                    <Button
                      size="small"
                      loading={busy}
                      icon={<Check size={13} strokeWidth={1.5} />}
                      data-testid={`sm-unsubscribe-${skill.name}`}
                      onClick={() => void onUnsubscribe(skill)}
                    >
                      {t("skill_marketplace.enabled")}
                    </Button>
                  ) : (
                    <Button
                      type="primary"
                      size="small"
                      loading={busy}
                      data-testid={`sm-subscribe-${skill.name}`}
                      onClick={() => void onSubscribe(skill)}
                    >
                      {t("skill_marketplace.enable")}
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          );
          return locked ? (
            <Badge.Ribbon
              key={skill.id}
              text={t("skill_marketplace.locked_ribbon")}
              color="gray"
            >
              {card}
            </Badge.Ribbon>
          ) : (
            card
          );
        })}
      </div>
    );
  }, [crossTenant, loading, error, items, busyId, t, onSubscribe, onUnsubscribe]);

  return (
    <div>
      {header}
      {body}
    </div>
  );
}
