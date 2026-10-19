from test_agent_review_delivery_wave import REQUEST, call_api

from app.agent import review_wave
from app.schemas import ReviewRequest


async def test_agent_does_not_use_charger_from_other_depot(store):
    _, settings, repo = store
    pdx = await repo.read("chargers", "charger-fast-03", "PDX-02")
    assert pdx["maxKw"] == 350
    repo.trace.clear()
    result, tools = await review_wave(repo, ReviewRequest.model_validate(REQUEST), settings)
    assert result.assignments[0].charger_id == pdx["id"]
    assert all(c.depot_id == "SEA-01" for c in tools.chargers)
    assert all(r["partitionKey"] == "SEA-01" for r in repo.trace if r["container"] == "chargers")
    audit = await repo.read("recommendations", result.audit_id, "SEA-01")
    charger_records = [r for r in audit["evidenceRecords"] if r["container"] == "chargers"]
    assert charger_records == [
        {"container": "chargers", "id": "charger-fast-03", "partitionKey": "SEA-01"}
    ]


async def test_reserved_charger_and_occupied_charger_not_feasible(store):
    client, settings, repo = store
    charger = await repo.read("chargers", "charger-fast-03", "SEA-01")
    charger["reservations"] = [
        {
            "vehicleId": "other-vehicle",
            "start": "2026-10-19T12:00:00-07:00",
            "end": "2026-10-19T14:00:00-07:00",
        }
    ]
    await repo.database.get_container_client("chargers").upsert_item(charger)
    response = await call_api(client, settings)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["recommendation"] == "unableToSchedule"
    assert result["assignments"] == []
    assert {r["risk"] for r in result["routeRisks"]} == {"batteryShortfall", "noFeasibleCharger"}
