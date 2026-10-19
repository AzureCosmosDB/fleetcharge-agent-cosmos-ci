import json

import pytest
from agent_framework import (
    BaseChatClient,
    ChatContext,
    ChatResponse,
    Content,
    FunctionTool,
    Message,
)

from app.model_client import OllamaStructuredTools, model_client
from app.schemas import ReviewRequest
from app.scripted_model_client import ScriptedModelClient
from app.settings import Settings


async def test_default_client_remains_scripted():
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")
    async with model_client(Settings(), request) as client:
        assert isinstance(client, ScriptedModelClient)
        assert client.depot_id == request.depot_id
        assert client.wave_id == request.delivery_wave_id


async def test_supplied_client_does_not_require_ollama_provider():
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")
    supplied: BaseChatClient = ScriptedModelClient("SEA-01", "wave-test", Settings.review_at)
    async with model_client(Settings(mode="ollama"), request, supplied) as client:
        assert client is supplied


def make_context():
    async def get_depot_policy(depotId: str) -> dict[str, str]:
        """Read the requested policy."""
        return {"depotId": depotId}

    function = FunctionTool(name="get_depot_policy", func=get_depot_policy)
    client = ScriptedModelClient("SEA-01", "wave-test", Settings.review_at)
    return ChatContext(
        client=client,
        messages=[Message("user", [Content.from_text('{"depotId":"SEA-01"}')])],
        options={"tools": [function]},
    )


async def test_structured_adapter_emits_model_arguments_and_preserves_identity():
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")
    context = make_context()
    registered = context.options["tools"]

    async def respond():
        assert context.options["tools"] == []
        schema = context.options["response_format"]
        assert schema["properties"]["name"]["enum"] == ["get_depot_policy"]
        assert schema["properties"]["arguments"]["properties"]["depotId"]["enum"] == ["SEA-01"]
        assert context.messages[-1].text.startswith("Tool results: []\n")
        assert len(context.messages[-1].contents) == 1
        context.result = ChatResponse(
            response_id="local-response",
            model="local-model",
            messages=Message(
                "assistant",
                [Content.from_text('{"name":"get_depot_policy","arguments":{"depotId":"SEA-01"}}')],
            ),
        )

    await OllamaStructuredTools(request).process(context, respond)
    assert context.options["tools"] is registered
    call = context.result.messages[0].contents[0]
    assert call.type == "function_call"
    assert call.name == "get_depot_policy"
    assert call.arguments == {"depotId": "SEA-01"}
    assert call.call_id.startswith("call-")
    assert context.result.response_id == "local-response"
    assert context.result.model == "local-model"
    assert "enum" not in registered[0].input_model.model_json_schema()["properties"]["depotId"]


@pytest.mark.parametrize(
    "proposal",
    [
        "not-json",
        "[]",
        '{"name":"unknown_tool","arguments":{}}',
        '{"name":"get_depot_policy","arguments":{},"extra":1}',
        '{"name":"get_depot_policy","arguments":{}}',
    ],
)
async def test_structured_adapter_rejects_invalid_model_proposals(proposal):
    context = make_context()
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")

    async def respond():
        context.result = ChatResponse(messages=Message("assistant", [Content.from_text(proposal)]))

    with pytest.raises(ValueError):
        await OllamaStructuredTools(request).process(context, respond)


async def test_structured_adapter_does_not_invent_or_repair_model_values():
    context = make_context()
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")

    async def respond():
        context.result = ChatResponse(
            messages=Message(
                "assistant",
                [Content.from_text('{"name":"get_depot_policy","arguments":{"depotId":"PDX-02"}}')],
            )
        )

    await OllamaStructuredTools(request).process(context, respond)
    assert context.result.messages[0].contents[0].arguments == {"depotId": "PDX-02"}


async def test_structured_adapter_preserves_real_tool_results():
    context = make_context()
    context.messages.extend(
        [
            Message(
                "assistant",
                [Content.from_function_call("source-call", "read_source", arguments={})],
            ),
            Message(
                "tool",
                [Content.from_function_result("source-call", result='{"batteryPercent":58}')],
            ),
        ]
    )

    async def respond():
        results = json.loads(context.messages[-1].text.split("\n", 1)[0][len("Tool results: ") :])
        assert results == [{"tool": "read_source", "result": {"batteryPercent": 58}}]
        context.result = ChatResponse(
            messages=Message(
                "assistant",
                [Content.from_text('{"name":"get_depot_policy","arguments":{"depotId":"SEA-01"}}')],
            )
        )

    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")
    await OllamaStructuredTools(request).process(context, respond)


async def test_structured_adapter_stops_on_failed_tool_before_model_call():
    context = make_context()
    context.messages.extend(
        [
            Message(
                "assistant", [Content.from_function_call("failed", "read_source", arguments={})]
            ),
            Message(
                "tool",
                [
                    Content.from_function_result(
                        "failed", result="Error: Function failed.", exception="source failed"
                    )
                ],
            ),
        ]
    )

    async def forbidden():
        pytest.fail("A failed tool must not trigger another model call")

    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")
    with pytest.raises(ValueError, match="failed tool"):
        await OllamaStructuredTools(request).process(context, forbidden)


async def test_structured_adapter_rejects_streaming_explicitly():
    context = make_context()
    context.stream = True
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")

    async def forbidden():
        pytest.fail("Unsupported streaming must not contact a model")

    with pytest.raises(ValueError, match="non-streaming"):
        await OllamaStructuredTools(request).process(context, forbidden)


async def test_structured_adapter_propagates_transport_failure_and_restores_tools():
    context = make_context()
    registered = context.options["tools"]
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-test")

    async def failed_provider():
        raise ConnectionError("Local model server unavailable")

    with pytest.raises(ConnectionError, match="unavailable"):
        await OllamaStructuredTools(request).process(context, failed_provider)
    assert context.options["tools"] is registered
