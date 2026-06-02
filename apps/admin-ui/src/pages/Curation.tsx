/**
 * Curation+Eval page — Stream H.4 PR 1.
 *
 * Single ``/curation`` route hosting two sub-panels: candidates review
 * (default) + eval-datasets CRUD. Internal Antd ``<Tabs>`` switch — no
 * URL change, since the panels share the same tenant scope + cross-tenant
 * banner shell. Sub-panels live under ``pages/curation/`` to keep the
 * outer file small (Mini-ADR style file org).
 */
import { useState } from "react";
import { Tabs } from "antd";
import { CheckSquare } from "lucide-react";
import { useTranslation } from "react-i18next";

import { CandidatesPanel } from "./curation/CandidatesPanel";
import { EvalDatasetsPanel } from "./curation/EvalDatasetsPanel";
import { PageHeader } from "../components/PageHeader";

type CurationTab = "candidates" | "datasets";

export function Curation() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<CurationTab>("candidates");

  return (
    <div data-testid="curation-root">
      <PageHeader
        icon={<CheckSquare size={18} strokeWidth={1.5} />}
        title={t("curation.page_title")}
        subtitle={t("curation.subtitle")}
      />

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as CurationTab)}
        items={[
          { key: "candidates", label: t("curation.tab_candidates") },
          { key: "datasets", label: t("curation.tab_datasets") },
        ]}
        data-testid="curation-tabs"
      />

      {activeTab === "candidates" && <CandidatesPanel />}
      {activeTab === "datasets" && <EvalDatasetsPanel />}
    </div>
  );
}
