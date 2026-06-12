/**
 * SDK for ``/v1/platform/rate-card`` — Stream H.9 PR 1 (design § 6.10).
 *
 * All endpoints are ENVELOPED (``{success,data,error}``) — calls go
 * through the ``getJson``/``postJson``/``patchJson`` helpers (unlike
 * the raw H.7/H.8 routers; [memory:envelope-vs-raw-contract-check]).
 * DELETE is a bare 204.
 *
 * Authorization is a double gate server-side (``require("billing",·)``
 * + ``is_system_admin``); the page's frontend gate is UX only
 * (Mini-ADR H-22).
 *
 * Prices are MICRO-USD PER TOKEN (``*_token_micros``) plus a
 * basis-point markup. The UI takes raw micros and shows a read-only
 * $/1M-tokens conversion — no implicit unit conversion (Mini-ADR H-21).
 */
import { apiClient, getJson, patchJson, postJson } from "./client";

export type PlanTier = "free" | "pro" | "enterprise";

export interface RateCardRecord {
  id: string;
  /** NULL = platform-global (the only shape today). */
  tenant_id: string | null;
  provider: string;
  model: string;
  input_token_micros: number;
  output_token_micros: number;
  cache_creation_token_micros: number;
  cache_read_token_micros: number;
  markup_bps: number;
  plan_tier: PlanTier | null;
  effective_from: string;
  effective_until: string | null;
}

export interface RateCardUpsert {
  provider: string;
  model: string;
  input_token_micros: number;
  output_token_micros: number;
  cache_creation_token_micros?: number;
  cache_read_token_micros?: number;
  markup_bps?: number;
  plan_tier?: PlanTier | null;
  effective_from: string;
  effective_until?: string | null;
}

/** Mutable fields only — provider/model/plan_tier/effective_from are the
 *  row's temporal+specificity identity and immutable post-create; reprice
 *  by inserting a new row (Mini-ADR H-20). */
export interface RateCardPatch {
  input_token_micros?: number;
  output_token_micros?: number;
  cache_creation_token_micros?: number;
  cache_read_token_micros?: number;
  markup_bps?: number;
  effective_until?: string | null;
}

export async function listRateCards(
  params: { provider?: string; model?: string; includeExpired?: boolean } = {},
): Promise<RateCardRecord[]> {
  return getJson<RateCardRecord[]>("/v1/platform/rate-card", {
    params: {
      provider: params.provider,
      model: params.model,
      include_expired: params.includeExpired,
    },
  });
}

export async function createRateCard(body: RateCardUpsert): Promise<RateCardRecord> {
  return postJson<RateCardRecord>("/v1/platform/rate-card", body);
}

export async function getRateCard(id: string): Promise<RateCardRecord> {
  return getJson<RateCardRecord>(`/v1/platform/rate-card/${encodeURIComponent(id)}`);
}

export async function patchRateCard(id: string, body: RateCardPatch): Promise<RateCardRecord> {
  return patchJson<RateCardRecord>(`/v1/platform/rate-card/${encodeURIComponent(id)}`, body);
}

export async function deleteRateCard(id: string): Promise<void> {
  await apiClient.delete(`/v1/platform/rate-card/${encodeURIComponent(id)}`);
}

/** Read-only $/1M-tokens hint next to a micros input (H-21): micros are
 *  micro-USD per token, so $/1M tokens = micros (1e-6 USD × 1e6 tokens). */
export function microsPerTokenToUsdPerMillion(micros: number): string {
  return `$${micros.toLocaleString("en-US")} / 1M tokens`;
}
