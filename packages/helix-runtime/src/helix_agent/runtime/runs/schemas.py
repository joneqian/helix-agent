# ============================================================
# Adapted from bytedance/deer-flow @ 813d3c94efa7fdea6aafcb4f459304db91fcaed0
# Source: backend/packages/harness/deerflow/runtime/runs/schemas.py
# License: MIT (see vendor LICENSE)
# Modifications:
#   - Lowercase enum values aligned to ADR-0002 audit_log result words
# Last sync: 2026-05-11
# ============================================================

"""Run lifecycle status + disconnect-mode enums."""

from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    """Lifecycle status of a single run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


class DisconnectMode(StrEnum):
    """Behaviour when the SSE consumer disconnects mid-run."""

    CANCEL = "cancel"  # abort the run
    CONTINUE = "continue"  # keep running; results still go to event_log
