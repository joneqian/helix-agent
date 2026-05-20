"""LLM provider fallback router — Stream E.11 + E.12.5.

:class:`LLMRouter` implements the :class:`~orchestrator.llm.caller.LLMCaller`
protocol so the ReAct graph (E.6) treats it as a single callable; under
the hood it walks a chain of :class:`ProviderHandle` entries (primary
first, then fallbacks) and falls back on **retryable** errors only.

Fallback semantics — straight from
[STREAM-E-DESIGN § 2.4](../../../../../docs/streams/STREAM-E-DESIGN.md):

- :class:`LLMClientError` (4xx) → re-raise immediately. The caller is
  malformed; the next provider would reject it for the same reason and
  waste its rate-limit budget.
- :class:`LLMServerError` / :class:`LLMRateLimitError` /
  :class:`LLMNetworkError` / :class:`CircuitOpenError` → log + continue.
- All providers exhausted → :class:`AllProvidersExhaustedError` wrapping
  the last attempt's exception for diagnostic context.

The router **does not** retry within a single provider — that's
:class:`~helix_agent.runtime.middleware.LLMErrorHandlingMiddleware`'s
job (E.4 ``around_llm_call``). E.12.5 wires the middleware chain in:

::

    LLMRouter
      → (per provider) chain.invoke("around_llm_call", ctx, terminal=provider.complete)
                       ↑
                       │  ctx.payload contains provider_key / messages /
                       │  tools / response — Mini-ADR E-13 explains why
                       │  the wrap is per-provider and not per-router
                       │  (E.4 breaker per-key isolation + langfuse
                       │  per-provider span split).

Without the middleware chain (``chain=None``), each provider gets one
attempt before fallback — the M0 unit-test path and a valid degraded
mode for early-stage runs that haven't booted the chain yet.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from langchain_core.messages import AIMessage, BaseMessage

from helix_agent.common.observability import helix_counter
from helix_agent.runtime.middleware import (
    LLMClientError,
    LLMError,
    LLMStreamStaleError,
    MiddlewareChain,
    MiddlewareContext,
)
from orchestrator.tools.registry import ToolSpec

logger = logging.getLogger(__name__)

# Stream L.L3 — counter for provider-level stream stale timeouts. Labeled by
# ``provider_key`` so dashboards can show which upstream is hanging.
_llm_stream_stale_total = helix_counter(
    "helix_llm_stream_stale_total",
    "Provider calls that exceeded LLMRouter.stream_deadline_s (Stream L.L3).",
    ("provider_key",),
)


@runtime_checkable
class LLMProvider(Protocol):
    """Wire-level LLM caller — one provider, one model.

    Concrete adapters
    (:class:`~orchestrator.llm.providers.anthropic.AnthropicProvider`,
    :class:`~orchestrator.llm.providers.openai.OpenAIProvider`)
    translate :class:`BaseMessage` / :class:`ToolSpec` into the provider's
    wire format and back, raising :class:`LLMError` subclasses for
    transport / vendor failures. The router treats every
    :class:`LLMProvider` interchangeably; differences between Anthropic
    and OpenAI (system prompt placement, tool schemas, etc.) are an
    adapter concern.
    """

    async def complete(
        self,
        *,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolSpec],
    ) -> AIMessage:
        """Call the upstream provider and return the LLM's response.

        Implementations MUST raise :class:`LLMError` subclasses for any
        failure (transport, 4xx, 5xx, rate-limit, parse). Letting raw
        :class:`httpx.HTTPError` / :class:`ValueError` propagate would
        defeat the router's fallback classification.
        """


@dataclass(frozen=True)
class ProviderHandle:
    """One node in the router's fallback chain.

    ``key`` identifies the upstream rate-limit bucket — typically
    ``"<provider>:<role>"`` (e.g. ``"anthropic:primary"``,
    ``"openai:fallback"``). It is passed downstream as the
    ``provider_key`` payload field so E.4's
    :class:`~helix_agent.runtime.middleware.BreakerRegistry` builds
    per-key circuit breakers (Mini-ADR E-4: breakers are per upstream
    key, not per provider, because one tenant can hold multiple keys
    for the same vendor and they must fail in isolation).
    """

    provider: LLMProvider
    key: str


class AllProvidersExhaustedError(LLMError):
    """Every :class:`ProviderHandle` in the chain failed with a retryable
    error. Wraps the **last** attempt's exception so callers (and tests)
    can inspect what finally tripped the chain.

    Inherits :class:`LLMError` so it composes with E.4 error-handling
    middleware's exception classification — wrappers can treat
    "exhausted" as terminal rather than retryable.
    """

    def __init__(self, last_exc: BaseException) -> None:
        super().__init__(
            f"all LLM providers exhausted; last error: {type(last_exc).__name__}: {last_exc}"
        )
        self.last_exc = last_exc


@dataclass
class LLMRouter:
    """Try each :class:`ProviderHandle` in order; fall back on retryable errors.

    When ``around_llm_chain`` is set, each provider call is wrapped in
    ``chain.invoke("around_llm_call", ...)`` — letting E.4 retry /
    breaker, E.5 langfuse span recording, and any future
    around-LLM-call middleware run **per provider** (Mini-ADR E-13).

    See module docstring for the full fallback semantics. The router is
    stateless — all per-provider state (breaker counters, rate-limit
    tokens) lives in middleware / inside :class:`LLMProvider` adapters
    so swapping the router or wrapping it with retries is safe.
    """

    providers: Sequence[ProviderHandle]
    around_llm_chain: MiddlewareChain | None = field(default=None)
    #: Stream L.L3 — wall-clock cap on a single provider's ``complete()``
    #: call. ``None`` or ``0`` disables the timeout (dev / long batch
    #: paths); positive values wrap each provider attempt in
    #: ``asyncio.wait_for`` and translate ``TimeoutError`` into
    #: :class:`LLMStreamStaleError` so the router falls back to the next
    #: provider rather than locking the run.
    stream_deadline_s: float | None = field(default=None)

    async def __call__(
        self,
        *,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolSpec],
    ) -> AIMessage:
        if not self.providers:
            raise AllProvidersExhaustedError(
                RuntimeError("LLMRouter constructed with empty provider chain")
            )

        last_exc: LLMError | None = None
        for idx, handle in enumerate(self.providers):
            try:
                return await self._call_one(handle, messages=messages, tools=tools)
            except LLMClientError:
                logger.warning(
                    "llm_router.client_error_no_fallback idx=%d key=%s",
                    idx,
                    handle.key,
                )
                raise
            except LLMError as exc:
                last_exc = exc
                next_idx = idx + 1
                has_next = next_idx < len(self.providers)
                logger.warning(
                    "llm_router.provider_failed idx=%d key=%s err=%s fallback=%s",
                    idx,
                    handle.key,
                    type(exc).__name__,
                    self.providers[next_idx].key if has_next else "<none>",
                )
                if has_next:
                    continue
                break

        assert last_exc is not None  # noqa: S101 - loop invariant
        raise AllProvidersExhaustedError(last_exc)

    async def _call_one(
        self,
        handle: ProviderHandle,
        *,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolSpec],
    ) -> AIMessage:
        """Invoke one provider, optionally wrapped in the around-LLM chain.

        Without ``around_llm_chain`` we just delegate to ``provider.complete``
        — the M0 unit-test path. With the chain set, build a
        :class:`MiddlewareContext` carrying ``provider_key`` + the call
        inputs, let the chain run middlewares around a terminal that
        actually calls the provider and stashes the result in
        ``ctx.payload["response"]``.
        """
        if self.around_llm_chain is None:
            result = await self._invoke_with_deadline(
                handle,
                handle.provider.complete(messages=messages, tools=tools),
            )
            assert isinstance(result, AIMessage)  # noqa: S101 - provider Protocol contract
            return result

        ctx = MiddlewareContext(
            payload={
                "provider_key": handle.key,
                "messages": list(messages),
                "tools": list(tools),
            }
        )

        async def terminal(c: MiddlewareContext) -> None:
            response = await handle.provider.complete(
                messages=c.payload["messages"],
                tools=c.payload["tools"],
            )
            c.payload["response"] = response

        await self._invoke_with_deadline(handle, self.around_llm_chain.invoke(ctx, terminal))
        response = ctx.payload.get("response")
        if not isinstance(response, AIMessage):
            # Middleware mis-handled the terminal (didn't call call_next, or
            # cleared the response) → surface clearly rather than silently
            # returning a falsy / wrong-typed value.
            raise RuntimeError(
                f"around_llm_call chain finished without populating an AIMessage "
                f"response for provider_key={handle.key!r}"
            )
        return response

    async def _invoke_with_deadline(
        self,
        handle: ProviderHandle,
        coro: Awaitable[Any],
    ) -> Any:
        """Stream L.L3 — wrap a provider invocation in ``asyncio.wait_for``.

        ``stream_deadline_s`` is per-provider (Mini-ADR L-3): a hung
        provider trips the timeout, raises :class:`LLMStreamStaleError`
        (a retryable :class:`LLMServerError` subclass), and the surrounding
        :meth:`__call__` loop falls back to the next provider rather than
        locking the run. When ``stream_deadline_s`` is ``None`` or ``0``
        the call is awaited directly (dev / long-batch path).
        """
        deadline = self.stream_deadline_s
        if deadline is None or deadline <= 0:
            return await coro
        try:
            return await asyncio.wait_for(coro, timeout=deadline)
        except TimeoutError as exc:
            _llm_stream_stale_total.labels(provider_key=handle.key).inc()
            logger.warning(
                "llm_router.stream_stale key=%s deadline_s=%.1f",
                handle.key,
                deadline,
            )
            raise LLMStreamStaleError(
                f"provider {handle.key!r} exceeded stream_deadline_s={deadline:.1f}"
            ) from exc
