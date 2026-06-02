/**
 * Model catalog SDK — Stream S PR D (Mini-ADR S-4 client side).
 *
 * ``GET /v1/model-catalog`` returns the selectable models per *configured*
 * provider (the backend already intersects the catalog with platform
 * credentials and drops deprecated models), inside the standard envelope.
 */
import { getJson } from "./client";

export interface CatalogModel {
  name: string;
  vision: boolean;
  embeddings: boolean;
  context_window: number | null;
  deprecated: boolean;
}

export interface ProviderModels {
  provider: string;
  models: CatalogModel[];
}

export interface ModelCatalog {
  providers: ProviderModels[];
}

export async function fetchModelCatalog(): Promise<ModelCatalog> {
  return getJson<ModelCatalog>("/v1/model-catalog");
}
