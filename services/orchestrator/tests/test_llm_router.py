"""Unit tests for :class:`LLMRouter` (Stream E.11).

Covers test matrix #20 (primary fail → fallback success), #21 (4xx no
fallback), #22 (all exhausted) from STREAM-E-DESIGN § 5.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from helix_agent.runtime.middleware import (
    CircuitOpenError,
    LLMClientError,
    LLMNetworkError,
    LLMRateLimitError,
    LLMServerError,
)
from orchestrator.llm import (
    AllProvidersExhaustedError,
    LLMProvider,
    LLMRouter,
    ProviderHandle,
)
from orchestrator.tools.registry import ToolSpec

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class _ScriptedProvider:
    """LLMProvider stub. Either returns ``response`` or raises ``raise_with``."""

    response: AIMessage | None = None
    raise_with: BaseException | None = None
    calls: list[dict[str, object]] = field(default_factory=list)

    async def complete(
        self,
        *,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolSpec],
    ) -> AIMessage:
        self.calls.append({"messages": list(messages), "tools": list(tools)})
        if self.raise_with is not None:
            raise self.raise_with
        assert self.response is not None
        return self.response


def _handle(provider: _ScriptedProvider, key: str = "test:primary") -> ProviderHandle:
    return ProviderHandle(provider=provider, key=key)


def _msgs() -> list[BaseMessage]:
    return [HumanMessage(content="hello")]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_primary_succeeds_no_fallback() -> None:
    expected = AIMessage(content="hi")
    primary = _ScriptedProvider(response=expected)
    fallback = _ScriptedProvider(response=AIMessage(content="should not be called"))

    router = LLMRouter(
        providers=[_handle(primary, "p"), _handle(fallback, "f")],
    )
    result = await router(messages=_msgs(), tools=[])

    assert result is expected
    assert len(primary.calls) == 1
    assert fallback.calls == []


# ---------------------------------------------------------------------------
# Test matrix #20 — primary fails, fallback succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_error_falls_back() -> None:
    primary = _ScriptedProvider(raise_with=LLMServerError("anthropic 503"))
    fallback = _ScriptedProvider(response=AIMessage(content="from fallback"))
    router = LLMRouter(providers=[_handle(primary, "p"), _handle(fallback, "f")])

    result = await router(messages=_msgs(), tools=[])

    assert result.content == "from fallback"
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_rate_limit_falls_back() -> None:
    primary = _ScriptedProvider(raise_with=LLMRateLimitError("anthropic 429"))
    fallback = _ScriptedProvider(response=AIMessage(content="ok"))
    router = LLMRouter(providers=[_handle(primary, "p"), _handle(fallback, "f")])

    result = await router(messages=_msgs(), tools=[])

    assert result.content == "ok"


@pytest.mark.asyncio
async def test_network_error_falls_back() -> None:
    primary = _ScriptedProvider(raise_with=LLMNetworkError("connection reset"))
    fallback = _ScriptedProvider(response=AIMessage(content="ok"))
    router = LLMRouter(providers=[_handle(primary, "p"), _handle(fallback, "f")])

    result = await router(messages=_msgs(), tools=[])

    assert result.content == "ok"


@pytest.mark.asyncio
async def test_circuit_open_falls_back() -> None:
    """E.4 ``LLMErrorHandlingMiddleware`` may pre-raise ``CircuitOpenError``
    without ever calling the provider — the router still treats it as a
    fallback trigger because the upstream key is unusable."""
    primary = _ScriptedProvider(raise_with=CircuitOpenError("p"))
    fallback = _ScriptedProvider(response=AIMessage(content="ok"))
    router = LLMRouter(providers=[_handle(primary, "p"), _handle(fallback, "f")])

    result = await router(messages=_msgs(), tools=[])

    assert result.content == "ok"


@pytest.mark.asyncio
async def test_three_provider_chain_second_works() -> None:
    a = _ScriptedProvider(raise_with=LLMServerError("a 503"))
    b = _ScriptedProvider(response=AIMessage(content="b"))
    c = _ScriptedProvider(response=AIMessage(content="should not be called"))
    router = LLMRouter(
        providers=[_handle(a, "a"), _handle(b, "b"), _handle(c, "c")],
    )

    result = await router(messages=_msgs(), tools=[])

    assert result.content == "b"
    assert len(a.calls) == 1
    assert len(b.calls) == 1
    assert c.calls == []


# ---------------------------------------------------------------------------
# Test matrix #21 — 4xx never falls back
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_error_does_not_fall_back() -> None:
    primary = _ScriptedProvider(raise_with=LLMClientError("anthropic 400 bad request"))
    fallback = _ScriptedProvider(response=AIMessage(content="should not be called"))
    router = LLMRouter(providers=[_handle(primary, "p"), _handle(fallback, "f")])

    with pytest.raises(LLMClientError, match="400 bad request"):
        await router(messages=_msgs(), tools=[])

    assert fallback.calls == []


# ---------------------------------------------------------------------------
# Test matrix #22 — all providers exhausted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_providers_5xx_raises_exhausted() -> None:
    first_exc = LLMServerError("a 503")
    last_exc = LLMServerError("b 502")
    a = _ScriptedProvider(raise_with=first_exc)
    b = _ScriptedProvider(raise_with=last_exc)
    router = LLMRouter(providers=[_handle(a, "a"), _handle(b, "b")])

    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await router(messages=_msgs(), tools=[])

    assert exc_info.value.last_exc is last_exc
    assert "503" not in str(exc_info.value)  # last error attached, not first
    assert "502" in str(exc_info.value)


@pytest.mark.asyncio
async def test_empty_provider_chain_raises_exhausted_immediately() -> None:
    router = LLMRouter(providers=[])
    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await router(messages=_msgs(), tools=[])

    assert isinstance(exc_info.value.last_exc, RuntimeError)


@pytest.mark.asyncio
async def test_single_provider_5xx_raises_exhausted() -> None:
    primary = _ScriptedProvider(raise_with=LLMServerError("503"))
    router = LLMRouter(providers=[_handle(primary, "p")])

    with pytest.raises(AllProvidersExhaustedError):
        await router(messages=_msgs(), tools=[])


# ---------------------------------------------------------------------------
# Mixed-error chains — ordering preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_retryable_errors_continue_until_success() -> None:
    a = _ScriptedProvider(raise_with=LLMRateLimitError("a 429"))
    b = _ScriptedProvider(raise_with=LLMServerError("b 503"))
    c = _ScriptedProvider(raise_with=LLMNetworkError("c reset"))
    d = _ScriptedProvider(response=AIMessage(content="finally"))
    router = LLMRouter(
        providers=[
            _handle(a, "a"),
            _handle(b, "b"),
            _handle(c, "c"),
            _handle(d, "d"),
        ],
    )

    result = await router(messages=_msgs(), tools=[])

    assert result.content == "finally"
    assert len(a.calls) == 1
    assert len(b.calls) == 1
    assert len(c.calls) == 1
    assert len(d.calls) == 1


@pytest.mark.asyncio
async def test_client_error_after_fallbacks_still_short_circuits() -> None:
    """Even mid-chain, a 4xx still aborts immediately — the next
    provider would see the same bad request."""
    a = _ScriptedProvider(raise_with=LLMServerError("a 503"))
    b = _ScriptedProvider(raise_with=LLMClientError("b 400"))
    c = _ScriptedProvider(response=AIMessage(content="should not be called"))
    router = LLMRouter(
        providers=[_handle(a, "a"), _handle(b, "b"), _handle(c, "c")],
    )

    with pytest.raises(LLMClientError):
        await router(messages=_msgs(), tools=[])

    assert c.calls == []


# ---------------------------------------------------------------------------
# Protocol contract
# ---------------------------------------------------------------------------


def test_router_satisfies_llm_provider_input_protocol() -> None:
    """Router's call signature matches :class:`LLMProvider.complete` —
    the integration with E.6 graph_builder relies on it being callable
    as an :class:`LLMCaller`."""
    # Smoke check via duck-typing: router has the expected attributes.
    router = LLMRouter(providers=[])
    assert callable(router)


def test_handle_is_frozen() -> None:
    """``ProviderHandle`` is ``frozen=True`` so it can be reused as a
    dict key / set member without mutability surprises."""
    primary = _ScriptedProvider()
    handle = ProviderHandle(provider=primary, key="x")
    with pytest.raises(Exception):  # noqa: B017 - frozen dataclass raises FrozenInstanceError
        handle.key = "y"  # type: ignore[misc]


def test_scripted_provider_satisfies_protocol() -> None:
    """Confidence check on the test helper itself."""
    assert isinstance(_ScriptedProvider(response=AIMessage(content="x")), LLMProvider)
