from dataclasses import replace

import pytest
from agent_framework import (
    BaseChatClient,
    ChatResponse,
    Content,
    FunctionInvocationLayer,
    Message,
)

from app.agent import review_wave
from app.schemas import ReviewRequest
from app.scripted_model_client import ScriptedModelClient
from app.tools import TOOL_NAMES

REQUEST = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-2026-10-19-1400")


@pytest.mark.parametrize("mode", ["scripted", "ollama"])
async def test_client_without_script_counter_uses_shared_guarded_tools(store, mode):
    _, settings, repo = store
    seen_tools = []
    script = ScriptedModelClient(REQUEST.depot_id, REQUEST.delivery_wave_id, settings.review_at)

    class Client(FunctionInvocationLayer, BaseChatClient):
        async def _inner_get_response(self, *, messages, stream, options, **kwargs):
            seen_tools.append([function.name for function in options.get("tools", [])])
            return await script._inner_get_response(
                messages=messages, stream=stream, options=options
            )

    result, tools = await review_wave(repo, REQUEST, replace(settings, mode=mode), Client())
    assert result.assignments[0].duration_minutes == 11
    assert tuple(call["name"] for call in tools.calls) == TOOL_NAMES
    assert all(call["status"] == "success" for call in tools.calls)
    assert tools.persisted == result
    if mode == "ollama":
        assert seen_tools == [[name] for name in TOOL_NAMES] + [[]]


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
