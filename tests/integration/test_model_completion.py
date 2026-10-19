import json
from dataclasses import replace

import pytest
from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    Content,
    FunctionInvocationLayer,
    Message,
)

from app.agent import review_wave
from app.model_client import OllamaStructuredTools
from app.schemas import ReviewRequest
from app.scripted_model_client import ScriptedModelClient
from app.tools import TOOL_NAMES

REQUEST = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-2026-10-19-1400")


@pytest.mark.parametrize("mode", ["scripted", "ollama"])
async def test_client_without_script_counter_uses_shared_guarded_tools(store, mode):
    _, settings, repo = store
    seen_tools = []
    seen_choices = []
    script = ScriptedModelClient(REQUEST.depot_id, REQUEST.delivery_wave_id, settings.review_at)

    class Client(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
        async def _inner_get_response(self, *, messages, stream, options, **kwargs):
            if mode == "ollama":
                schema = options["response_format"]
                names = schema.get("properties", {}).get("name", {}).get("enum", [])
                seen_tools.append(names)
            else:
                seen_tools.append([function.name for function in options.get("tools", [])])
            seen_choices.append(options.get("tool_choice"))
            if mode == "ollama":
                results = json.loads(messages[-1].text.split("\n", 1)[0][len("Tool results: ") :])
                result = results[-1]["result"] if results else None
                call = script.next_call(result)
                script.turn += 1
                value = {"name": call[0], "arguments": call[1]} if call else result
                return ChatResponse(
                    messages=Message("assistant", [Content.from_text(json.dumps(value))])
                )
            return await script._inner_get_response(
                messages=messages, stream=stream, options=options
            )

    client = Client(middleware=[OllamaStructuredTools(REQUEST)] if mode == "ollama" else [])
    result, tools = await review_wave(repo, REQUEST, replace(settings, mode=mode), client)
    assert result.assignments[0].duration_minutes == 11
    assert tuple(call["name"] for call in tools.calls) == TOOL_NAMES
    assert all(call["status"] == "success" for call in tools.calls)
    assert tools.persisted == result
    if mode == "ollama":
        assert seen_tools == [[name] for name in TOOL_NAMES] + [[]]
        assert seen_choices == ["none"] * 8


async def test_non_scripted_premature_completion_never_persists(store):
    _, settings, repo = store

    class Client(FunctionInvocationLayer, BaseChatClient):
        async def _inner_get_response(self, **kwargs):
            return ChatResponse(messages=Message("assistant", [Content.from_text("{}")]))

    with pytest.raises(ValueError, match="complete acknowledged"):
        await review_wave(repo, REQUEST, replace(settings, mode="ollama"), Client())
    assert [
        item
        async for item in repo.database.get_container_client("recommendations").read_all_items()
    ] == []
