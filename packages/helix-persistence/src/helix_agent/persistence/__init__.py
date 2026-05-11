"""Helix-Agent persistence — SQLAlchemy 2.0 async ORM + Alembic migrations."""

# Explicit `as` re-exports signal intentional public API to static analyzers
# (mypy --strict, CodeQL py/unused-import).
from helix_agent.persistence.base import Base as Base
from helix_agent.persistence.database import DatabaseConfig as DatabaseConfig
from helix_agent.persistence.database import (
    create_async_engine_from_config as create_async_engine_from_config,
)
from helix_agent.persistence.database import (
    create_async_session_factory as create_async_session_factory,
)
from helix_agent.persistence.models import AuditLogRow as AuditLogRow
from helix_agent.persistence.models import EventLogRow as EventLogRow
from helix_agent.persistence.models import ThreadMetaRow as ThreadMetaRow
from helix_agent.persistence.thread_meta import (
    InMemoryThreadMetaStore as InMemoryThreadMetaStore,
)
from helix_agent.persistence.thread_meta import (
    SqlThreadMetaStore as SqlThreadMetaStore,
)
from helix_agent.persistence.thread_meta import ThreadMetaStore as ThreadMetaStore

__all__ = [
    "AuditLogRow",
    "Base",
    "DatabaseConfig",
    "EventLogRow",
    "InMemoryThreadMetaStore",
    "SqlThreadMetaStore",
    "ThreadMetaRow",
    "ThreadMetaStore",
    "create_async_engine_from_config",
    "create_async_session_factory",
]
