/**
 * Tier 2 capability pickers — knowledge bases (RAG), attached skills, and
 * static sub-agent delegation. Each loads its option list from the existing
 * list endpoints and degrades to an empty list on failure (the picker stays
 * usable, just without suggestions). Every control emits the FULL merged
 * manifest via the form_model writers, preserving non-curated fields.
 */
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Button, Input, Select, Typography } from "antd";
import { useTranslation } from "react-i18next";

import { listAgents } from "../../api/agents";
import { listBases } from "../../api/knowledge";
import { listSkills } from "../../api/skills";
import { FieldHelp } from "../FieldHelp";
import {
  readKnowledgeRefs,
  readSkills,
  readSubagents,
  setKnowledgeRefs,
  setSkills,
  setSubagents,
  type SubAgentFields,
} from "./form_model";

const { Text } = Typography;

const SECTION: CSSProperties = { marginBottom: 24 };

function Heading({ children }: { children: ReactNode }) {
  return <h3 style={{ fontSize: 15, margin: "0 0 12px" }}>{children}</h3>;
}

interface CapabilityPickersProps {
  formData: unknown;
  onChange: (data: unknown) => void;
}

export function CapabilityPickers({ formData, onChange }: CapabilityPickersProps) {
  const { t } = useTranslation();
  const [bases, setBases] = useState<string[]>([]);
  const [skills, setSkillOptions] = useState<string[]>([]);
  const [agents, setAgents] = useState<string[]>([]);

  useEffect(() => {
    let alive = true;
    listBases().then(
      (b) => alive && setBases((b ?? []).map((x) => x.name)),
      () => {},
    );
    listSkills().then(
      (s) => {
        if (!alive) return;
        const names = [...(s?.items ?? []), ...(s?.platform_items ?? [])].map((x) => x.name);
        setSkillOptions([...new Set(names)]);
      },
      () => {},
    );
    listAgents().then(
      (a) => alive && setAgents((a?.items ?? []).map((x) => `${x.name}@${x.version}`)),
      () => {},
    );
    return () => {
      alive = false;
    };
  }, []);

  const knowledgeRefs = readKnowledgeRefs(formData);
  const attachedSkills = readSkills(formData);
  const subagents = readSubagents(formData);

  const toOptions = (values: string[]) => values.map((v) => ({ label: v, value: v }));

  const patchSubagent = (i: number, patch: Partial<SubAgentFields>): void => {
    const next = subagents.map((row, idx) => (idx === i ? { ...row, ...patch } : row));
    onChange(setSubagents(formData, next));
  };
  const addSubagent = (): void =>
    onChange(setSubagents(formData, [...subagents, { name: "", agent_ref: "", description: "" }]));
  const removeSubagent = (i: number): void =>
    onChange(setSubagents(formData, subagents.filter((_, idx) => idx !== i)));

  return (
    <>
      <section data-testid="af-knowledge" style={SECTION}>
        <Heading>
          {t("agent_form.section_knowledge")}
          <FieldHelp text={t("agent_form.section_knowledge_help")} testId="af-knowledge" />
        </Heading>
        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          {t("agent_form.knowledge_hint")}
        </Text>
        <div data-testid="af-knowledge-select">
          <Select
            mode="tags"
            style={{ width: "100%" }}
            value={knowledgeRefs}
            options={toOptions(bases)}
            aria-label={t("agent_form.section_knowledge")}
            placeholder={t("agent_form.knowledge_placeholder")}
            onChange={(v: string[]) => onChange(setKnowledgeRefs(formData, v))}
          />
        </div>
      </section>

      <section data-testid="af-skills" style={SECTION}>
        <Heading>
          {t("agent_form.section_skills")}
          <FieldHelp text={t("agent_form.section_skills_help")} testId="af-skills" />
        </Heading>
        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          {t("agent_form.skills_hint")}
        </Text>
        <div data-testid="af-skills-select">
          <Select
            mode="tags"
            style={{ width: "100%" }}
            value={attachedSkills}
            options={toOptions(skills)}
            aria-label={t("agent_form.section_skills")}
            placeholder={t("agent_form.skills_placeholder")}
            onChange={(v: string[]) => onChange(setSkills(formData, v))}
          />
        </div>
      </section>

      <section data-testid="af-subagents" style={SECTION}>
        <Heading>
          {t("agent_form.section_subagents")}
          <FieldHelp text={t("agent_form.section_subagents_help")} testId="af-subagents" />
        </Heading>
        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          {t("agent_form.subagents_hint")}
        </Text>
        {subagents.map((row, i) => (
          <div
            key={i}
            data-testid={`af-subagent-row-${i}`}
            style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}
          >
            <Input
              style={{ width: 160 }}
              value={row.name ?? ""}
              data-testid={`af-subagent-name-${i}`}
              aria-label={t("agent_form.subagent_name")}
              placeholder={t("agent_form.subagent_name")}
              onChange={(e) => patchSubagent(i, { name: e.target.value })}
            />
            <Select
              style={{ width: 200 }}
              value={row.agent_ref || undefined}
              options={toOptions(agents)}
              data-testid={`af-subagent-ref-${i}`}
              aria-label={t("agent_form.subagent_ref")}
              placeholder={t("agent_form.subagent_ref")}
              onChange={(v: string) => patchSubagent(i, { agent_ref: v })}
            />
            <Input
              style={{ flex: 1 }}
              value={row.description ?? ""}
              data-testid={`af-subagent-desc-${i}`}
              aria-label={t("agent_form.subagent_description")}
              placeholder={t("agent_form.subagent_description")}
              onChange={(e) => patchSubagent(i, { description: e.target.value })}
            />
            <Button
              type="text"
              danger
              size="small"
              data-testid={`af-subagent-remove-${i}`}
              aria-label={t("agent_form.subagent_remove")}
              onClick={() => removeSubagent(i)}
            >
              {t("agent_form.subagent_remove")}
            </Button>
          </div>
        ))}
        <Button
          type="dashed"
          size="small"
          data-testid="af-subagent-add"
          onClick={addSubagent}
        >
          {t("agent_form.subagent_add")}
        </Button>
      </section>
    </>
  );
}
