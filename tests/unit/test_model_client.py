from agent_framework import BaseChatClient

from app.model_client import model_client
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
