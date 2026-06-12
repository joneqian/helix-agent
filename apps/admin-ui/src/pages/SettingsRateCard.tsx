/**
 * Rate Card page — Stream H.9 PR 1 (design § 6.10).
 *
 * Platform pricing governance over ``/v1/platform/rate-card``
 * (system_admin only; the frontend gate is UX — the real boundary is
 * the backend's ``require("billing",·)`` + ``is_system_admin`` double
 * gate, Mini-ADR H-22).
 *
 * Edit surface mirrors the backend's temporal-identity semantics
 * (Mini-ADR H-20): provider / model / plan_tier / effective_from are
 * immutable post-create — the edit drawer greys them out and the copy
 * points at "insert a new row" for repricing.
 *
 * Prices are raw micro-USD-per-token inputs with a read-only $/1M
 * conversion hint (Mini-ADR H-21) — no implicit unit conversion.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  App,
  Button,
  DatePicker,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { Banknote, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  createRateCard,
  deleteRateCard,
  listRateCards,
  microsPerTokenToUsdPerMillion,
  patchRateCard,
  type PlanTier,
  type RateCardPatch,
  type RateCardRecord,
} from "../api/rate_card";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PageHeader } from "../components/PageHeader";

const { Text } = Typography;

const PLAN_OPTIONS: (PlanTier | "all")[] = ["all", "free", "pro", "enterprise"];

function errMessage(err: unknown): string {
  return err instanceof ApiError
    ? `${err.code}: ${err.message}`
    : err instanceof Error
      ? err.message
      : "unknown error";
}

interface CreateFormValues {
  provider: string;
  model: string;
  input_token_micros: number;
  output_token_micros: number;
  cache_creation_token_micros?: number;
  cache_read_token_micros?: number;
  markup_bps?: number;
  plan_tier?: PlanTier | "all";
  effective_from: Dayjs;
  effective_until?: Dayjs | null;
}

interface EditFormValues {
  input_token_micros: number;
  output_token_micros: number;
  cache_creation_token_micros: number;
  cache_read_token_micros: number;
  markup_bps: number;
  effective_until?: Dayjs | null;
}

/** Micros InputNumber with the H-21 read-only $/1M hint. */
function MicrosField({ name, label }: { name: string; label: string }) {
  return (
    <Form.Item noStyle shouldUpdate>
      {({ getFieldValue }) => {
        const value: number | undefined = getFieldValue(name);
        return (
          <Form.Item
            name={name}
            label={label}
            rules={[{ required: name.startsWith("input") || name.startsWith("output") }]}
            extra={
              typeof value === "number" ? (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  ≈ {microsPerTokenToUsdPerMillion(value)}
                </Text>
              ) : undefined
            }
          >
            <InputNumber min={0} style={{ width: "100%" }} data-testid={`rc-${name}`} />
          </Form.Item>
        );
      }}
    </Form.Item>
  );
}

export function SettingsRateCard() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const auth = useAuth();
  const isSystemAdmin = auth.identity?.isSystemAdmin ?? false;

  const [items, setItems] = useState<RateCardRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [includeExpired, setIncludeExpired] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<RateCardRecord | null>(null);
  const [saving, setSaving] = useState(false);
  const [createForm] = Form.useForm<CreateFormValues>();
  const [editForm] = Form.useForm<EditFormValues>();

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listRateCards({
        provider: providerFilter || undefined,
        model: modelFilter || undefined,
        includeExpired,
      });
      setItems(result);
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setLoading(false);
    }
  }, [providerFilter, modelFilter, includeExpired]);

  useEffect(() => {
    if (isSystemAdmin) {
      void refresh();
    }
  }, [isSystemAdmin, refresh]);

  const handleCreate = useCallback(
    async (values: CreateFormValues) => {
      setCreating(true);
      try {
        await createRateCard({
          provider: values.provider,
          model: values.model,
          input_token_micros: values.input_token_micros,
          output_token_micros: values.output_token_micros,
          cache_creation_token_micros: values.cache_creation_token_micros,
          cache_read_token_micros: values.cache_read_token_micros,
          markup_bps: values.markup_bps,
          plan_tier:
            values.plan_tier === "all" || values.plan_tier === undefined
              ? null
              : values.plan_tier,
          effective_from: values.effective_from.toISOString(),
          effective_until: values.effective_until?.toISOString() ?? null,
        });
        setCreateOpen(false);
        createForm.resetFields();
        await refresh();
      } catch (err) {
        message.error(errMessage(err));
      } finally {
        setCreating(false);
      }
    },
    [createForm, message, refresh],
  );

  const openEdit = useCallback(
    (record: RateCardRecord) => {
      setEditing(record);
      editForm.setFieldsValue({
        input_token_micros: record.input_token_micros,
        output_token_micros: record.output_token_micros,
        cache_creation_token_micros: record.cache_creation_token_micros,
        cache_read_token_micros: record.cache_read_token_micros,
        markup_bps: record.markup_bps,
        effective_until: record.effective_until ? dayjs(record.effective_until) : null,
      });
    },
    [editForm],
  );

  const handleEdit = useCallback(
    async (values: EditFormValues) => {
      if (editing === null) return;
      setSaving(true);
      try {
        const patch: RateCardPatch = {
          input_token_micros: values.input_token_micros,
          output_token_micros: values.output_token_micros,
          cache_creation_token_micros: values.cache_creation_token_micros,
          cache_read_token_micros: values.cache_read_token_micros,
          markup_bps: values.markup_bps,
          effective_until: values.effective_until?.toISOString() ?? null,
        };
        await patchRateCard(editing.id, patch);
        setEditing(null);
        await refresh();
      } catch (err) {
        message.error(errMessage(err));
      } finally {
        setSaving(false);
      }
    },
    [editing, message, refresh],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteRateCard(id);
        await refresh();
      } catch (err) {
        message.error(errMessage(err));
      }
    },
    [message, refresh],
  );

  const columns: TableColumnsType<RateCardRecord> = useMemo(
    () => [
      {
        title: t("rate_card_page.col_provider"),
        dataIndex: "provider",
        key: "provider",
        width: 120,
        render: (provider: string) => <Text strong>{provider}</Text>,
      },
      {
        title: t("rate_card_page.col_model"),
        dataIndex: "model",
        key: "model",
        render: (model: string) => <Text className="mono">{model}</Text>,
      },
      {
        title: t("rate_card_page.col_plan"),
        dataIndex: "plan_tier",
        key: "plan_tier",
        width: 110,
        render: (tier: PlanTier | null) =>
          tier === null ? (
            <Tag bordered={false}>{t("rate_card_page.all_plans")}</Tag>
          ) : (
            <Tag color="blue" bordered={false}>
              {tier}
            </Tag>
          ),
      },
      {
        title: t("rate_card_page.col_input"),
        dataIndex: "input_token_micros",
        key: "input",
        width: 110,
        render: (v: number) => (
          <Tooltip title={microsPerTokenToUsdPerMillion(v)}>
            <Text className="mono">{v}</Text>
          </Tooltip>
        ),
      },
      {
        title: t("rate_card_page.col_output"),
        dataIndex: "output_token_micros",
        key: "output",
        width: 110,
        render: (v: number) => (
          <Tooltip title={microsPerTokenToUsdPerMillion(v)}>
            <Text className="mono">{v}</Text>
          </Tooltip>
        ),
      },
      {
        title: t("rate_card_page.col_markup"),
        dataIndex: "markup_bps",
        key: "markup",
        width: 100,
        render: (bps: number) => <Text className="mono">{bps} bps</Text>,
      },
      {
        title: t("rate_card_page.col_effective"),
        key: "effective",
        width: 230,
        render: (_: unknown, record) => (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {new Date(record.effective_from).toLocaleDateString()} →{" "}
            {record.effective_until
              ? new Date(record.effective_until).toLocaleDateString()
              : t("rate_card_page.open_ended")}
          </Text>
        ),
      },
      {
        title: "",
        key: "actions",
        width: 140,
        render: (_: unknown, record) => (
          <Space size={6}>
            <Button
              size="small"
              onClick={() => openEdit(record)}
              data-testid={`rc-edit-${record.id}`}
            >
              {t("rate_card_page.edit")}
            </Button>
            <Popconfirm
              title={t("rate_card_page.delete_confirm_title")}
              description={t("rate_card_page.delete_confirm_body")}
              onConfirm={() => void handleDelete(record.id)}
              okText={t("rate_card_page.delete")}
              okButtonProps={{ danger: true }}
            >
              <Button
                size="small"
                danger
                type="text"
                icon={<Trash2 size={13} strokeWidth={1.5} />}
                aria-label={t("rate_card_page.delete")}
                data-testid={`rc-delete-${record.id}`}
              />
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [t, openEdit, handleDelete],
  );

  if (!isSystemAdmin) {
    return (
      <div data-testid="rate-card-root">
        <PageHeader
          icon={<Banknote size={18} strokeWidth={1.5} />}
          title={t("rate_card_page.page_title")}
        />
        <Empty
          description={t("rate_card_page.system_admin_only")}
          style={{ marginTop: 64 }}
          data-testid="rate-card-forbidden"
        />
      </div>
    );
  }

  return (
    <div data-testid="rate-card-root">
      <PageHeader
        icon={<Banknote size={18} strokeWidth={1.5} />}
        title={t("rate_card_page.page_title")}
        subtitle={
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t("rate_card_page.subtitle")}
          </Text>
        }
        actions={
          <Space size={10}>
            <Input
              placeholder={t("rate_card_page.filter_provider")}
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              style={{ width: 140 }}
              size="small"
              allowClear
              data-testid="rc-filter-provider"
            />
            <Input
              placeholder={t("rate_card_page.filter_model")}
              value={modelFilter}
              onChange={(e) => setModelFilter(e.target.value)}
              style={{ width: 160 }}
              size="small"
              allowClear
              data-testid="rc-filter-model"
            />
            <Space size={6}>
              <Switch
                size="small"
                checked={includeExpired}
                onChange={setIncludeExpired}
                aria-label={t("rate_card_page.include_expired")}
                data-testid="rc-include-expired"
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t("rate_card_page.include_expired")}
              </Text>
            </Space>
            <Button
              type="primary"
              size="small"
              icon={<Plus size={14} strokeWidth={1.5} />}
              onClick={() => setCreateOpen(true)}
              data-testid="rc-create-open"
            >
              {t("rate_card_page.create")}
            </Button>
          </Space>
        }
      />

      {error !== null && (
        <Alert
          type="error"
          showIcon
          message={t("rate_card_page.failed_to_load")}
          description={error}
          style={{ marginBottom: 16 }}
          data-testid="rate-card-error"
        />
      )}

      <Table<RateCardRecord>
        size="small"
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={false}
        locale={{ emptyText: <Empty description={t("rate_card_page.empty")} /> }}
        data-testid="rate-card-table"
      />

      <Modal
        title={t("rate_card_page.create")}
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        confirmLoading={creating}
        okText={t("common.save")}
        data-testid="rc-create-modal"
      >
        <Form<CreateFormValues> form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="provider"
            label={t("rate_card_page.field_provider")}
            rules={[{ required: true }]}
          >
            <Input data-testid="rc-create-provider" />
          </Form.Item>
          <Form.Item
            name="model"
            label={t("rate_card_page.field_model")}
            rules={[{ required: true }]}
          >
            <Input data-testid="rc-create-model" />
          </Form.Item>
          <MicrosField name="input_token_micros" label={t("rate_card_page.field_input")} />
          <MicrosField name="output_token_micros" label={t("rate_card_page.field_output")} />
          <MicrosField
            name="cache_creation_token_micros"
            label={t("rate_card_page.field_cache_creation")}
          />
          <MicrosField
            name="cache_read_token_micros"
            label={t("rate_card_page.field_cache_read")}
          />
          <Form.Item name="markup_bps" label={t("rate_card_page.field_markup")}>
            <InputNumber min={0} style={{ width: "100%" }} data-testid="rc-markup_bps" />
          </Form.Item>
          <Form.Item name="plan_tier" label={t("rate_card_page.field_plan")}>
            <Select
              options={PLAN_OPTIONS.map((p) => ({
                value: p,
                label: p === "all" ? t("rate_card_page.all_plans") : p,
              }))}
              allowClear
            />
          </Form.Item>
          <Form.Item
            name="effective_from"
            label={t("rate_card_page.field_effective_from")}
            rules={[{ required: true }]}
          >
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="effective_until"
            label={t("rate_card_page.field_effective_until")}
            dependencies={["effective_from"]}
            rules={[
              ({ getFieldValue }) => ({
                validator(_, value: Dayjs | null | undefined) {
                  const from: Dayjs | undefined = getFieldValue("effective_from");
                  if (!value || !from || value.isAfter(from)) return Promise.resolve();
                  return Promise.reject(new Error(t("rate_card_page.until_after_from")));
                },
              }),
            ]}
          >
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={
          editing !== null
            ? t("rate_card_page.edit_title", {
                provider: editing.provider,
                model: editing.model,
              })
            : ""
        }
        open={editing !== null}
        onClose={() => setEditing(null)}
        width={480}
        extra={
          <Button type="primary" loading={saving} onClick={() => editForm.submit()}>
            {t("common.save")}
          </Button>
        }
        data-testid="rc-edit-drawer"
      >
        {editing !== null && (
          <>
            {/* Mini-ADR H-20 — immutable identity fields shown read-only. */}
            <Alert
              type="info"
              showIcon
              message={t("rate_card_page.identity_immutable")}
              style={{ marginBottom: 16 }}
              data-testid="rc-identity-note"
            />
            <dl
              style={{
                display: "grid",
                gridTemplateColumns: "140px 1fr",
                rowGap: 6,
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              <dt style={{ color: "var(--hx-text-tertiary)" }}>
                {t("rate_card_page.field_provider")}
              </dt>
              <dd style={{ margin: 0 }}>{editing.provider}</dd>
              <dt style={{ color: "var(--hx-text-tertiary)" }}>
                {t("rate_card_page.field_model")}
              </dt>
              <dd style={{ margin: 0 }} className="mono">
                {editing.model}
              </dd>
              <dt style={{ color: "var(--hx-text-tertiary)" }}>
                {t("rate_card_page.field_plan")}
              </dt>
              <dd style={{ margin: 0 }}>
                {editing.plan_tier ?? t("rate_card_page.all_plans")}
              </dd>
              <dt style={{ color: "var(--hx-text-tertiary)" }}>
                {t("rate_card_page.field_effective_from")}
              </dt>
              <dd style={{ margin: 0 }}>
                {new Date(editing.effective_from).toLocaleString()}
              </dd>
            </dl>
            <Form<EditFormValues> form={editForm} layout="vertical" onFinish={handleEdit}>
              <MicrosField name="input_token_micros" label={t("rate_card_page.field_input")} />
              <MicrosField
                name="output_token_micros"
                label={t("rate_card_page.field_output")}
              />
              <MicrosField
                name="cache_creation_token_micros"
                label={t("rate_card_page.field_cache_creation")}
              />
              <MicrosField
                name="cache_read_token_micros"
                label={t("rate_card_page.field_cache_read")}
              />
              <Form.Item name="markup_bps" label={t("rate_card_page.field_markup")}>
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item
                name="effective_until"
                label={t("rate_card_page.field_effective_until")}
              >
                <DatePicker showTime style={{ width: "100%" }} />
              </Form.Item>
            </Form>
          </>
        )}
      </Drawer>
    </div>
  );
}
