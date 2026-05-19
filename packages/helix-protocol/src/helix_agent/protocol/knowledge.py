"""Knowledge base / RAG — Stream J.5.

A tenant uploads documents into named knowledge bases; each document is
parsed, chunked, and embedded into ``knowledge_chunk`` rows for vector
retrieval. An agent's ``knowledge:`` manifest block binds it to a subset
of the tenant's bases, which its ``knowledge_search`` tool queries.

All three records are scoped to ``tenant_id`` only — knowledge bases are
tenant-shared, not per-user (unlike J.3 memory). See
``docs/streams/STREAM-J-DESIGN.md`` § 12.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Default per-base chunking parameters (token-counted). A base may
#: override them at creation to tune chunk granularity to its content.
DEFAULT_CHUNK_MAX_TOKENS: Final = 512
DEFAULT_CHUNK_OVERLAP_TOKENS: Final = 64


class DocumentStatus(StrEnum):
    """``knowledge_document.status`` — one document's ingestion lifecycle."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeBase(BaseModel):
    """One row of ``knowledge_base`` — a named, tenant-scoped document collection.

    ``chunk_max_tokens`` / ``chunk_overlap_tokens`` are this base's
    chunking parameters; the ingestion pipeline slices each document to
    them. Per-base so different bases can tune granularity (Stream J.5).
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    tenant_id: UUID
    name: str = Field(description="logical name, unique per tenant")
    chunk_max_tokens: int = Field(
        default=DEFAULT_CHUNK_MAX_TOKENS, gt=0, description="max tokens per chunk"
    )
    chunk_overlap_tokens: int = Field(
        default=DEFAULT_CHUNK_OVERLAP_TOKENS,
        ge=0,
        description="tokens of overlap between adjacent chunks",
    )
    created_at: datetime | None = None

    @model_validator(mode="after")
    def _check_chunking(self) -> KnowledgeBase:
        if self.chunk_overlap_tokens >= self.chunk_max_tokens:
            msg = "chunk_overlap_tokens must be less than chunk_max_tokens"
            raise ValueError(msg)
        return self


class KnowledgeDocument(BaseModel):
    """One row of ``knowledge_document`` — an ingested source file.

    Re-uploading the same ``filename`` into the same base replaces the
    document's chunks — ``(tenant_id, kb_id, filename)`` is unique.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    tenant_id: UUID
    kb_id: UUID
    filename: str
    status: DocumentStatus
    error: str | None = Field(default=None, description="failure detail when status is FAILED")
    chunk_count: int = Field(default=0, ge=0, description="chunks produced by the latest ingest")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KnowledgeChunk(BaseModel):
    """One row of ``knowledge_chunk`` — an embedded slice of a document."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    tenant_id: UUID
    kb_id: UUID
    document_id: UUID
    chunk_index: int = Field(ge=0, description="0-based position within the source document")
    content: str
    embedding: tuple[float, ...] = Field(
        repr=False, description="semantic embedding vector of ``content``"
    )
    created_at: datetime | None = None
