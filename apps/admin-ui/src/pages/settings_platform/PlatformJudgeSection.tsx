/**
 * Platform Judge-model config section (Stream PI-3-A3).
 *
 * Self-contained section: GETs the platform judge-config on mount, shows the
 * current judge model (or an info note that agents use their own model), and a
 * form to set / clear it. Many operators don't know what a "judge model" is, so
 * the section leads with a friendly explanation. system_admin-only at the route
 * level; surfaces backend error codes.
 */
import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";
import { Alert, App, Button, Select, Space, Spin, Typography } from "antd";
import { useTranslation } from "react-i18next";

import {
  getPlatformJudgeConfig,
  putPlatformJudgeConfig,
  type PlatformJudgeConfigView,
  type ProviderModel,
} from "../../api/platform_judge_config";
import { ApiError } from "../../api/client";

const { Text, Paragraph } = Typography;

export interface PlatformJudgeSectionProps {
  /** Invoked after a successful save (so a parent page can refresh/notify). */
  onSaved?: () => void;
}

function distinctProviders(models: readonly ProviderModel[]): string[] {
  return [...new Set(models.map((m) => m.provider))];
}

function modelsFor(models: readonly ProviderModel[], provider: string | null): string[] {
  if (provider === null) {
    return [];
  }
  return models.filter((m) => m.provider === provider).map((m) => m.model);
}

export function PlatformJudgeSection({ onSaved }: PlatformJudgeSectionProps): ReactElement {
  const { t } = useTranslation();
  const { message } = App.useApp();

  const [view, setView] = useState<PlatformJudgeConfigView | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [provider, setProvider] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const applyView = useCallback((next: PlatformJudgeConfigView) => {
    setView(next);
    setProvider(next.judge?.provider ?? null);
    setModel(next.judge?.model ?? null);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      applyView(await getPlatformJudgeConfig());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setLoading(false);
    }
  }, [applyView]);

  useEffect(() => {
    void load();
  }, [load]);

  const providers = useMemo(() => distinctProviders(view?.available ?? []), [view]);
  const models = useMemo(() => modelsFor(view?.available ?? [], provider), [view, provider]);

  const errMessage = useCallback(
    (err: ApiError): string => {
      const key = `settings_platform.judge_err_${err.code}`;
      const translated = t(key);
      return translated === key ? err.message : translated;
    },
    [t],
  );

  const save = useCallback(
    async (body: { judge_provider: string | null; judge_model: string | null }) => {
      setSaving(true);
      setSaveError(null);
      try {
        const result = await putPlatformJudgeConfig(body);
        applyView({ judge: result.judge, available: view?.available ?? [] });
        message.success(t("settings_platform.judge_saved"));
        onSaved?.();
      } catch (err) {
        setSaveError(err instanceof ApiError ? errMessage(err) : t("settings_platform.judge_save"));
      } finally {
        setSaving(false);
      }
    },
    [applyView, view, message, t, onSaved, errMessage],
  );

  const onSave = useCallback(
    () => save({ judge_provider: provider, judge_model: model }),
    [save, provider, model],
  );
  const onClear = useCallback(
    () => save({ judge_provider: null, judge_model: null }),
    [save],
  );

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }} data-testid="pj-loading">
        <Spin />
      </div>
    );
  }

  if (loadError !== null || view === null) {
    return (
      <Alert
        type="error"
        showIcon
        message={t("settings_platform.judge_current")}
        description={loadError ?? "unknown error"}
        data-testid="pj-load-error"
      />
    );
  }

  return (
    <div data-testid="pj-root">
      {/* Friendly explanation — most operators don't know what a judge is. */}
      <Alert
        type="info"
        showIcon
        message={t("settings_platform.judge_help_title")}
        description={t("settings_platform.judge_help_body")}
        style={{ marginBottom: 16 }}
        data-testid="pj-help"
      />

      <h2 style={{ fontSize: 15, margin: "8px 0" }}>{t("settings_platform.judge_current")}</h2>
      {view.judge === null ? (
        <Paragraph type="secondary" data-testid="pj-unconfigured">
          {t("settings_platform.judge_unconfigured")}
        </Paragraph>
      ) : (
        <Text style={{ display: "block", marginBottom: 16 }}>
          {view.judge.provider} / {view.judge.model}
        </Text>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 480 }}>
        <label>
          <div style={{ marginBottom: 4 }}>{t("settings_platform.judge_provider_label")}</div>
          <div data-testid="pj-provider">
            <Select
              style={{ width: "100%" }}
              value={provider ?? undefined}
              onChange={(value: string) => {
                setProvider(value);
                setModel(null);
              }}
              options={providers.map((p) => ({ label: p, value: p }))}
              aria-label={t("settings_platform.judge_provider_label")}
            />
          </div>
        </label>

        <label>
          <div style={{ marginBottom: 4 }}>{t("settings_platform.judge_model_label")}</div>
          <div data-testid="pj-model">
            <Select
              style={{ width: "100%" }}
              value={model ?? undefined}
              disabled={provider === null}
              onChange={(value: string) => setModel(value)}
              options={models.map((m) => ({ label: m, value: m }))}
              aria-label={t("settings_platform.judge_model_label")}
            />
          </div>
        </label>

        {saveError !== null && (
          <Alert type="error" showIcon message={saveError} data-testid="pj-error" />
        )}

        <Space>
          <Button
            type="primary"
            loading={saving}
            disabled={!provider || !model || saving}
            onClick={onSave}
            data-testid="pj-save"
          >
            {t("settings_platform.judge_save")}
          </Button>
          <Button
            disabled={view.judge === null || saving}
            onClick={onClear}
            data-testid="pj-clear"
          >
            {t("settings_platform.judge_clear")}
          </Button>
        </Space>
      </div>
    </div>
  );
}
