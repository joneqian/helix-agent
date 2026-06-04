"""``model_rate_card`` ORM model — Stream Y (Mini-ADR Y-3).

Platform-curated model rate card (per-``(provider, model, plan_tier)`` token
prices in integer micro-USD + a basis-point markup, temporally versioned). RLS
(NULL-tenant isolation), CHECK constraints, and the partial unique index are
declared in migration ``0059_model_rate_card``, not here — the model is purely
structural (mirrors ``mcp_connector_catalog``). ``tenant_id`` is NULLABLE:
NULL = platform-global (the only shape today).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from helix_agent.persistence.base import Base


class ModelRateCardRow(Base):
    """One platform-curated rate-card row (a price valid over a time window)."""

    __tablename__ = "model_rate_card"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # NULL = platform-global (the only shape today); kept so future per-tenant
    # private rate cards are a non-migration change.
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_token_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_token_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cache_creation_token_micros: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    cache_read_token_micros: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    markup_bps: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # NULL = generic (applies to any tier); a tier-specific row beats it.
    plan_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
