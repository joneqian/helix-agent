/**
 * Language switcher — Stream H.1b PR 2a.
 *
 * Toggles between zh-CN and en in place. ``i18next-browser-languagedetector``
 * is already wired with ``caches: ["localStorage"]`` (see ``i18n/index.ts``),
 * so calling ``i18n.changeLanguage`` persists automatically.
 */
import { Button, Tooltip } from "antd";
import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.resolvedLanguage ?? i18n.language;
  const isZh = current?.startsWith("zh") ?? true;
  const next = isZh ? "en" : "zh-CN";
  const label = isZh ? "EN" : "中";

  return (
    <Tooltip title={isZh ? "English" : "中文"}>
      <Button
        type="text"
        size="small"
        onClick={() => {
          void i18n.changeLanguage(next);
        }}
        aria-label={isZh ? "Switch to English" : "切换到中文"}
        data-testid="language-switcher"
        icon={<Languages size={14} strokeWidth={1.5} />}
      >
        <span style={{ fontSize: 11, fontWeight: 500 }}>{label}</span>
      </Button>
    </Tooltip>
  );
}
