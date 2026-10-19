import asyncio
import json
from pathlib import Path

import httpx

from app.agent import review_wave
from app.api import create_app
from app.fleet_rules import canonical_hash
from app.schemas import ReviewRequest, ReviewResponse
from app.tools import TOOL_NAMES, wire

REQUEST = {"depotId": "SEA-01", "deliveryWaveId": "wave-2026-10-19-1400"}


async def call_api(client, settings, payload=REQUEST):
    app = create_app(settings, client)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        return await http.post("/agent/review-delivery-wave", json=payload)


async def test_agent_recommends_rebalance_for_seeded_delivery_wave(store):
    client, settings, repo = store
    response = await call_api(client, settings)
    assert response.status_code == 200, response.text
    result = response.json()
    golden = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "expected-golden.json").read_text()
    )
    assert result == golden
    assert result["recommendation"] == "rebalanceCharging"
    assert result["assignments"] == [
        {
            "vehicleId": "van-042",
            "chargerId": "charger-fast-03",
            "start": "2026-10-19T12:30:00-07:00",
            "durationMinutes": 11,
            "reason": "Battery state is below route requirement with safety buffer",
        }
    ]
    assert result["routeRisks"] == [
        {"routeId": "route-77", "vehicleId": "van-042", "risk": "batteryShortfall"}
    ]
    assert result["evidence"] == sorted(
        [
            "policy-SEA-01",
            REQUEST["deliveryWaveId"],
            "route-77",
            "route-88",
            "vehicle-van-042",
            "vehicle-van-088",
            "telemetry-van-042-latest",
            "telemetry-van-088-latest",
            "charger-fast-03",
        ]
    )
    assert result["decisionHash"] == canonical_hash(
        ReviewResponse.model_validate(result).model_dump(by_alias=True, exclude={"decision_hash"})
    )
    stored = await repo.read("recommendations", result["auditId"], "SEA-01")
    assert stored["payload"] == result
    assert {r["id"] for r in stored["evidenceRecords"]} == set(result["evidence"])
    for record in stored["evidenceRecords"]:
        source = await repo.read(record["container"], record["id"], record["partitionKey"])
        assert source["depotId"] == "SEA-01"
    assert all(record["etag"] for record in stored["sourceVersions"])


async def test_framework_tool_sequence_and_arguments(store):
    _, settings, repo = store
    result, tools = await review_wave(repo, ReviewRequest.model_validate(REQUEST), settings)
    assert tuple(call["name"] for call in tools.calls) == TOOL_NAMES
    assert tools.calls[2]["arguments"]["routeIds"] == ["route-77", "route-88"]
    assert tools.calls[3]["arguments"]["vehicleIds"] == ["van-042", "van-088"]
    assert tools.calls[4]["arguments"] == {"vehicleIds": ["van-042", "van-088"]}
    assert tools.calls[5]["arguments"] == {
        "depotId": "SEA-01",
        "connectorTypes": ["CCS"],
        "startAfter": settings.review_at,
        "endBefore": "2026-10-19T14:00:00-07:00",
    }
    assert tools.calls[6]["arguments"]["decision"] == wire(tools.decision)
    assert tools.persisted == result
    assert len(repo.trace) >= 10


async def test_agent_writes_one_recommendation_for_repeated_wave_review(store):
    client, settings, repo = store
    responses = [(await call_api(client, settings)).json() for _ in range(10)]
    assert all(result == responses[0] for result in responses)
    concurrent = await asyncio.gather(call_api(client, settings), call_api(client, settings))
    assert all(r.status_code == 200 and r.json() == responses[0] for r in concurrent)
    container = repo.database.get_container_client("recommendations")
    audits = [
        a
        async for a in container.query_items(
            "SELECT * FROM c WHERE c.depotId = @depot",
            parameters=[{"name": "@depot", "value": "SEA-01"}],
            partition_key="SEA-01",
        )
    ]
    assert len(audits) == 1
    telemetry = await repo.read("telemetry", "telemetry-van-042-latest", "van-042")
    telemetry["batteryPercent"] = 90
    await repo.database.get_container_client("telemetry").upsert_item(telemetry)
    changed = await call_api(client, settings)
    assert changed.status_code == 200, changed.text
    changed_result = changed.json()
    assert changed_result["recommendation"] == "noAction"
    assert changed_result["assignments"] == changed_result["routeRisks"] == []
    assert changed_result["auditId"] == responses[0]["auditId"]
    assert changed_result["decisionHash"] != responses[0]["decisionHash"]
    audit = await repo.read("recommendations", changed_result["auditId"], "SEA-01")
    assert audit["payload"] == changed_result


async def test_validation_and_missing_wave_have_no_write(store):
    client, settings, repo = store
    for bad in [
        {**REQUEST, "extra": 1},
        {**REQUEST, "depotId": 1},
        {**REQUEST, "deliveryWaveId": "bad/id"},
    ]:
        response = await call_api(client, settings, bad)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalidRequest"
    missing = await call_api(client, settings, {**REQUEST, "deliveryWaveId": "missing"})
    assert missing.status_code == 404, missing.text
    assert missing.json()["error"]["code"] == "waveNotFound"
    assert [
        a async for a in repo.database.get_container_client("recommendations").read_all_items()
    ] == []
