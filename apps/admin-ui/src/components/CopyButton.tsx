/**
 * CopyButton — copies ``text`` to the clipboard with brief confirmation.
 *
 * A small text/icon button: the Copy glyph flips to a Check for ~1.5s after a
 * successful copy. Clipboard failures (insecure context, denied permission)
 * are swallowed — the worst case is a no-op, never a thrown error.
 */
import { useState } from "react";
import { Button, Tooltip } from "antd";
import { Check, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";

interface CopyButtonProps {
  text: string;
  testId?: string;
}

export function CopyButton({ text, testId }: CopyButtonProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (insecure context / denied) — no-op.
    }
  };

  return (
    <Tooltip title={copied ? t("common.copied") : t("common.copy")}>
      <Button
        type="text"
        size="small"
        aria-label={t("common.copy")}
        data-testid={testId}
        onClick={handleCopy}
        icon={
          copied ? <Check size={13} strokeWidth={1.75} /> : <Copy size={13} strokeWidth={1.75} />
        }
      />
    </Tooltip>
  );
}
