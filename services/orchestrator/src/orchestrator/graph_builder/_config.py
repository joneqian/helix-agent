"""Helpers to lift per-run objects out of ``RunnableConfig``.

Shared by the graph nodes (``builder``, ``planner``) — kept in its own
module so neither node module has to import the other (no import cycle).
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.runnables import RunnableConfig

from helix_agent.runtime.audit.logger import AuditLogger
from helix_agent.runtime.cancellation import CANCELLATION_TOKEN_KEY, CancellationToken

#: Stream TE-2 — key under which the run's :class:`AuditLogger` travels in
#: ``config["configurable"]`` (a live object, like the cancellation token —
#: not checkpoint-serialisable, injected per-invocation by ``sse.run_agent``).
AUDIT_LOGGER_KEY = "audit_logger"


def configurable_uuid(config: RunnableConfig, key: str) -> UUID | None:
    """Parse ``config['configurable'][key]`` as a UUID, or ``None``.

    Run-scoped bindings (``tenant_id`` / ``user_id`` / …) travel via
    ``config['configurable']`` as strings; nodes lift them with this.
    """
    raw = (config.get("configurable") or {}).get(key)
    if isinstance(raw, UUID):
        return raw
    if isinstance(raw, str):
        try:
            return UUID(raw)
        except ValueError:
            return None
    return None


def current_run_id(config: RunnableConfig) -> str | None:
    """The run's id from ``config['configurable']``.

    Distinguishes one graph invocation from the next on the same
    checkpointed thread — used to scope per-run counters whose channels
    would otherwise accumulate across runs (e.g. the reflect budget).
    """
    raw = (config.get("configurable") or {}).get("run_id")
    return str(raw) if raw is not None else None


def cancellation_token(config: RunnableConfig) -> CancellationToken:
    """Lift the run's :class:`CancellationToken` out of ``config``.

    The token travels via ``config["configurable"]`` (not ``AgentState``
    — a live :class:`asyncio.Event` is not checkpoint-serialisable).
    When absent — dev / unit-test path that never cancels — a fresh,
    never-cancelled token is returned so node code is uniform.
    """
    configurable = config.get("configurable") or {}
    token = configurable.get(CANCELLATION_TOKEN_KEY)
    if isinstance(token, CancellationToken):
        return token
    return CancellationToken()


def audit_logger_from_config(config: RunnableConfig) -> AuditLogger | None:
    """Lift the run's :class:`AuditLogger` out of ``config`` (Stream TE-2).

    Like the cancellation token it travels via ``config["configurable"]``
    (a live object, not checkpoint-serialisable). ``None`` when absent —
    the dev / unit-test path, or a control-plane that wires no audit sink;
    callers must treat the tool-call audit emit as best-effort.
    """
    configurable = config.get("configurable") or {}
    logger = configurable.get(AUDIT_LOGGER_KEY)
    if isinstance(logger, AuditLogger):
        return logger
    return None
