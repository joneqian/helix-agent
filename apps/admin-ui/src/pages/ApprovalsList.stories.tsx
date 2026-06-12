import type { ComponentType } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";

import { ApprovalsList } from "./ApprovalsList";
import { apiClient } from "../api/client";
import "../i18n";

const THREAD = "33333333-3333-3333-3333-333333333333";

function approvalItem(runId: string, minutesAgo: number, summary: string, reason: string) {
  return {
    id: crypto.randomUUID(),
    tenant_id: "22222222-2222-2222-2222-222222222222",
    user_id: null,
    run_id: runId,
    thread_id: THREAD,
    request_id: `approval:${runId}`,
    node: "tools",
    reason_kind: reason,
    action_summary: summary,
    proposed_args: { to: "ops@example.com" },
    requested_at: new Date(Date.now() - minutesAgo * 60_000).toISOString(),
    timeout_at: new Date(Date.now() + 60 * 60_000).toISOString(),
    status: "pending",
    decided_by: null,
    decided_at: null,
  };
}

/** Stub the axios layer: the list resolves three pending rows; a
 *  ``:decide`` POST resolves all-ok so the inline buttons exercise the
 *  full happy path in the story. */
function withStubs(Story: ComponentType) {
  apiClient.defaults.adapter = (config) => {
    const respond = (data: unknown) =>
      Promise.resolve({
        data: { success: true, data, error: null },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    if ((config.url ?? "").includes(":decide")) {
      const body = JSON.parse(String(config.data ?? "{}")) as {
        decisions: { run_id: string }[];
      };
      return respond({
        results: body.decisions.map((d) => ({
          run_id: d.run_id,
          ok: true,
          continuation_run_id: crypto.randomUUID(),
        })),
        succeeded: body.decisions.length,
      });
    }
    return respond({
      items: [
        approvalItem("11111111-aaaa-aaaa-aaaa-111111111111", 130, "send_email to ops@example.com", "policy_gate"),
        approvalItem("22222222-bbbb-bbbb-bbbb-222222222222", 45, "delete 12 stale artifacts", "risk_confirmation"),
        approvalItem("33333333-cccc-cccc-cccc-333333333333", 5, "choose migration strategy B", "approach_choice"),
      ],
      total: 3,
      limit: 100,
      offset: 0,
    });
  };
  return (
    <MemoryRouter>
      <Story />
    </MemoryRouter>
  );
}

const meta: Meta<typeof ApprovalsList> = {
  title: "Pages/ApprovalsList",
  component: ApprovalsList,
  decorators: [withStubs],
};
export default meta;

type Story = StoryObj<typeof ApprovalsList>;

export const PendingQueue: Story = {};
