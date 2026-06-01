/**
 * Manifest JSON Schema SDK — Stream S PR C (Mini-ADR S-1).
 *
 * Wraps ``GET /v1/agents/schema`` which returns ``AgentSpec.model_json_schema()``
 * inside the standard ``{ success, data, error }`` envelope. The visual editor
 * renders its form straight from this, so the form never drifts from the
 * backend contract.
 */
import { getJson } from "./client";

/** A JSON Schema document. Kept loose — RJSF consumes it structurally. */
export type JsonSchema = Record<string, unknown>;

export async function fetchAgentSchema(): Promise<JsonSchema> {
  return getJson<JsonSchema>("/v1/agents/schema");
}
