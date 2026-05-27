"""In-memory ``MemoryStore`` for unit tests."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from helix_agent.common.threat_patterns import ThreatFinding, scan_for_threats
from helix_agent.persistence.memory.base import MemoryInjectionBlockedError, MemoryStore
from helix_agent.persistence.memory.hash import hash_content
from helix_agent.protocol import MemoryItem


def _with_drift_flag(item: MemoryItem) -> MemoryItem:
    """Capability Uplift Sprint #2 (Mini-ADR U-4) — recompute the
    K.K7 content hash and stamp ``drift=True`` when it diverges from
    the stored ``content_hash``. The original content is preserved;
    the recall node redacts based on the flag."""
    stored = item.content_hash
    if stored is None:
        return item
    if hash_content(item.content) == stored:
        return item
    return item.model_copy(update={"drift": True})


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine distance (0 = identical) — mirrors pgvector's ``<=>``."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


class InMemoryMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._rows: list[MemoryItem] = []

    async def write(self, items: Sequence[MemoryItem]) -> None:
        # Capability Uplift Sprint #2 (Mini-ADR U-3) — atomic strict scan.
        blocked: list[tuple[object, list[ThreatFinding]]] = []
        for item in items:
            findings = scan_for_threats(item.content, scope="strict")
            if findings:
                blocked.append((item.id, findings))
        if blocked:
            raise MemoryInjectionBlockedError(blocked)  # type: ignore[arg-type]
        for item in items:
            # Stream K.K7 — fill content_hash if the caller didn't, and
            # skip the row when an identical live entry already exists
            # for the same ``(tenant, user, content_hash)`` (mirrors the
            # SQL ON CONFLICT DO NOTHING path).
            content_hash = item.content_hash or hash_content(item.content)
            if any(
                r.tenant_id == item.tenant_id
                and r.user_id == item.user_id
                and r.deleted_at is None
                and (r.content_hash or hash_content(r.content)) == content_hash
                for r in self._rows
            ):
                continue
            self._rows.append(item.model_copy(update={"content_hash": content_hash}))

    async def retrieve(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        query_embedding: Sequence[float],
        kind: Literal["fact", "episodic"] | None = None,
        limit: int = 5,
    ) -> list[MemoryItem]:
        candidates = [
            row
            for row in self._rows
            if row.tenant_id == tenant_id
            and row.user_id == user_id
            and row.deleted_at is None  # Stream K.K6 — hide soft-deleted
            and (kind is None or row.kind == kind)
        ]
        candidates.sort(key=lambda row: _cosine_distance(query_embedding, row.embedding))
        return [_with_drift_flag(row) for row in candidates[:limit]]

    async def list_for_user(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        kind: Literal["fact", "episodic"] | None = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        candidates = [
            row
            for row in self._rows
            if row.tenant_id == tenant_id
            and row.user_id == user_id
            and row.deleted_at is None
            and (kind is None or row.kind == kind)
        ]
        # newest-first matches the partial index ordering in migration 0024.
        candidates.sort(
            key=lambda row: row.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return candidates[:limit]

    async def list_all_tenants(
        self,
        *,
        kind: Literal["fact", "episodic"] | None = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        candidates = [
            row
            for row in self._rows
            if row.deleted_at is None and (kind is None or row.kind == kind)
        ]
        candidates.sort(
            key=lambda row: row.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return candidates[:limit]

    async def update_content(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        memory_id: UUID,
        content: str,
        embedding: Sequence[float],
        kind: Literal["fact", "episodic"] | None = None,
    ) -> MemoryItem | None:
        for idx, row in enumerate(self._rows):
            if (
                row.id == memory_id
                and row.tenant_id == tenant_id
                and row.user_id == user_id
                and row.deleted_at is None
            ):
                updated = row.model_copy(
                    update={
                        "content": content,
                        # K.K7 — keep dedup hash in sync with content
                        "content_hash": hash_content(content),
                        "embedding": tuple(float(v) for v in embedding),
                        "kind": kind if kind is not None else row.kind,
                    }
                )
                self._rows[idx] = updated
                return updated
        return None

    async def soft_delete(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        memory_id: UUID,
    ) -> bool:
        for idx, row in enumerate(self._rows):
            if row.id == memory_id and row.tenant_id == tenant_id and row.user_id == user_id:
                if row.deleted_at is not None:
                    return True  # idempotent
                self._rows[idx] = row.model_copy(update={"deleted_at": datetime.now(UTC)})
                return True
        return False
