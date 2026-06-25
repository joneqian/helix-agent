/**
 * Platform Agent template detail/edit page — Stream Agent-Templates (M1-6).
 *
 * Route ``/settings/agent-templates/:name/:version``. system_admin edits a
 * template's marketplace metadata + base manifest via the shared
 * ``AgentTemplateConfigForm``; the page owns the Save button (drives the form's
 * imperative ``submit()``). Mirrors ``McpCatalogDetail``.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Alert, App, Button, Spin } from "antd";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";
import { useAuth } from "../auth/AuthContext";
import { getAgentTemplate, type AgentTemplate } from "../api/agent-templates";
import {
  AgentTemplateConfigForm,
  type AgentTemplateConfigFormHandle,
} from "../components/agent_templates/AgentTemplateConfigForm";

export function AgentTemplateDetail() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const { name = "", version = "" } = useParams<{ name: string; version: string }>();
  const navigate = useNavigate();
  const auth = useAuth();
  const isSystemAdmin = auth.identity?.isSystemAdmin ?? false;

  const formRef = useRef<AgentTemplateConfigFormHandle>(null);
  const [entry, setEntry] = useState<AgentTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEntry(await getAgentTemplate(name, version));
    } catch (err) {
      setError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setLoading(false);
    }
  }, [name, version]);

  useEffect(() => {
    if (isSystemAdmin) void load();
  }, [isSystemAdmin, load]);

  if (!isSystemAdmin) {
    return (
      <Alert
        type="warning"
        showIcon
        message={t("agent_templates.not_admin_title")}
        description={t("agent_templates.not_admin_body")}
        data-testid="atd-not-admin"
      />
    );
  }

  return (
    <div data-testid="atd-root">
      <PageHeader
        title={entry ? entry.display_name : `${name}@${version}`}
        subtitle={`${name}@${version}`}
        backTo={{ label: t("agent_templates.page_title"), to: "/settings/agent-templates" }}
        actions={
          entry && (
            <Button
              type="primary"
              loading={saving}
              onClick={() => void formRef.current?.submit()}
              data-testid="atd-save"
            >
              {t("common.save")}
            </Button>
          )
        }
      />
      {error !== null && (
        <Alert
          type="error"
          showIcon
          message={t("agent_templates.failed_to_load")}
          description={error}
          style={{ marginBottom: 12 }}
          data-testid="atd-error"
        />
      )}
      {loading ? (
        <Spin />
      ) : entry ? (
        <AgentTemplateConfigForm
          ref={formRef}
          editing={entry}
          onSubmittingChange={setSaving}
          onSaved={(saved) => {
            setEntry(saved);
            message.success(t("agent_templates.saved_ok"));
            void load();
          }}
        />
      ) : (
        <Button onClick={() => navigate("/settings/agent-templates")}>{t("agent_templates.back")}</Button>
      )}
    </div>
  );
}
