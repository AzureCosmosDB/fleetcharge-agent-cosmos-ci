import asyncio
from dataclasses import replace

import httpx
import pytest
from agent_framework import ChatResponse, Content, Message
from azure.core.exceptions import ServiceRequestError
from test_agent_review_delivery_wave import REQUEST, call_api

from app.agent import review_wave
from app.api import create_app
from app.schemas import ReviewRequest
from app.scripted_model_client import ScriptedModelClient
from app.tools import ReviewTools


async def audit_count(repo):
    return len(
        [
            item
            async for item in repo.database.get_container_client("recommendations").read_all_items()
        ]
    )


async def test_failed_write_is_503_and_never_fake_success(store, monkeypatch):
    client, settings, repo = store

    async def fail_write(self, audit):
        raise ServiceRequestError("Test transport failure")

    monkeypatch.setattr(type(repo), "upsert", fail_write)
    response = await call_api(client, settings)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["retryable"] is True
    assert "may have completed" in response.json()["error"]["message"]
    assert await audit_count(repo) == 0


async def test_acknowledged_write_is_retained_if_transport_outcome_uncertain(store, monkeypatch):
    client, settings, repo = store
    original = type(repo).upsert

    async def uncertain_write(self, audit):
        await original(self, audit)
        raise ServiceRequestError("Lost acknowledgement after persistence")

    monkeypatch.setattr(type(repo), "upsert", uncertain_write)
    response = await call_api(client, settings)
    assert response.status_code == 503, response.text
    assert await audit_count(repo) == 1


async def test_timeout_is_504_no_prewritten_audit(store, monkeypatch):
    client, settings, repo = store

    async def stalled_read(self, depotId):
        await asyncio.sleep(10)

    monkeypatch.setattr(ReviewTools, "get_depot_policy", stalled_read)
    # Preserve the registered name for the framework tool schema.
    stalled_read.__name__ = "get_depot_policy"
    response = await call_api(client, replace(settings, timeout_seconds=0.01))
    assert response.status_code == 504, response.text
    assert response.json()["error"]["code"] == "reviewTimedOut"
    assert await audit_count(repo) == 0


@pytest.mark.parametrize("mutation", ["proposal", "wrong-depot", "unknown-tool", "duplicate"])
async def test_script_tampering_never_persists(store, mutation):
    _, settings, repo = store

    class TamperedClient(ScriptedModelClient):
        def next_call(self, result):
            call = super().next_call(result)
            if mutation == "proposal" and self.turn == 6:
                call[1]["decision"]["evidence"] = []
            if self.turn == 0:
                if mutation == "wrong-depot":
                    call[1]["depotId"] = "PDX-02"
                elif mutation == "unknown-tool":
                    return "invented_tool", {}
            if mutation == "duplicate" and self.turn == 1:
                return "get_depot_policy", {"depotId": "SEA-01"}
            return call

    with pytest.raises((ValueError, KeyError)):
        await review_wave(
            repo,
            ReviewRequest.model_validate(REQUEST),
            settings,
            TamperedClient("SEA-01", REQUEST["deliveryWaveId"], settings.review_at),
        )
    assert await audit_count(repo) == 0


async def test_invalid_terminal_response_retains_acknowledged_audit(store):
    _, settings, repo = store

    class BadTerminal(ScriptedModelClient):
        async def _inner_get_response(self, **kwargs):
            response = await super()._inner_get_response(**kwargs)
            if self.turn == 8:
                return ChatResponse(messages=Message("assistant", [Content.from_text("{}")]))
            return response

    with pytest.raises(ValueError):
        await review_wave(
            repo,
            ReviewRequest.model_validate(REQUEST),
            settings,
            BadTerminal("SEA-01", REQUEST["deliveryWaveId"], settings.review_at),
        )
    assert await audit_count(repo) == 1


async def test_malformed_json_has_consistent_envelope(store):
    client, settings, repo = store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, client)), base_url="http://test"
    ) as http:
        response = await http.post(
            "/agent/review-delivery-wave", content="{", headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalidRequest"
    assert await audit_count(repo) == 0


async def test_unexpected_tool_failure_is_sanitized_500(store, monkeypatch):
    client, settings, repo = store

    async def get_depot_policy(self, depotId):
        """Injected tool failure."""
        raise RuntimeError("internal details must not reach the HTTP response")

    monkeypatch.setattr(ReviewTools, "get_depot_policy", get_depot_policy)
    response = await call_api(client, settings)
    assert response.status_code == 500, response.text
    assert response.json()["error"]["code"] == "agentExecutionFailed"
    assert "internal details" not in response.text
    assert await audit_count(repo) == 0
