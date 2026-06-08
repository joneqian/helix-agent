/**
 * Skill-evolution governance smoke — Stream SE (SE-8-5).
 *
 * Mirrors the H.4 governance smoke style: login → navigate → assert the
 * SE-8 governance chrome rendered (kill-switch on /skills; governance / eval /
 * lineage panels on a skill detail) → axe. Per-skill detail responses are
 * stubbed inline (the global ``installControlPlaneStub`` returns empty lists);
 * later ``page.route`` registrations win, so these override the stub.
 */
import { test, expect, expectNoA11yViolations, SAMPLE_JWT } from "./fixtures";

async function login(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/login");
  await page.getByTestId("login-token").fill(SAMPLE_JWT);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/agents$/);
}

const KILL_SWITCH_STATE = {
  global: null,
  tenant: null,
  effective_halted: false,
};

const SKILL = {
  id: "sk-test",
  name: "researcher",
  status: "active",
  latest_version: 1,
  description: "a test skill",
  category: "research",
  pinned: false,
  last_used_at: null,
  state_changed_at: null,
  created_at: "2026-06-08T00:00:00Z",
  updated_at: "2026-06-08T00:00:00Z",
  visibility: "agent_private",
  created_by_agent_name: "assistant",
};

const VERSION = {
  id: "v-1",
  skill_id: "sk-test",
  version: 1,
  prompt_fragment: "do x",
  tool_names: [],
  description: "",
  category: "research",
  required_models: [],
  authored_by: "agent",
  supporting_files: {},
  lazy_load: false,
  high_risk: false,
  evolution_origin: "distilled",
  created_at: "2026-06-08T00:00:00Z",
};

const EVAL = {
  id: "ev-1",
  tenant_id: "t1",
  skill_id: "sk-test",
  skill_version: 1,
  baseline_score: 0.4,
  skill_score: 0.85,
  delta: 0.45,
  n_cases: 12,
  replay_source: "trajectory",
  verdict: "pass",
  high_risk: false,
  evolution_round: 0,
  created_at: "2026-06-08T00:00:00Z",
};

test("/skills renders the kill-switch + passes axe", async ({ page }) => {
  await login(page);
  await page.route("**/v1/skill-evolution/kill-switch", async (route) => {
    await route.fulfill({ json: KILL_SWITCH_STATE });
  });
  await page.goto("/skills");
  await expect(page.getByTestId("skill-kill-switch")).toBeVisible();
  await expect(page.getByTestId("skill-kill-switch-tenant")).toBeVisible();
  await expectNoA11yViolations(page, "/skills");
});

test("skill detail renders governance / eval / lineage panels + passes axe", async ({ page }) => {
  await login(page);
  await page.route("**/v1/skills/sk-test", async (route) => {
    await route.fulfill({ json: SKILL });
  });
  await page.route("**/v1/skills/sk-test/versions", async (route) => {
    await route.fulfill({ json: { items: [VERSION] } });
  });
  await page.route("**/v1/skill-evolution/skills/sk-test/eval-results", async (route) => {
    await route.fulfill({ json: { items: [EVAL] } });
  });
  await page.route("**/v1/skill-evolution/skills/sk-test/lineage", async (route) => {
    await route.fulfill({
      json: { skill: SKILL, forked_from_source: null, versions: [VERSION] },
    });
  });
  await page.route("**/v1/skill-evolution/promote-requests*", async (route) => {
    await route.fulfill({ json: { items: [], next_cursor: null, cross_tenant: false } });
  });

  await page.goto("/skills/sk-test");
  await expect(page.getByTestId("skill-governance-panel")).toBeVisible();
  await expect(page.getByTestId("skill-eval-panel")).toBeVisible();
  await expect(page.getByTestId("skill-lineage-panel")).toBeVisible();
  await expect(page.getByTestId("skill-eval-row-ev-1")).toBeVisible();
  await expectNoA11yViolations(page, "/skills/sk-test");
});
