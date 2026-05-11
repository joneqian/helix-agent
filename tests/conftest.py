"""Pytest top-level configuration and shared fixtures.

Fixtures registered here are available to every test under `tests/` plus
each package/service test directory.

Per-Stream additions:
- Stream A.1 will add real Postgres migrations via `tmp_postgres_dsn`
- Stream E.1 will add VCR-recorded Anthropic cassettes via `vcrpy`
  (cassettes live under `tests/cassettes/<test_id>.yaml`)
- ADR-0007: `mock_secret_store` implements the SecretStore protocol
  to be added by Stream A.x
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from testcontainers.postgres import PostgresContainer


# ---------------------------------------------------------------------------
# Mock LLM — deterministic stub for unit tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeCompletion:
    """Pretend LLM response. Add fields as production LLM contract grows."""

    content: str
    tokens_used: int = 0
    cached: bool = False


@dataclass
class MockLLM:
    """Deterministic LLM stub.

    Default behavior: any prompt returns `FakeCompletion(content="ok")`.
    Configure overrides via `.expect(prompt_prefix, response)`.
    All prompts are recorded in `.calls` for assertion.
    """

    default: FakeCompletion = field(default_factory=lambda: FakeCompletion(content="ok"))
    expectations: list[tuple[str, FakeCompletion]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def expect(self, prompt_prefix: str, response: FakeCompletion) -> None:
        """Register a response for prompts starting with `prompt_prefix`."""
        self.expectations.append((prompt_prefix, response))

    async def complete(self, prompt: str) -> FakeCompletion:
        """Return the first matching expectation, or the default."""
        self.calls.append(prompt)
        for prefix, response in self.expectations:
            if prompt.startswith(prefix):
                return response
        return self.default


@pytest.fixture
def mock_llm() -> MockLLM:
    """Fresh MockLLM per test."""
    return MockLLM()


# ---------------------------------------------------------------------------
# Mock SecretStore — in-memory impl, drop-in for ADR-0007 SecretStore protocol
# ---------------------------------------------------------------------------


@dataclass
class InMemorySecretStore:
    """Dict-backed SecretStore for tests.

    When `helix_agent.runtime.secrets.SecretStore` Protocol lands in
    Stream A.x (per ADR-0007), this class will explicitly implement it.
    """

    _store: dict[str, str] = field(default_factory=dict)

    async def get(self, name: str, *, version: str | None = None) -> str:
        del version  # not modelled in in-memory store
        if name not in self._store:
            raise KeyError(f"secret not found: {name}")
        return self._store[name]

    async def put(self, name: str, value: str) -> None:
        self._store[name] = value


@pytest.fixture
def mock_secret_store() -> InMemorySecretStore:
    """Fresh InMemorySecretStore per test."""
    return InMemorySecretStore()


# ---------------------------------------------------------------------------
# Postgres container — session-scoped, used by integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Session-scoped Postgres 16 container via testcontainers.

    Heavy — adds ~10s session startup. Stream A.1 will be the first
    consumer (event_log / audit_log migrations).

    Requires Docker daemon available; tests using this fixture should
    be marked `@pytest.mark.integration`.
    """
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine")
    with container:
        yield container


@pytest.fixture
def tmp_postgres_dsn(postgres_container: PostgresContainer) -> str:
    """SQLAlchemy-compatible DSN for the session Postgres container.

    Tests should manage their own schema cleanup (recommend: pytest
    transaction rollback fixture; Stream A.1 lands the helper).
    """
    return postgres_container.get_connection_url()
