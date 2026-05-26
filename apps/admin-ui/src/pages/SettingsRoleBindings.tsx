/**
 * Settings — Role Bindings page (Stream H.4 PR 7).
 *
 * Subject (user / service_account) → role mappings. The
 * ``platform_scope`` checkbox in the Create drawer is only visible to
 * system_admins (mirrors backend gate at ``role_bindings.py:66``);
 * checking it requires type-to-confirm ``CONFIRM PLATFORM ROLE`` to
 * prevent accidental cross-tenant elevation.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  App,
  Breadcrumb,
  Button,
  Checkbox,
  Drawer,
  Empty,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { ChevronRight, Globe2, RefreshCw, Shield, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  createRoleBinding,
  deleteRoleBinding,
  listRoleBindings,
  type CreateRoleBindingBody,
  type RoleBindingList,
  type RoleBindingRecord,
  type RoleName,
  type SubjectType,
} from "../api/role_bindings";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useTenantScope } from "../tenant/TenantScopeContext";

const { Text } = Typography;

const SUBJECT_OPTIONS: SubjectType[] = ["user", "service_account"];
const ROLE_OPTIONS: RoleName[] = [
  "tenant_admin",
  "developer",
  "viewer",
  "system_admin",
];
const CONFIRM_PHRASE = "CONFIRM PLATFORM ROLE";

interface CreateForm {
  subject_type: SubjectType;
  subject_id: string;
  role: RoleName;
  platform_scope: boolean;
  confirm: string;
}

export function SettingsRoleBindings() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const { scope, apiTenantScope } = useTenantScope();
  const auth = useAuth();
  const isSystemAdmin = auth.identity?.isSystemAdmin ?? false;

  const [data, setData] = useState<RoleBindingList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [platformScopeFilter, setPlatformScopeFilter] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createForm] = Form.useForm<CreateForm>();
  const platformScopeChecked = Form.useWatch("platform_scope", createForm) ?? false;
  const roleSelected = Form.useWatch("role", createForm);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listRoleBindings({
        tenantScope: apiTenantScope,
        platformScope: platformScopeFilter,
      });
      setData(result);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `${err.code}: ${err.message}`
          : err instanceof Error
            ? err.message
            : "unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [apiTenantScope, platformScopeFilter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const onCreate = useCallback(async () => {
    const values = await createForm.validateFields();
    if (values.platform_scope && values.confirm !== CONFIRM_PHRASE) {
      message.error(t("settings_iam.rb_confirm_required"));
      return;
    }
    const body: CreateRoleBindingBody = {
      subject_type: values.subject_type,
      subject_id: values.subject_id,
      role: values.role,
      platform_scope: values.platform_scope,
    };
    setCreateSubmitting(true);
    try {
      await createRoleBinding(body);
      message.success(t("settings_iam.rb_created"));
      setCreateOpen(false);
      createForm.resetFields();
      refresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "failed");
    } finally {
      setCreateSubmitting(false);
    }
  }, [createForm, message, refresh, t]);

  const onDelete = useCallback(
    async (id: string) => {
      try {
        await deleteRoleBinding(id);
        message.success(t("settings_iam.rb_deleted"));
        refresh();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "failed");
      }
    },
    [message, refresh, t],
  );

  const columns: TableColumnsType<RoleBindingRecord> = useMemo(() => [
    {
      title: t("settings_iam.col_subject_type"),
      dataIndex: "subject_type",
      key: "subject_type",
      width: 140,
      render: (v: SubjectType) => <Tag>{v}</Tag>,
    },
    {
      title: t("settings_iam.col_subject_id"),
      dataIndex: "subject_id",
      key: "subject_id",
      render: (uid: string) => (
        <Tooltip title={uid}>
          <Text code style={{ fontSize: 11 }}>{uid}</Text>
        </Tooltip>
      ),
    },
    {
      title: t("settings_iam.col_role"),
      dataIndex: "role",
      key: "role",
      width: 160,
      render: (r: RoleName, record) => (
        <Space size={6}>
          <Tag color={r === "system_admin" ? "magenta" : "blue"}>{r}</Tag>
          {record.platform_scope && (
            <Tag color="purple" icon={<Globe2 size={11} strokeWidth={1.75} />} bordered={false}>
              platform
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: t("settings_iam.col_tenant"),
      dataIndex: "tenant_id",
      key: "tenant",
      width: 140,
      render: (tid: string | null) => (
        tid === null ? (
          <Text type="secondary" style={{ fontSize: 12 }}>—</Text>
        ) : (
          <Text code style={{ fontSize: 11 }}>{tid.slice(0, 8)}…</Text>
        )
      ),
    },
    {
      title: t("settings_iam.col_granted_at"),
      dataIndex: "granted_at",
      key: "granted_at",
      width: 180,
      render: (iso: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {new Date(iso).toLocaleString()}
        </Text>
      ),
    },
    {
      title: t("settings_iam.col_actions"),
      key: "actions",
      width: 120,
      render: (_, record) => (
        <Popconfirm
          title={t("settings_iam.rb_delete_confirm_title")}
          description={
            record.platform_scope
              ? t("settings_iam.rb_delete_platform_warn")
              : t("settings_iam.rb_delete_confirm_body")
          }
          okType="danger"
          okText={t("common.delete")}
          cancelText={t("common.cancel")}
          onConfirm={() => onDelete(record.id)}
        >
          <Button
            size="small"
            danger
            icon={<Trash2 size={12} strokeWidth={1.75} />}
            data-testid={`rb-delete-${record.id}`}
          >
            {t("common.delete")}
          </Button>
        </Popconfirm>
      ),
    },
  ], [t, onDelete]);

  const isCrossTenant = data?.cross_tenant ?? false;

  return (
    <div data-testid="rb-root">
      <div className="hx-page-header">
        <Breadcrumb
          separator={<ChevronRight size={12} strokeWidth={1.5} />}
          items={[{ title: t("common.home") }, { title: t("settings_iam.rb_page_title") }]}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, marginBottom: 16 }}>
          <Shield size={20} strokeWidth={1.5} />
          <h1 style={{ margin: 0 }}>{t("settings_iam.rb_page_title")}</h1>
          {isCrossTenant && (
            <Tag icon={<Globe2 size={12} strokeWidth={1.5} />} color="purple" data-testid="rb-cross-banner">
              {t("settings_iam.cross_tenant_banner")}
            </Tag>
          )}
          <span style={{ flex: 1 }} />
          {isSystemAdmin && (
            <Checkbox
              checked={platformScopeFilter}
              onChange={(e) => setPlatformScopeFilter(e.target.checked)}
              data-testid="rb-platform-scope-filter"
            >
              {t("settings_iam.rb_filter_platform_scope")}
            </Checkbox>
          )}
          <Button onClick={refresh} loading={loading} icon={<RefreshCw size={14} strokeWidth={1.5} />}>
            {t("common.refresh")}
          </Button>
          <Button
            type="primary"
            onClick={() => setCreateOpen(true)}
            data-testid="rb-create-btn"
          >
            {t("settings_iam.rb_create")}
          </Button>
        </div>
        <p style={{ color: "var(--hx-text-secondary)", fontSize: 13, margin: "0 0 12px" }}>
          {t("settings_iam.rb_subtitle")}
        </p>
      </div>

      {error !== null && (
        <Alert
          type="error"
          showIcon
          message={t("settings_iam.failed_to_load")}
          description={error}
          style={{ marginBottom: 12 }}
          data-testid="rb-error"
        />
      )}

      <Table<RoleBindingRecord>
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey={(r) => r.id}
        loading={loading}
        pagination={{ pageSize: 50, showSizeChanger: false, total: data?.total ?? 0 }}
        locale={{
          emptyText: (
            <Empty
              description={
                scope === "*"
                  ? t("settings_iam.rb_empty_cross")
                  : platformScopeFilter
                    ? t("settings_iam.rb_empty_platform")
                    : t("settings_iam.rb_empty_home")
              }
            />
          ),
        }}
        data-testid="rb-table"
      />

      <Drawer
        title={t("settings_iam.rb_create_drawer_title")}
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        width={520}
        data-testid="rb-create-drawer"
        extra={
          <Space>
            <Button onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
            <Button
              type={platformScopeChecked ? "primary" : "primary"}
              danger={platformScopeChecked}
              loading={createSubmitting}
              onClick={onCreate}
              data-testid="rb-create-submit"
            >
              {platformScopeChecked
                ? t("settings_iam.rb_create_platform_submit")
                : t("settings_iam.rb_create_submit")}
            </Button>
          </Space>
        }
      >
        <Form form={createForm} layout="vertical" initialValues={{ subject_type: "user", platform_scope: false }}>
          <Form.Item
            name="subject_type"
            label={t("settings_iam.field_subject_type")}
            rules={[{ required: true }]}
          >
            <Select<SubjectType>
              data-testid="rb-subject-type-select"
              options={SUBJECT_OPTIONS.map((s) => ({ value: s, label: s }))}
            />
          </Form.Item>
          <Form.Item
            name="subject_id"
            label={t("settings_iam.field_subject_id")}
            rules={[{ required: true, message: t("settings_iam.subject_id_required") }]}
          >
            <Input data-testid="rb-subject-id-input" placeholder="UUID" />
          </Form.Item>
          <Form.Item
            name="role"
            label={t("settings_iam.field_role")}
            rules={[{ required: true, message: t("settings_iam.role_required") }]}
          >
            <Select<RoleName>
              data-testid="rb-role-select"
              options={ROLE_OPTIONS.map((r) => ({ value: r, label: r }))}
            />
          </Form.Item>
          {isSystemAdmin && (
            <Form.Item
              name="platform_scope"
              valuePropName="checked"
              extra={t("settings_iam.platform_scope_hint")}
            >
              <Checkbox data-testid="rb-platform-scope-checkbox">
                {t("settings_iam.field_platform_scope")}
              </Checkbox>
            </Form.Item>
          )}
          {platformScopeChecked && (
            <>
              <Alert
                type="warning"
                showIcon
                message={t("settings_iam.platform_scope_warn_title")}
                description={t("settings_iam.platform_scope_warn_body")}
                style={{ marginBottom: 12 }}
              />
              <Form.Item
                name="confirm"
                label={t("settings_iam.confirm_phrase_label", { phrase: CONFIRM_PHRASE })}
                rules={[
                  {
                    validator: (_, value) =>
                      value === CONFIRM_PHRASE
                        ? Promise.resolve()
                        : Promise.reject(new Error(t("settings_iam.rb_confirm_required"))),
                  },
                ]}
              >
                <Input
                  placeholder={CONFIRM_PHRASE}
                  style={{ fontFamily: "var(--hx-font-mono)" }}
                  data-testid="rb-confirm-input"
                />
              </Form.Item>
            </>
          )}
          {roleSelected === "system_admin" && !platformScopeChecked && (
            <Alert
              type="info"
              showIcon
              message={t("settings_iam.role_requires_platform_scope")}
            />
          )}
        </Form>
      </Drawer>
    </div>
  );
}
