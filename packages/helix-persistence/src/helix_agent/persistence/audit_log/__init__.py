"""Audit log repository — append-only operational audit (subsystems/17).

The Repository pattern mirrors ``thread_meta``: an abstract
:class:`AuditLogStore` with in-memory + Postgres implementations. The
higher-level ``AuditLogger`` service that adds PII redaction, fallback
queue, and self-audit on read is Stream A.4 batch 2.
"""

from helix_agent.persistence.audit_log.base import AuditLogStore as AuditLogStore
from helix_agent.persistence.audit_log.cursor import decode_cursor as decode_cursor
from helix_agent.persistence.audit_log.cursor import encode_cursor as encode_cursor
from helix_agent.persistence.audit_log.memory import (
    InMemoryAuditLogStore as InMemoryAuditLogStore,
)
from helix_agent.persistence.audit_log.sql import SqlAuditLogStore as SqlAuditLogStore

__all__ = [
    "AuditLogStore",
    "InMemoryAuditLogStore",
    "SqlAuditLogStore",
    "decode_cursor",
    "encode_cursor",
]
