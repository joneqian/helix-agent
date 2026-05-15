"""Unit tests for the OpenAI-compatible provider presets — Stream E.11.5.

These vendors all expose the OpenAI Chat Completions wire format
behind a different base URL (and sometimes a different path). The
tests verify the URL composition and that the factory output is
drop-in compatible with :class:`OpenAIProvider`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from orchestrator.llm import (
    DEEPSEEK_BASE_URL,
    DEFAULT_CHAT_COMPLETIONS_PATH,
    DOUBAO_BASE_URL,
    DOUBAO_CHAT_COMPLETIONS_PATH,
    GLM_BASE_URL,
    GLM_CHAT_COMPLETIONS_PATH,
    KIMI_BASE_URL,
    QWEN_BASE_URL,
    OpenAIProvider,
    make_deepseek_client,
    make_doubao_client,
    make_glm_client,
    make_kimi_client,
    make_qwen_client,
)
from orchestrator.llm.providers.openai import HTTPOpenAIClient

# ---------------------------------------------------------------------------
# URL composition helpers
# ---------------------------------------------------------------------------


@dataclass
class _RecordingTransport(httpx.AsyncBaseTransport):
    """Capture the actual URL httpx posts to so we can verify
    ``{base_url}{chat_completions_path}`` concatenation."""

    response_body: Mapping[str, Any] = field(default_factory=dict)
    captured_url: str | None = None
    captured_auth: str | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.captured_url = str(request.url)
        self.captured_auth = request.headers.get("authorization")
        return httpx.Response(200, json=dict(self.response_body))


async def _make_call(client: HTTPOpenAIClient) -> _RecordingTransport:
    transport = client.transport
    assert isinstance(transport, _RecordingTransport)
    transport.response_body = {"choices": [{"message": {"content": "ok"}}]}
    provider = OpenAIProvider(client=client, model="model-x")
    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])
    assert isinstance(result, AIMessage)
    return transport


# ---------------------------------------------------------------------------
# Per-vendor URL + auth composition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kimi_client_targets_moonshot_v1() -> None:
    transport = _RecordingTransport()
    client = make_kimi_client(api_key="sk-kimi-test", transport=transport)
    captured = await _make_call(client)
    assert captured.captured_url == f"{KIMI_BASE_URL}{DEFAULT_CHAT_COMPLETIONS_PATH}"
    assert captured.captured_auth == "Bearer sk-kimi-test"


@pytest.mark.asyncio
async def test_glm_client_targets_paas_v4() -> None:
    transport = _RecordingTransport()
    client = make_glm_client(api_key="zp-test", transport=transport)
    captured = await _make_call(client)
    assert captured.captured_url == f"{GLM_BASE_URL}{GLM_CHAT_COMPLETIONS_PATH}"
    # Sanity: not the default /v1/chat/completions
    assert "/v1/chat/completions" not in captured.captured_url
    assert captured.captured_auth == "Bearer zp-test"


@pytest.mark.asyncio
async def test_deepseek_client_targets_api_deepseek_v1() -> None:
    transport = _RecordingTransport()
    client = make_deepseek_client(api_key="sk-ds-test", transport=transport)
    captured = await _make_call(client)
    assert captured.captured_url == f"{DEEPSEEK_BASE_URL}{DEFAULT_CHAT_COMPLETIONS_PATH}"
    assert captured.captured_auth == "Bearer sk-ds-test"


@pytest.mark.asyncio
async def test_qwen_client_targets_dashscope_compatible_mode() -> None:
    transport = _RecordingTransport()
    client = make_qwen_client(api_key="sk-qwen-test", transport=transport)
    captured = await _make_call(client)
    assert captured.captured_url == f"{QWEN_BASE_URL}{DEFAULT_CHAT_COMPLETIONS_PATH}"
    # Sanity: compatible-mode segment is present
    assert "/compatible-mode/" in captured.captured_url
    assert captured.captured_auth == "Bearer sk-qwen-test"


@pytest.mark.asyncio
async def test_doubao_client_targets_ark_api_v3() -> None:
    transport = _RecordingTransport()
    client = make_doubao_client(api_key="ark-test", transport=transport)
    captured = await _make_call(client)
    assert captured.captured_url == f"{DOUBAO_BASE_URL}{DOUBAO_CHAT_COMPLETIONS_PATH}"
    # Sanity: not the default /v1/chat/completions
    assert "/v1/chat/completions" not in captured.captured_url
    assert captured.captured_auth == "Bearer ark-test"


# ---------------------------------------------------------------------------
# Base URL override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_doubao_base_url_override_works() -> None:
    """Multi-region ARK deployments: the factory must accept a custom
    base_url (e.g. for huabei2 / shanghai endpoints) while keeping the
    same path suffix."""
    transport = _RecordingTransport()
    client = make_doubao_client(
        api_key="ark-test",
        base_url="https://ark.cn-shanghai.volces.com",
        transport=transport,
    )
    captured = await _make_call(client)
    assert captured.captured_url == (
        "https://ark.cn-shanghai.volces.com" + DOUBAO_CHAT_COMPLETIONS_PATH
    )


@pytest.mark.asyncio
async def test_kimi_base_url_override_works() -> None:
    transport = _RecordingTransport()
    client = make_kimi_client(
        api_key="sk-test",
        base_url="https://api.moonshot.cn.internal",
        transport=transport,
    )
    captured = await _make_call(client)
    assert (
        captured.captured_url == "https://api.moonshot.cn.internal" + DEFAULT_CHAT_COMPLETIONS_PATH
    )


# ---------------------------------------------------------------------------
# Factory output is a real HTTPOpenAIClient
# ---------------------------------------------------------------------------


def test_factories_return_http_openai_client_instances() -> None:
    """Each factory must return a :class:`HTTPOpenAIClient` so it
    composes with :class:`OpenAIProvider` without additional plumbing."""
    factories = [
        make_kimi_client,
        make_glm_client,
        make_deepseek_client,
        make_qwen_client,
        make_doubao_client,
    ]
    for factory in factories:
        client = factory(api_key="test")
        assert isinstance(client, HTTPOpenAIClient), (
            f"{factory.__name__} returned {type(client).__name__}, not HTTPOpenAIClient"
        )


def test_glm_path_is_non_default() -> None:
    """Regression guard: GLM must NOT be using ``/v1/chat/completions`` —
    Zhipu's gateway 404s on that path."""
    client = make_glm_client(api_key="test")
    assert client.chat_completions_path == GLM_CHAT_COMPLETIONS_PATH
    assert client.chat_completions_path != DEFAULT_CHAT_COMPLETIONS_PATH


def test_doubao_path_is_non_default() -> None:
    """Regression guard: Doubao must NOT be using ``/v1/chat/completions``."""
    client = make_doubao_client(api_key="test")
    assert client.chat_completions_path == DOUBAO_CHAT_COMPLETIONS_PATH
    assert client.chat_completions_path != DEFAULT_CHAT_COMPLETIONS_PATH


def test_kimi_qwen_deepseek_use_default_path() -> None:
    """Sanity: vendors that DO use ``/v1/chat/completions`` keep the
    default — otherwise they'd silently break."""
    for factory in (make_kimi_client, make_qwen_client, make_deepseek_client):
        client = factory(api_key="test")
        assert client.chat_completions_path == DEFAULT_CHAT_COMPLETIONS_PATH, (
            f"{factory.__name__} unexpectedly overrode the default path"
        )
