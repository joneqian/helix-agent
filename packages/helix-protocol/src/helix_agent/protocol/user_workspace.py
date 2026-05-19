"""Per-user persistent workspace — Stream J.15.

A :class:`UserWorkspace` is the durable workspace of one
``(tenant_id, user_id)`` pair — a docker named volume that outlives the
ephemeral sandbox containers mounting it. Files an agent writes under
``/workspace`` in one run survive into the next (STREAM-J-DESIGN § 9).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserWorkspace(BaseModel):
    """One row of ``user_workspace`` — a user's persistent volume."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    volume_name: str = Field(
        description="docker named volume identifier — deterministic per (tenant, user)"
    )
    size_bytes: int = Field(
        default=0, ge=0, description="last measured volume size; 0 until first measurement"
    )
    created_at: datetime | None = None
    last_accessed_at: datetime | None = None
