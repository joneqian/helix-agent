/**
 * Runs SDK — backed by ``/v1/sessions/{thread_id}/runs/*``.
 *
 * Stream H.1b PR 3. Runs are scoped under a thread (session), so every
 * call needs the ``thread_id`` in the URL. There is no cross-thread
 * "list all runs" endpoint yet (Mini-ADR J-41 keeps the per-thread
 * shape); PR 4 wires a control-plane index when it lands.
 *
 * ``GET /v1/sessions/{thread_id}/runs/{run_id}`` is one of the few
 * endpoints that returns the raw payload (no envelope) — see :func:`getRun`.
 */
import { apiClient } from "./client";

export type RunStatus =
  | "queued"
  | "running"
  | "paused"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled"
  | "unknown";

export interface PendingApproval {
  request_id: string;
  node: string;
  reason_kind: string;
  action_summary: string;
  proposed_args: Record<string, unknown>;
  requested_at: string;
  timeout_at: string;
}

export interface RunDetail {
  run_id: string;
  thread_id: string;
  status: RunStatus;
  pending_approval: PendingApproval | null;
}

/** Raw (no envelope) fetch — runs.py historically returns the run
 *  status directly. Keeping this endpoint un-enveloped to match
 *  Mini-ADR J-41; ADR refresh PR would normalise. */
export async function getRun(
  threadId: string,
  runId: string,
): Promise<RunDetail> {
  const response = await apiClient.get<RunDetail>(
    `/v1/sessions/${threadId}/runs/${runId}`,
  );
  return response.data;
}

export interface ResumeRunRequest {
  approved: boolean;
  reason?: string;
  override_args?: Record<string, unknown>;
}

export async function resumeRun(
  threadId: string,
  runId: string,
  body: ResumeRunRequest,
): Promise<RunDetail> {
  const response = await apiClient.post<RunDetail>(
    `/v1/sessions/${threadId}/runs/${runId}/resume`,
    body,
  );
  return response.data;
}
