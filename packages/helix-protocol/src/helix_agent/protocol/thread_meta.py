"""thread_meta row shape — vendor-aligned (see 06-OPEN-SOURCE-DEPS §P0)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ThreadStatus(StrEnum):
    """LangGraph thread lifecycle."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThreadMeta(BaseModel):
    """One row of ``thread_meta`` — keyed by LangGraph thread_id; multiple
    runs / sessions can share the same thread.

    DeerFlow vendor pattern, extended with ``tenant_id`` per ADR-0002.
    """

    model_config = ConfigDict(frozen=True)

    thread_id: UUID
    tenant_id: UUID
    created_by: str = Field(description="actor_id of session creator (user / sa)")
    status: ThreadStatus = ThreadStatus.ACTIVE
    agent_name: str | None = Field(default=None, description="manifest name")
    agent_version: str | None = Field(default=None, description="manifest version (semver)")
    created_at: datetime | None = None
    updated_at: datetime | None = None
