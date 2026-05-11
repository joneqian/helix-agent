"""Async engine + session factory wiring."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession as _AsyncSession,
)


@dataclass(frozen=True)
class DatabaseConfig:
    """Minimal Postgres connection config.

    Values come from ``environments/{env}.yaml`` (see Stream A.6+).
    Stream A.3 will wrap this in a PgBouncer-aware pool.
    """

    dsn: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout_s: float = 30.0
    echo_sql: bool = False


def create_async_engine_from_config(config: DatabaseConfig) -> AsyncEngine:
    """Build an asyncpg-backed engine.

    DSN must use ``postgresql+asyncpg://`` driver scheme.
    """
    return create_async_engine(
        config.dsn,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout_s,
        echo=config.echo_sql,
        future=True,
    )


def create_async_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[_AsyncSession]:
    """Build an ``AsyncSession`` factory with no autocommit / no autoflush.

    Caller manages transactions explicitly via ``async with session.begin()``.
    """
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
