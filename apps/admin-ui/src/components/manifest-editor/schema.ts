/**
 * Process-lifetime cache for the AgentSpec JSON Schema. The schema only
 * changes on backend deploy, so one fetch per page load is plenty. The
 * cache stores the in-flight promise to dedupe concurrent callers.
 */
import { fetchAgentSchema, type JsonSchema } from "../../api/manifest_schema";

let cached: Promise<JsonSchema> | null = null;

export function loadAgentSchema(): Promise<JsonSchema> {
  if (cached === null) {
    cached = fetchAgentSchema();
  }
  return cached;
}

/** Test-only: clear the cache between cases. */
export function __resetSchemaCacheForTest(): void {
  cached = null;
}
