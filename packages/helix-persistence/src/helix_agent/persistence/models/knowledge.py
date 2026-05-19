"""``knowledge_*`` ORM models — Stream J.5 RAG.

A tenant's ``knowledge_base`` owns ``knowledge_document`` rows (uploaded
source files); each document owns ``knowledge_chunk`` rows (embedded
slices). All three are tenant-scoped only — RLS (migration ``0021``)
enforces ``app.tenant_id``. There are no foreign keys between the tables
(a FK into a ``FORCE`` RLS table is a footgun, Mini-ADR J-1a); the
``KnowledgeStore`` cascades deletes in the application layer.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from helix_agent.persistence.base import Base
from helix_agent.persistence.embedding import EMBEDDING_DIM
from helix_agent.protocol import DEFAULT_CHUNK_MAX_TOKENS, DEFAULT_CHUNK_OVERLAP_TOKENS


class KnowledgeBaseRow(Base):
    """One ``knowledge_base`` — a named, tenant-scoped document collection."""

    __tablename__ = "knowledge_base"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_CHUNK_MAX_TOKENS))
    )
    chunk_overlap_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_CHUNK_OVERLAP_TOKENS))
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="knowledge_base_identity_uniq"),)


class KnowledgeDocumentRow(Base):
    """One ``knowledge_document`` — an ingested source file.

    ``(tenant_id, kb_id, filename)`` is unique — re-uploading the same
    filename updates the document in place.
    """

    __tablename__ = "knowledge_document"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    kb_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "kb_id", "filename", name="knowledge_document_identity_uniq"),
    )


class KnowledgeChunkRow(Base):
    """One ``knowledge_chunk`` — an embedded slice of a document."""

    __tablename__ = "knowledge_chunk"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    kb_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    #: Full-text vector for the keyword side of hybrid search — populated
    #: by the store from jieba-segmented ``content`` (Stream J.5).
    content_tsv: Mapped[str | None] = mapped_column(TSVECTOR(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("knowledge_chunk_kb_idx", "tenant_id", "kb_id"),
        Index("knowledge_chunk_document_idx", "document_id"),
        Index("knowledge_chunk_tsv_idx", "content_tsv", postgresql_using="gin"),
    )
