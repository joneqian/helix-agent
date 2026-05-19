"""``user_workspace`` ORM model — Stream J.15 per-user execution environment.

One row per ``(tenant_id, user_id)`` pair, registering the docker named
volume that backs that user's persistent workspace. The volume outlives
the ephemeral sandbox containers that mount it; see migration
``0018_user_workspace`` and STREAM-J-DESIGN § 9.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from helix_agent.persistence.base import Base


class UserWorkspaceRow(Base):
    """A user's persistent workspace volume (Stream J.15).

    Supervisor-owned, like ``sandbox_instance`` — no RLS. The
    sandbox-supervisor authenticates callers via mTLS and scopes by
    ``(tenant_id, user_id)`` in the application layer (Mini-ADR J-1).
    """

    __tablename__ = "user_workspace"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    #: docker named volume — deterministic per (tenant, user), see ``workspace.base``.
    volume_name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="user_workspace_identity_uniq"),
    )
