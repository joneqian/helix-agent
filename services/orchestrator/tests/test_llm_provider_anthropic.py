"""Unit tests for :class:`AnthropicProvider` + :class:`HTTPAnthropicClient`
— Stream E.11.
"""

from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from helix_agent.runtime.middleware import (
    LLMClientError,
    LLMNetworkError,
    LLMRateLimitError,
    LLMServerError,
)
from orchestrator.llm import (
    AnthropicProvider,
    HTTPAnthropicClient,
    RecordingAnthropicClient,
)
from orchestrator.tools.registry import ToolSpec

# ---------------------------------------------------------------------------
# Recording client — request shape mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_message_lifted_to_system_field() -> None:
    client = RecordingAnthropicClient(
        response={"content": [{"type": "text", "text": "ok"}]},
    )
    provider = AnthropicProvider(client=client, model="claude-sonnet-4-6")

    await provider.complete(
        messages=[
            SystemMessage(content="you are helpful"),
            HumanMessage(content="hi"),
        ],
        tools=[],
    )

    assert client.calls[0]["system"] == "you are helpful"
    assert client.calls[0]["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_multiple_system_messages_concatenated() -> None:
    client = RecordingAnthropicClient(
        response={"content": [{"type": "text", "text": "ok"}]},
    )
    provider = AnthropicProvider(client=client, model="claude")

    await provider.complete(
        messages=[
            SystemMessage(content="rule 1"),
            SystemMessage(content="rule 2"),
            HumanMessage(content="go"),
        ],
        tools=[],
    )

    assert client.calls[0]["system"] == "rule 1\n\nrule 2"


@pytest.mark.asyncio
async def test_no_system_message_leaves_system_none() -> None:
    client = RecordingAnthropicClient(
        response={"content": [{"type": "text", "text": "ok"}]},
    )
    provider = AnthropicProvider(client=client, model="claude")

    await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert client.calls[0]["system"] is None


@pytest.mark.asyncio
async def test_ai_message_with_tool_calls_emits_tool_use_block() -> None:
    client = RecordingAnthropicClient(
        response={"content": [{"type": "text", "text": "done"}]},
    )
    provider = AnthropicProvider(client=client, model="claude")

    history_ai = AIMessage(
        content="checking",
        tool_calls=[
            {
                "id": "toolu_1",
                "name": "read_file",
                "args": {"path": "/etc/hosts"},
                "type": "tool_call",
            }
        ],
    )

    await provider.complete(
        messages=[
            HumanMessage(content="read hosts"),
            history_ai,
            ToolMessage(content="127.0.0.1 localhost", tool_call_id="toolu_1"),
        ],
        tools=[],
    )

    assistant_msg = client.calls[0]["messages"][1]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] == [
        {"type": "text", "text": "checking"},
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "read_file",
            "input": {"path": "/etc/hosts"},
        },
    ]

    tool_msg = client.calls[0]["messages"][2]
    assert tool_msg == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": "127.0.0.1 localhost",
            }
        ],
    }


@pytest.mark.asyncio
async def test_tool_specs_mapped_to_input_schema() -> None:
    client = RecordingAnthropicClient(
        response={"content": [{"type": "text", "text": "ok"}]},
    )
    provider = AnthropicProvider(client=client, model="claude")
    spec = ToolSpec(
        name="search",
        description="search the web",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
    )

    await provider.complete(messages=[HumanMessage(content="hi")], tools=[spec])

    assert client.calls[0]["tools"] == [
        {
            "name": "search",
            "description": "search the web",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }
    ]


@pytest.mark.asyncio
async def test_empty_tools_yields_no_tools_field() -> None:
    client = RecordingAnthropicClient(
        response={"content": [{"type": "text", "text": "ok"}]},
    )
    provider = AnthropicProvider(client=client, model="claude")

    await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert client.calls[0]["tools"] is None


# ---------------------------------------------------------------------------
# Response decoding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_only_response_yields_plain_ai_message() -> None:
    client = RecordingAnthropicClient(
        response={"content": [{"type": "text", "text": "hello world"}]},
    )
    provider = AnthropicProvider(client=client, model="claude")

    result = await provider.complete(
        messages=[HumanMessage(content="hi")],
        tools=[],
    )

    assert result.content == "hello world"
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_tool_use_response_decoded_to_tool_calls() -> None:
    client = RecordingAnthropicClient(
        response={
            "content": [
                {"type": "text", "text": "let me check"},
                {
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "search",
                    "input": {"q": "hello"},
                },
            ]
        },
    )
    provider = AnthropicProvider(client=client, model="claude")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert result.content == "let me check"
    assert result.tool_calls == [
        {"id": "toolu_abc", "name": "search", "args": {"q": "hello"}, "type": "tool_call"},
    ]


@pytest.mark.asyncio
async def test_multiple_tool_use_blocks_decoded_in_order() -> None:
    client = RecordingAnthropicClient(
        response={
            "content": [
                {"type": "tool_use", "id": "1", "name": "a", "input": {}},
                {"type": "tool_use", "id": "2", "name": "b", "input": {"x": 1}},
            ]
        },
    )
    provider = AnthropicProvider(client=client, model="claude")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert [tc["name"] for tc in result.tool_calls] == ["a", "b"]
    assert result.tool_calls[1]["args"] == {"x": 1}


@pytest.mark.asyncio
async def test_empty_response_yields_empty_ai_message() -> None:
    client = RecordingAnthropicClient(response={})
    provider = AnthropicProvider(client=client, model="claude")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert result.content == ""
    assert result.tool_calls == []


# ---------------------------------------------------------------------------
# HTTPAnthropicClient — error mapping
# ---------------------------------------------------------------------------


def _http_client(handler) -> HTTPAnthropicClient:  # type: ignore[no-untyped-def]
    """Build an :class:`HTTPAnthropicClient` wired to ``handler`` via
    :class:`httpx.MockTransport` so tests exercise the real error-mapping
    code path without hitting the network."""
    return HTTPAnthropicClient(
        api_key="sk-test",
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )


async def _call(client: HTTPAnthropicClient) -> object:
    return await client.messages(
        model="claude",
        system=None,
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        max_tokens=100,
    )


@pytest.mark.asyncio
async def test_http_429_raises_rate_limit_error() -> None:
    client = _http_client(lambda _req: httpx.Response(429, text="rate_limited"))
    with pytest.raises(LLMRateLimitError, match="429"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_400_raises_client_error() -> None:
    client = _http_client(lambda _req: httpx.Response(400, text="bad_request"))
    with pytest.raises(LLMClientError, match="400"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_503_raises_server_error() -> None:
    client = _http_client(lambda _req: httpx.Response(503, text="unavailable"))
    with pytest.raises(LLMServerError, match="503"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_network_error_raises_network_error() -> None:
    """Raw :class:`httpx.HTTPError` is mapped to :class:`LLMNetworkError`."""

    def _boom(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _http_client(_boom)
    with pytest.raises(LLMNetworkError, match="connection"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_200_returns_parsed_json() -> None:
    client = _http_client(
        lambda _req: httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]}),
    )
    body = await _call(client)
    assert body == {"content": [{"type": "text", "text": "ok"}]}


@pytest.mark.asyncio
async def test_http_200_non_object_body_raises_server_error() -> None:
    client = _http_client(lambda _req: httpx.Response(200, json=["unexpected", "list"]))
    with pytest.raises(LLMServerError, match="non-object"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_500_error_body_truncated_to_500_chars() -> None:
    """Verbose 5xx bodies should not blow up logs / exception messages."""
    huge = "x" * 2000
    client = _http_client(lambda _req: httpx.Response(500, text=huge))
    with pytest.raises(LLMServerError) as exc_info:
        await _call(client)
    assert "...[truncated]" in str(exc_info.value)
    # Truncation cap is 500 chars; full exception string is bounded.
    assert len(str(exc_info.value)) < 1000


# ---------------------------------------------------------------------------
# Recording client error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recording_client_raises_injected_exception() -> None:
    client = RecordingAnthropicClient(raise_with=LLMServerError("simulated"))
    provider = AnthropicProvider(client=client, model="claude")

    with pytest.raises(LLMServerError, match="simulated"):
        await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    # The call should still have been recorded — useful for asserting
    # that the request was constructed before the simulated failure.
    assert len(client.calls) == 1


def test_recording_response_default_is_empty_dict() -> None:
    client = RecordingAnthropicClient()
    assert client.response == {}
    assert client.calls == []
    # Confidence check: json roundtrip works on the default response.
    json.dumps(dict(client.response))
