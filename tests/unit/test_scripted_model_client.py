import json

import pytest
from agent_framework import Agent, Content, Message

from app.scripted_model_client import ScriptedModelClient


async def test_framework_dispatches_real_typed_function():
    calls = []

    async def get_depot_policy(depotId: str) -> dict[str, str]:
        """Load the depot policy."""
        calls.append(depotId)
        return {"depotId": depotId}

    class OneTurnClient(ScriptedModelClient):
        def next_call(self, result):
            if self.turn == 0:
                return "get_depot_policy", {"depotId": self.depot_id}
            return None

    client = OneTurnClient("SEA-01", "wave-1", "2026-10-19T12:30:00-07:00")
    agent = Agent(client, tools=[get_depot_policy])
    result = await agent.run("Review wave")
    assert calls == ["SEA-01"]
    assert json.loads(result.text) == {"depotId": "SEA-01"}
    assert client.turn == 2


async def test_unexpected_tool_result_is_rejected():
    client = ScriptedModelClient("SEA-01", "wave-1", "2026-10-19T12:30:00-07:00")
    client.turn = 1
    with pytest.raises(ValueError, match="call ID"):
        await client._inner_get_response(
            messages=[
                Message(
                    "tool", [Content.from_function_result("wrong", result={"depotId": "SEA-01"})]
                )
            ],
            stream=False,
            options={},
        )


async def test_script_exhaustion_is_explicit():
    client = ScriptedModelClient("SEA-01", "wave-1", "2026-10-19T12:30:00-07:00")
    client.turn = 20
    with pytest.raises(ValueError, match="turn limit"):
        await client._inner_get_response(messages=[], stream=False, options={})
