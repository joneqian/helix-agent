/**
 * Platform Judge-model config SDK — backed by /v1/platform/judge-config
 * (Stream PI-3-A3). system_admin-only, platform-level. The judge model is used
 * by the PI-2b output judge + PI-3b action judge; unset → each agent's own model.
 */
import { getJson, putJson } from "./client";

export interface ProviderModel {
  provider: string;
  model: string;
}

export interface PlatformJudgeConfigView {
  judge: ProviderModel | null;
  available: ProviderModel[];
}

export interface PlatformJudgeConfigWrite {
  judge_provider?: string | null;
  judge_model?: string | null;
}

export async function getPlatformJudgeConfig(): Promise<PlatformJudgeConfigView> {
  return getJson<PlatformJudgeConfigView>("/v1/platform/judge-config");
}

export async function putPlatformJudgeConfig(
  body: PlatformJudgeConfigWrite,
): Promise<{ judge: ProviderModel | null }> {
  return putJson("/v1/platform/judge-config", body);
}
