"""LLM provider fallback router — Stream E.11.

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
job (E.4 ``around_llm_call``). Expected production wiring:

::

    LLMRouter
      → (per provider) middleware chain @ around_llm_call
        → (terminal handler) ProviderHandle.provider.complete(...)

Without the middleware, each provider gets one attempt before fallback —
which is the M0 unit-test path and also a valid degraded mode.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from langchain_core.messages import AIMessage, BaseMessage

from helix_agent.runtime.middleware import LLMClientError, LLMError
from orchestrator.tools.registry import ToolSpec

logger = logging.getLogger(__name__)


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

    See module docstring for the full fallback semantics. The router is
    stateless — all per-provider state (breaker counters, rate-limit
    tokens) lives in middleware / inside :class:`LLMProvider` adapters
    so swapping the router or wrapping it with retries is safe.
    """

    providers: Sequence[ProviderHandle]

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
                return await handle.provider.complete(messages=messages, tools=tools)
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
