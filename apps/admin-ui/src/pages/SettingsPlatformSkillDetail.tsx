/**
 * Platform skill detail page — skill-authoring-ia Phase C.
 *
 * Reuses the tenant ``SkillDetail`` editor through the injected
 * ``platformSkillApi`` (``/v1/platform/skills``) + the ``platform`` variant
 * (hides the tenant-flywheel panels, drops the "stale" status, shows the
 * ``required_tier`` tag). Routed at ``/settings/platform-skills/:skillId``.
 */
import { useTranslation } from "react-i18next";

import { platformSkillApi } from "../api/skillApi";
import { SkillDetail } from "./SkillDetail";

export function SettingsPlatformSkillDetail() {
  const { t } = useTranslation();
  return (
    <SkillDetail
      api={platformSkillApi}
      variant="platform"
      backTo={{ label: t("nav.platform_skills"), to: "/settings/platform-skills" }}
    />
  );
}
