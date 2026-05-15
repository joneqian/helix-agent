"""LLM caller + provider routing subsystem — Stream E.6 + E.11.

Public surface:

- :class:`LLMCaller` (E.6) — the abstract callable the ReAct graph
  consumes.
- :class:`LLMRouter` (E.11) — multi-provider fallback router that
  implements :class:`LLMCaller`.
- :class:`ProviderHandle` / :class:`LLMProvider` /
  :class:`AllProvidersExhaustedError` (E.11) — building blocks.
- Concrete adapters (:class:`AnthropicProvider`, :class:`OpenAIProvider`)
  and their recording / HTTP client variants for production + tests.
"""

from orchestrator.llm.caller import LLMCaller as LLMCaller
from orchestrator.llm.providers import (
    DEFAULT_MAX_TOKENS as DEFAULT_MAX_TOKENS,
)
from orchestrator.llm.providers import (
    AnthropicClient as AnthropicClient,
)
from orchestrator.llm.providers import (
    AnthropicProvider as AnthropicProvider,
)
from orchestrator.llm.providers import (
    HTTPAnthropicClient as HTTPAnthropicClient,
)
from orchestrator.llm.providers import (
    HTTPOpenAIClient as HTTPOpenAIClient,
)
from orchestrator.llm.providers import (
    OpenAIClient as OpenAIClient,
)
from orchestrator.llm.providers import (
    OpenAIProvider as OpenAIProvider,
)
from orchestrator.llm.providers import (
    RecordingAnthropicClient as RecordingAnthropicClient,
)
from orchestrator.llm.providers import (
    RecordingOpenAIClient as RecordingOpenAIClient,
)
from orchestrator.llm.router import (
    AllProvidersExhaustedError as AllProvidersExhaustedError,
)
from orchestrator.llm.router import (
    LLMProvider as LLMProvider,
)
from orchestrator.llm.router import (
    LLMRouter as LLMRouter,
)
from orchestrator.llm.router import (
    ProviderHandle as ProviderHandle,
)

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "AllProvidersExhaustedError",
    "AnthropicClient",
    "AnthropicProvider",
    "HTTPAnthropicClient",
    "HTTPOpenAIClient",
    "LLMCaller",
    "LLMProvider",
    "LLMRouter",
    "OpenAIClient",
    "OpenAIProvider",
    "ProviderHandle",
    "RecordingAnthropicClient",
    "RecordingOpenAIClient",
]
