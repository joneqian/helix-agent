/**
 * Platform Agent Template SDK — backed by ``/v1/platform/agent-templates``
 * (platform, system_admin only), Stream Agent-Templates.
 *
 * A *template* is a platform-curated base Agent manifest (a full ``AgentSpec``)
 * that tenants ``fork`` into their own agents via ``extends``. Versioned by
 * ``(name, version)`` so a tenant can pin a version. Marketplace metadata
 * (display_name / category / icon / required_tier / status) is governance-level,
 * distinct from the manifest itself.
 *
 * The backend returns the standard ``{success, data, error}`` envelope; the
 * unwrapped payload is typed below. ``getJson`` / ``postJson`` / ``putJson`` /
 * ``patchJson`` call ``unwrap()`` internally — callers receive the data directly.
 */
import { apiClient, getJson, patchJson, postJson, putJson } from "./client";

const BASE = "/v1/platform/agent-templates";

export type TemplateTier = "free" | "pro" | "enterprise";
export type TemplateStatus = "draft" | "published";

/** Preset template categories — stored as the stable slug, displayed via the
 *  i18n ``labelKey``. */
export const TEMPLATE_CATEGORIES: { value: string; labelKey: string }[] = [
  { value: "support", labelKey: "agent_templates.cat_support" },
  { value: "sales", labelKey: "agent_templates.cat_sales" },
  { value: "research", labelKey: "agent_templates.cat_research" },
  { value: "coding", labelKey: "agent_templates.cat_coding" },
  { value: "data", labelKey: "agent_templates.cat_data" },
  { value: "productivity", labelKey: "agent_templates.cat_productivity" },
  { value: "general", labelKey: "agent_templates.cat_general" },
  { value: "other", labelKey: "agent_templates.cat_other" },
];

/** The i18n key for a category slug, or ``null`` for an unknown (legacy
 *  free-text) value the caller should render verbatim. */
export function templateCategoryLabelKey(slug: string): string | null {
  return TEMPLATE_CATEGORIES.find((c) => c.value === slug)?.labelKey ?? null;
}

/** A full Agent manifest. Typed loosely — the editor round-trips it as YAML/JSON
 *  and the backend validates it as an ``AgentSpec``. */
export type AgentManifest = Record<string, unknown>;

export interface AgentTemplate {
  id: string;
  tenant_id: string | null;
  name: string;
  version: string;
  spec: AgentManifest;
  spec_sha256: string;
  display_name: string;
  description: string;
  category: string;
  icon: string | null;
  required_tier: TemplateTier;
  status: TemplateStatus;
  enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/** Create body for ``POST /v1/platform/agent-templates``. ``name``/``version``
 *  are derived by the backend from ``spec.metadata``. */
export interface TemplateCreateBody {
  spec: AgentManifest;
  display_name: string;
  description?: string;
  category?: string;
  icon?: string | null;
  required_tier?: TemplateTier;
  status?: TemplateStatus;
  enabled?: boolean;
}

/** Partial marketplace-metadata update (``PATCH``). ``undefined`` = unchanged. */
export interface TemplateMetaPatch {
  display_name?: string;
  description?: string;
  category?: string;
  icon?: string | null;
  required_tier?: TemplateTier;
  status?: TemplateStatus;
  enabled?: boolean;
}

function ref(name: string, version: string): string {
  return `${BASE}/${encodeURIComponent(name)}/${encodeURIComponent(version)}`;
}

export function listAgentTemplates(params?: {
  category?: string;
  status?: TemplateStatus;
}): Promise<AgentTemplate[]> {
  return getJson<AgentTemplate[]>(BASE, { params });
}

export function createAgentTemplate(body: TemplateCreateBody): Promise<AgentTemplate> {
  return postJson<AgentTemplate>(BASE, body);
}

export function getAgentTemplate(name: string, version: string): Promise<AgentTemplate> {
  return getJson<AgentTemplate>(ref(name, version));
}

/** Replace the base manifest of an existing version (PUT). */
export function updateTemplateSpec(
  name: string,
  version: string,
  spec: AgentManifest,
): Promise<AgentTemplate> {
  return putJson<AgentTemplate>(ref(name, version), spec);
}

/** Patch marketplace metadata / status (PATCH). */
export function patchTemplateMeta(
  name: string,
  version: string,
  patch: TemplateMetaPatch,
): Promise<AgentTemplate> {
  return patchJson<AgentTemplate>(ref(name, version), patch);
}

export async function deleteAgentTemplate(name: string, version: string): Promise<void> {
  await apiClient.delete(ref(name, version));
}
