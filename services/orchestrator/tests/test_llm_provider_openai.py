"""Unit tests for :class:`OpenAIProvider` + :class:`HTTPOpenAIClient`
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
    HTTPOpenAIClient,
    OpenAIProvider,
    RecordingOpenAIClient,
)
from orchestrator.tools.registry import ToolSpec

# ---------------------------------------------------------------------------
# Recording client — request shape mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_message_inline_in_messages_array() -> None:
    client = RecordingOpenAIClient(
        response={"choices": [{"message": {"content": "ok"}}]},
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    await provider.complete(
        messages=[SystemMessage(content="be helpful"), HumanMessage(content="hi")],
        tools=[],
    )

    assert client.calls[0]["messages"] == [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "hi"},
    ]


@pytest.mark.asyncio
async def test_ai_message_with_tool_calls_emits_function_call_format() -> None:
    client = RecordingOpenAIClient(
        response={"choices": [{"message": {"content": "ok"}}]},
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    history_ai = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_1",
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
            ToolMessage(content="127.0.0.1", tool_call_id="call_1"),
        ],
        tools=[],
    )

    sent = client.calls[0]["messages"]
    assert sent[1] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps({"path": "/etc/hosts"}),
                },
            }
        ],
    }
    assert sent[2] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "127.0.0.1",
    }


@pytest.mark.asyncio
async def test_tool_spec_emits_function_schema() -> None:
    client = RecordingOpenAIClient(
        response={"choices": [{"message": {"content": "ok"}}]},
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")
    spec = ToolSpec(
        name="search",
        description="search the web",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
    )

    await provider.complete(messages=[HumanMessage(content="hi")], tools=[spec])

    assert client.calls[0]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "search the web",
                "parameters": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_empty_tools_yields_no_tools_field() -> None:
    client = RecordingOpenAIClient(
        response={"choices": [{"message": {"content": "ok"}}]},
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert client.calls[0]["tools"] is None


# ---------------------------------------------------------------------------
# Response decoding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_only_choice_yields_plain_ai_message() -> None:
    client = RecordingOpenAIClient(
        response={"choices": [{"message": {"role": "assistant", "content": "hello"}}]},
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert result.content == "hello"
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_tool_calls_decoded_with_json_args() -> None:
    client = RecordingOpenAIClient(
        response={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"q": "hello"}',
                                },
                            }
                        ],
                    }
                }
            ]
        },
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert result.content == ""
    assert result.tool_calls == [
        {"id": "call_abc", "name": "search", "args": {"q": "hello"}, "type": "tool_call"},
    ]


@pytest.mark.asyncio
async def test_malformed_arguments_string_decodes_to_empty_dict() -> None:
    """OpenAI sometimes streams partial JSON in ``arguments``; we tolerate
    rather than raise, matching the design choice in
    :func:`orchestrator.llm.providers.openai._parse_arguments`."""
    client = RecordingOpenAIClient(
        response={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "x", "arguments": "{not json"},
                            }
                        ],
                    }
                }
            ]
        },
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert result.tool_calls[0]["args"] == {}


@pytest.mark.asyncio
async def test_arguments_already_dict_passes_through() -> None:
    client = RecordingOpenAIClient(
        response={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "x", "arguments": {"a": 1}},
                            }
                        ],
                    }
                }
            ]
        },
    )
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert result.tool_calls[0]["args"] == {"a": 1}


@pytest.mark.asyncio
async def test_empty_choices_yields_empty_ai_message() -> None:
    client = RecordingOpenAIClient(response={"choices": []})
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")

    result = await provider.complete(messages=[HumanMessage(content="hi")], tools=[])

    assert result.content == ""
    assert result.tool_calls == []


# ---------------------------------------------------------------------------
# HTTPOpenAIClient — error mapping
# ---------------------------------------------------------------------------


def _http_client(handler) -> HTTPOpenAIClient:  # type: ignore[no-untyped-def]
    return HTTPOpenAIClient(
        api_key="sk-test",
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )


async def _call(client: HTTPOpenAIClient) -> object:
    return await client.chat_completions(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
    )


@pytest.mark.asyncio
async def test_http_429_raises_rate_limit_error() -> None:
    client = _http_client(lambda _req: httpx.Response(429, text="rate_limit"))
    with pytest.raises(LLMRateLimitError, match="429"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_401_raises_client_error() -> None:
    client = _http_client(lambda _req: httpx.Response(401, text="unauthorized"))
    with pytest.raises(LLMClientError, match="401"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_502_raises_server_error() -> None:
    client = _http_client(lambda _req: httpx.Response(502, text="bad gateway"))
    with pytest.raises(LLMServerError, match="502"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_network_error_raises_network_error() -> None:
    def _boom(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns failure")

    client = _http_client(_boom)
    with pytest.raises(LLMNetworkError, match="dns"):
        await _call(client)


@pytest.mark.asyncio
async def test_http_200_returns_parsed_json() -> None:
    client = _http_client(
        lambda _req: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
    )
    body = await _call(client)
    assert body == {"choices": [{"message": {"content": "ok"}}]}


@pytest.mark.asyncio
async def test_http_200_non_object_body_raises_server_error() -> None:
    client = _http_client(lambda _req: httpx.Response(200, json=["nope"]))
    with pytest.raises(LLMServerError, match="non-object"):
        await _call(client)
