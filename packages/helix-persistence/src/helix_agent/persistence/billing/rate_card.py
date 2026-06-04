"""Platform model rate-card store — Stream Y (Mini-ADR Y-3).

CRUD + temporal/most-specific resolution over the platform-curated model rate
card. Every row is platform-global (``tenant_id`` is NULL), so SQL callers MUST
be inside ``bypass_rls_session()`` — there is no per-tenant RLS scope to satisfy,
exactly like :class:`SqlMcpConnectorCatalogStore` / :class:`SqlPlatformSecretStore`.
The store layer itself is transparent: it does not import bypass; the
control-plane caller applies it.

``resolve`` is pure selection logic (most-specific tier + temporal window) and
is unit-tested directly.
"""

from __future__ import annotations

import abc
import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from helix_agent.persistence.models import ModelRateCardRow
from helix_agent.protocol import (
    ModelRateCardPatch,
    ModelRateCardRecord,
    ModelRateCardUpsert,
    TenantPlan,
)


class ModelRateCardConflictError(Exception):
    """A platform rate-card row already exists for the natural key.

    Natural key: ``(provider, model, plan_tier, effective_from)`` among platform
    (NULL-tenant) rows. Surfaced as a 409 by the control-plane POST handler.
    """

    def __init__(
        self, *, provider: str, model: str, plan_tier: TenantPlan | None, effective_from: datetime
    ) -> None:
        super().__init__(
            f"model_rate_card already exists: provider={provider!r} model={model!r} "
            f"plan_tier={plan_tier} effective_from={effective_from.isoformat()}"
        )
        self.provider = provider
        self.model = model
        self.plan_tier = plan_tier
        self.effective_from = effective_from


class ModelRateCardNotFoundError(Exception):
    """No ``model_rate_card`` row for the requested id."""

    def __init__(self, *, rate_card_id: UUID) -> None:
        super().__init__(f"model_rate_card not found: id={rate_card_id}")
        self.rate_card_id = rate_card_id


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _resolve(
    rows: list[ModelRateCardRecord],
    *,
    provider: str,
    model: str,
    plan_tier: TenantPlan | None,
    at: datetime,
) -> ModelRateCardRecord | None:
    """Pure most-specific + temporal selection over candidate rows.

    Selection rules (see STREAM-Y-DESIGN § Y-3):

    * Only rows for the given ``(provider, model)`` whose temporal window
      ``[effective_from, effective_until)`` contains ``at`` (open-ended when
      ``effective_until is None``) are eligible.
    * A row matching the given ``plan_tier`` beats a generic
      (``plan_tier is None``) row.
    * Among rows of equal specificity, the latest ``effective_from`` wins.
    """

    def _in_window(r: ModelRateCardRecord) -> bool:
        if at < r.effective_from:
            return False
        return r.effective_until is None or at < r.effective_until

    eligible = [r for r in rows if r.provider == provider and r.model == model and _in_window(r)]
    # Prefer tier-specific rows; fall back to generic (plan_tier is None) only
    # when no tier-specific row matches.
    tier_specific = [r for r in eligible if r.plan_tier == plan_tier]
    generic = [r for r in eligible if r.plan_tier is None]
    pool = tier_specific or generic
    if not pool:
        return None
    return max(pool, key=lambda r: r.effective_from)


class ModelRateCardStore(abc.ABC):
    """CRUD + resolution for the platform-curated model rate card.

    Platform table: every row is NULL-tenant, so SQL callers MUST drive these
    methods inside ``bypass_rls_session()``.
    """

    @abc.abstractmethod
    async def create(self, *, upsert: ModelRateCardUpsert, actor_id: str) -> ModelRateCardRecord:
        """Insert a new platform (NULL-tenant) rate-card row. Raises
        :class:`ModelRateCardConflictError` on a duplicate natural key."""

    @abc.abstractmethod
    async def get(self, rate_card_id: UUID) -> ModelRateCardRecord | None:
        """Return the row, or None if absent."""

    @abc.abstractmethod
    async def list(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        include_expired: bool = False,
    ) -> list[ModelRateCardRecord]:
        """Return rows ordered by ``(provider, model, effective_from desc)``.

        ``include_expired=False`` (the default) drops rows whose
        ``effective_until`` is in the past relative to now.
        """

    @abc.abstractmethod
    async def patch(self, *, rate_card_id: UUID, patch: ModelRateCardPatch) -> ModelRateCardRecord:
        """Apply a partial update. Raises
        :class:`ModelRateCardNotFoundError` if absent."""

    @abc.abstractmethod
    async def delete(self, rate_card_id: UUID) -> None:
        """Delete the row. Raises
        :class:`ModelRateCardNotFoundError` if absent."""

    @abc.abstractmethod
    async def resolve(
        self,
        *,
        provider: str,
        model: str,
        plan_tier: TenantPlan | None,
        at: datetime,
    ) -> ModelRateCardRecord | None:
        """Resolve the most-specific in-effect rate for ``(provider, model)`` at
        ``at``. Tier-specific beats generic; latest ``effective_from`` wins."""


class InMemoryModelRateCardStore(ModelRateCardStore):
    """Dict-backed rate-card store keyed by ``id``; lock-guarded."""

    def __init__(self) -> None:
        self._rows: dict[UUID, ModelRateCardRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, *, upsert: ModelRateCardUpsert, actor_id: str) -> ModelRateCardRecord:
        async with self._lock:
            if any(
                r.provider == upsert.provider
                and r.model == upsert.model
                and r.plan_tier == upsert.plan_tier
                and r.effective_from == upsert.effective_from
                for r in self._rows.values()
            ):
                raise ModelRateCardConflictError(
                    provider=upsert.provider,
                    model=upsert.model,
                    plan_tier=upsert.plan_tier,
                    effective_from=upsert.effective_from,
                )
            now = _utc_now()
            record = ModelRateCardRecord(
                id=uuid4(),
                tenant_id=None,
                provider=upsert.provider,
                model=upsert.model,
                input_token_micros=upsert.input_token_micros,
                output_token_micros=upsert.output_token_micros,
                cache_creation_token_micros=upsert.cache_creation_token_micros,
                cache_read_token_micros=upsert.cache_read_token_micros,
                markup_bps=upsert.markup_bps,
                plan_tier=upsert.plan_tier,
                effective_from=upsert.effective_from,
                effective_until=upsert.effective_until,
                created_at=now,
                updated_at=now,
            )
            self._rows[record.id] = record
            return record

    async def get(self, rate_card_id: UUID) -> ModelRateCardRecord | None:
        async with self._lock:
            return self._rows.get(rate_card_id)

    async def list(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        include_expired: bool = False,
    ) -> list[ModelRateCardRecord]:
        now = _utc_now()
        async with self._lock:
            rows = [
                r
                for r in self._rows.values()
                if (provider is None or r.provider == provider)
                and (model is None or r.model == model)
                and (include_expired or r.effective_until is None or r.effective_until > now)
            ]
        # (provider, model) ascending, effective_from DESCENDING (newest first)
        # — matches the base docstring + the SQL store. Stable two-pass sort.
        rows.sort(key=lambda r: r.effective_from, reverse=True)
        rows.sort(key=lambda r: (r.provider, r.model))
        return rows

    async def patch(self, *, rate_card_id: UUID, patch: ModelRateCardPatch) -> ModelRateCardRecord:
        async with self._lock:
            existing = self._rows.get(rate_card_id)
            if existing is None:
                raise ModelRateCardNotFoundError(rate_card_id=rate_card_id)
            # patch field == None means "leave unchanged"; provider/model/
            # plan_tier/effective_from are immutable post-create (reprice by
            # inserting a new row). effective_until is the exception: a sentinel
            # would be needed to distinguish "leave" from "set open-ended", so we
            # follow the protocol patch shape and treat None as "leave unchanged".
            changes: dict[str, object] = {"updated_at": _utc_now()}
            if patch.input_token_micros is not None:
                changes["input_token_micros"] = patch.input_token_micros
            if patch.output_token_micros is not None:
                changes["output_token_micros"] = patch.output_token_micros
            if patch.cache_creation_token_micros is not None:
                changes["cache_creation_token_micros"] = patch.cache_creation_token_micros
            if patch.cache_read_token_micros is not None:
                changes["cache_read_token_micros"] = patch.cache_read_token_micros
            if patch.markup_bps is not None:
                changes["markup_bps"] = patch.markup_bps
            if patch.effective_until is not None:
                changes["effective_until"] = patch.effective_until
            # Re-validate the merged row (model_copy doesn't run validators) so a
            # patch can't slip a cross-field-invalid record (parity with SQL).
            updated = ModelRateCardRecord.model_validate(
                existing.model_copy(update=changes).model_dump()
            )
            self._rows[rate_card_id] = updated
            return updated

    async def delete(self, rate_card_id: UUID) -> None:
        async with self._lock:
            if rate_card_id not in self._rows:
                raise ModelRateCardNotFoundError(rate_card_id=rate_card_id)
            del self._rows[rate_card_id]

    async def resolve(
        self,
        *,
        provider: str,
        model: str,
        plan_tier: TenantPlan | None,
        at: datetime,
    ) -> ModelRateCardRecord | None:
        async with self._lock:
            rows = list(self._rows.values())
        return _resolve(rows, provider=provider, model=model, plan_tier=plan_tier, at=at)


def _row_to_record(row: ModelRateCardRow) -> ModelRateCardRecord:
    return ModelRateCardRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        provider=row.provider,
        model=row.model,
        input_token_micros=row.input_token_micros,
        output_token_micros=row.output_token_micros,
        cache_creation_token_micros=row.cache_creation_token_micros,
        cache_read_token_micros=row.cache_read_token_micros,
        markup_bps=row.markup_bps,
        plan_tier=TenantPlan(row.plan_tier) if row.plan_tier is not None else None,
        effective_from=row.effective_from,
        effective_until=row.effective_until,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class DbModelRateCardStore(ModelRateCardStore):
    """Postgres-backed platform model rate card (bypass-RLS sessions)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, *, upsert: ModelRateCardUpsert, actor_id: str) -> ModelRateCardRecord:
        now = _utc_now()
        stmt = (
            pg_insert(ModelRateCardRow)
            .values(
                tenant_id=None,
                provider=upsert.provider,
                model=upsert.model,
                input_token_micros=upsert.input_token_micros,
                output_token_micros=upsert.output_token_micros,
                cache_creation_token_micros=upsert.cache_creation_token_micros,
                cache_read_token_micros=upsert.cache_read_token_micros,
                markup_bps=upsert.markup_bps,
                plan_tier=upsert.plan_tier.value if upsert.plan_tier is not None else None,
                effective_from=upsert.effective_from,
                effective_until=upsert.effective_until,
                created_at=now,
                updated_at=now,
            )
            .returning(ModelRateCardRow)
        )
        async with self._sf() as session:
            try:
                row = (await session.execute(stmt)).scalar_one()
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ModelRateCardConflictError(
                    provider=upsert.provider,
                    model=upsert.model,
                    plan_tier=upsert.plan_tier,
                    effective_from=upsert.effective_from,
                ) from exc
            await session.refresh(row)
            return _row_to_record(row)

    async def get(self, rate_card_id: UUID) -> ModelRateCardRecord | None:
        async with self._sf() as session:
            row = await session.get(ModelRateCardRow, rate_card_id)
        return _row_to_record(row) if row is not None else None

    async def list(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        include_expired: bool = False,
    ) -> list[ModelRateCardRecord]:
        stmt = select(ModelRateCardRow).order_by(
            ModelRateCardRow.provider,
            ModelRateCardRow.model,
            ModelRateCardRow.effective_from.desc(),
        )
        if provider is not None:
            stmt = stmt.where(ModelRateCardRow.provider == provider)
        if model is not None:
            stmt = stmt.where(ModelRateCardRow.model == model)
        if not include_expired:
            stmt = stmt.where(
                (ModelRateCardRow.effective_until.is_(None))
                | (ModelRateCardRow.effective_until > _utc_now())
            )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [_row_to_record(r) for r in rows]

    async def patch(self, *, rate_card_id: UUID, patch: ModelRateCardPatch) -> ModelRateCardRecord:
        async with self._sf() as session:
            existing = await session.get(ModelRateCardRow, rate_card_id)
            if existing is None:
                raise ModelRateCardNotFoundError(rate_card_id=rate_card_id)
            if patch.input_token_micros is not None:
                existing.input_token_micros = patch.input_token_micros
            if patch.output_token_micros is not None:
                existing.output_token_micros = patch.output_token_micros
            if patch.cache_creation_token_micros is not None:
                existing.cache_creation_token_micros = patch.cache_creation_token_micros
            if patch.cache_read_token_micros is not None:
                existing.cache_read_token_micros = patch.cache_read_token_micros
            if patch.markup_bps is not None:
                existing.markup_bps = patch.markup_bps
            if patch.effective_until is not None:
                existing.effective_until = patch.effective_until
            existing.updated_at = _utc_now()
            # Validate the prospective record BEFORE commit: if the merged row
            # violates a cross-field invariant, _row_to_record raises and the
            # context manager rolls back — no corrupt row is persisted.
            record = _row_to_record(existing)
            await session.commit()
            return record

    async def delete(self, rate_card_id: UUID) -> None:
        stmt = (
            sa_delete(ModelRateCardRow)
            .where(ModelRateCardRow.id == rate_card_id)
            .returning(ModelRateCardRow.id)
        )
        async with self._sf() as session:
            deleted = (await session.execute(stmt)).scalar_one_or_none()
            if deleted is None:
                await session.rollback()
                raise ModelRateCardNotFoundError(rate_card_id=rate_card_id)
            await session.commit()

    async def resolve(
        self,
        *,
        provider: str,
        model: str,
        plan_tier: TenantPlan | None,
        at: datetime,
    ) -> ModelRateCardRecord | None:
        stmt = select(ModelRateCardRow).where(
            ModelRateCardRow.provider == provider,
            ModelRateCardRow.model == model,
        )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        records = [_row_to_record(r) for r in rows]
        return _resolve(records, provider=provider, model=model, plan_tier=plan_tier, at=at)
