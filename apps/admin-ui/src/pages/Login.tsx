/**
 * Login page — Stream H.1b PR 1 + PR 2a (i18n).
 *
 * M0 surface: an operator pastes a JWT (OIDC) or a helix API key and
 * we persist it to localStorage. PR 2b of H.1b replaces this with a
 * proper OIDC code flow (helix doesn't own user auth — it federates
 * to the tenant's OIDC provider).
 */
import { useState } from "react";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "../auth/AuthContext";

const { Title, Paragraph, Text } = Typography;

interface LoginLocationState {
  from?: string;
}

export function Login() {
  const { t } = useTranslation();
  const { status, login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (status === "authenticated") {
    const from = (location.state as LoginLocationState | null)?.from ?? "/agents";
    return <Navigate to={from} replace />;
  }

  const onFinish = (values: { token: string }) => {
    const trimmed = values.token.trim();
    if (!trimmed) {
      setSubmitError(t("login.token_empty"));
      return;
    }
    setSubmitError(null);
    login(trimmed);
    const from = (location.state as LoginLocationState | null)?.from ?? "/agents";
    navigate(from, { replace: true });
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        background: "var(--hx-surface-base)",
      }}
    >
      <Card
        style={{ width: 480, maxWidth: "100%" }}
        styles={{ body: { padding: 32 } }}
        data-testid="login-card"
      >
        <Title level={3} style={{ marginTop: 0 }}>
          {t("login.title")}
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 24 }}>
          {t("login.paragraph")}
        </Paragraph>

        {submitError && (
          <Alert
            type="error"
            showIcon
            message={submitError}
            style={{ marginBottom: 16 }}
          />
        )}

        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="token"
            label={t("login.token_label")}
            rules={[{ required: true, message: t("login.token_required") }]}
          >
            <Input.TextArea
              rows={4}
              placeholder={t("login.token_placeholder")}
              autoComplete="off"
              spellCheck={false}
              data-testid="login-token"
              style={{ fontFamily: "var(--hx-font-mono, ui-monospace)" }}
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            data-testid="login-submit"
          >
            {t("common.sign_in")}
          </Button>
        </Form>

        <Paragraph type="secondary" style={{ marginTop: 24, marginBottom: 0 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t("login.pr2_hint")}&nbsp;
            <code>docs/streams/STREAM-H-DESIGN.md</code>.
          </Text>
        </Paragraph>
      </Card>
    </div>
  );
}
