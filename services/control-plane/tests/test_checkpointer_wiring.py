"""Tests for the E.1 checkpointer wiring — settings + lifespan swap.

The Postgres checkpointer itself is integration-tested by
``test_checkpointer_factory.py`` in helix-runtime. Here we cover the
control-plane wiring: settings defaults, the ``make_agent_builder``
seam, and the lifespan branch that swaps in the durable checkpointer.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from control_plane.app import create_app
from control_plane.runtime import AgentRuntime, make_agent_builder, make_agent_runtime
from control_plane.settings import Settings
from helix_agent.runtime.secret_store import LocalDevSecretStore
from tests.auth_fixtures import build_test_jwt_verifier


def _secret_store() -> LocalDevSecretStore:
    return LocalDevSecretStore.from_mapping({})


def test_checkpointer_settings_default_to_memory() -> None:
    settings = Settings()
    assert settings.checkpointer_backend == "memory"
    assert settings.checkpointer_dsn is None


def test_make_agent_builder_returns_distinct_callables() -> None:
    store = _secret_store()
    a = make_agent_builder(store, InMemorySaver())
    b = make_agent_builder(store, InMemorySaver())
    assert callable(a)
    assert callable(b)
    assert a is not b


def test_make_agent_runtime_builds_runtime() -> None:
    runtime = make_agent_runtime(_secret_store())
    assert isinstance(runtime, AgentRuntime)
    assert callable(runtime.agent_builder)


@pytest.mark.asyncio
async def test_lifespan_postgres_without_dsn_raises() -> None:
    """``checkpointer_backend='postgres'`` with no DSN fails fast at boot."""
    settings = Settings(checkpointer_backend="postgres", checkpointer_dsn=None)
    app = create_app(
        settings=settings,
        jwt_verifier=build_test_jwt_verifier(),
        enable_reaper=False,
    )
    with pytest.raises(RuntimeError, match="checkpointer_dsn"):
        async with app.router.lifespan_context(app):
            pass  # pragma: no cover - lifespan raises before yield


@pytest.mark.asyncio
async def test_lifespan_memory_backend_leaves_builder_untouched() -> None:
    """The memory backend takes the no-swap path through lifespan."""
    settings = Settings(checkpointer_backend="memory")
    app = create_app(
        settings=settings,
        jwt_verifier=build_test_jwt_verifier(),
        enable_reaper=False,
    )
    builder_before = app.state.agent_runtime.agent_builder
    async with app.router.lifespan_context(app):
        assert app.state.agent_runtime.agent_builder is builder_before
