"""Direct tool/SDK failure contracts; no model responses are substituted."""

import httpx
import pytest
from azure.core.exceptions import ServiceRequestError
from tool_review import REQUEST, run_tool_review

from app.api import create_app
from app.schemas import ReviewRequest
from app.tools import ReviewTools, wire


async def audit_count(repo):
    return len(
        [
            item
            async for item in repo.database.get_container_client("recommendations").read_all_items()
        ]
    )


@pytest.mark.parametrize("persist_first", [False, True])
async def test_tool_write_transport_failure_preserves_actual_outcome(
    store, monkeypatch, persist_first
):
    _, settings, repo = store
    original = type(repo).upsert

    async def failed_write(self, audit):
        if persist_first:
            await original(self, audit)
        raise ServiceRequestError("Test write transport failure")

    monkeypatch.setattr(type(repo), "upsert", failed_write)
    with pytest.raises(ServiceRequestError):
        await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)
    assert await audit_count(repo) == int(persist_first)


async def test_direct_tools_reject_wrong_depot_reordered_and_duplicate_calls(store):
    _, settings, repo = store
    tools = ReviewTools(repo, ReviewRequest.model_validate(REQUEST), settings)
    with pytest.raises(ValueError, match="depot"):
        await tools.get_depot_policy("PDX-02")
    with pytest.raises(ValueError, match="reordered"):
        await tools.get_delivery_wave("SEA-01", REQUEST["deliveryWaveId"])
    await tools.get_depot_policy("SEA-01")
    with pytest.raises(ValueError, match="reordered"):
        await tools.get_depot_policy("SEA-01")
    assert await audit_count(repo) == 0


async def test_tools_reject_tampered_write_without_changing_acknowledged_audit(store):
    _, settings, repo = store
    result, tools = await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)
    tools.calls.pop()
    with pytest.raises(ValueError, match="does not match"):
        await tools.write_charging_recommendation(
            "SEA-01", REQUEST["deliveryWaveId"], {**wire(tools.decision), "evidence": []}
        )
    stored = await repo.read("recommendations", result.audit_id, "SEA-01")
    assert stored["payload"] == wire(result)


async def test_malformed_json_has_consistent_api_envelope(store):
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
