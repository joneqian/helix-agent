import { Empty } from "antd";
import { Construction } from "lucide-react";
import { useTranslation } from "react-i18next";

export function ComingSoon({ title }: { title: string }) {
  const { t } = useTranslation();
  return (
    <div>
      <div className="hx-page-header">
        <h1>{title}</h1>
      </div>
      <Empty
        image={<Construction size={48} strokeWidth={1.5} style={{ color: "var(--hx-text-tertiary)", margin: "0 auto" }} />}
        description={
          <>
            <div style={{ fontSize: 14, color: "var(--hx-text-primary)", marginBottom: 4 }}>
              {t("coming_soon.title_prefix")}
            </div>
            <div style={{ fontSize: 13, color: "var(--hx-text-tertiary)" }}>
              {t("coming_soon.body")}<br />
              {t("coming_soon.other_pages_prefix")}(<strong>{title}</strong>){t("coming_soon.other_pages_suffix")}
            </div>
          </>
        }
        style={{ padding: "80px 24px" }}
      />
    </div>
  );
}
