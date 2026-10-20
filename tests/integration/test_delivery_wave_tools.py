from dataclasses import replace

import pytest
from tool_review import REQUEST, run_tool_review

from app.fleet_rules import SourceDataError
from app.schemas import ReviewRequest
from app.tools import wire


async def test_tools_never_assign_vehicle_on_maintenance_hold(store):
    _, settings, repo = store
    route = await repo.read("routes", "route-88", "SEA-01")
    route["assignedVehicleId"] = "van-099"
    await repo.database.get_container_client("routes").upsert_item(route)
    held = await repo.read("vehicles", "vehicle-van-099", "SEA-01")
    held["assignedRouteId"] = "route-88"
    await repo.database.get_container_client("vehicles").upsert_item(held)
    response, _ = await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)
    result = wire(response)
    assert result["recommendation"] == "unableToSchedule"
    assert not any(a["vehicleId"] == "van-099" for a in result["assignments"])
    assert {"routeId": "route-88", "vehicleId": "van-099", "risk": "maintenanceHold"} in result[
        "routeRisks"
    ]
    assert "vehicle-van-099" in result["evidence"]


async def test_tools_use_latest_telemetry_for_battery_decision(store):
    _, settings, repo = store
    result, tools = await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)
    assert next(v.battery_percent for v in tools.vehicles if v.vehicle_id == "van-042") == 95
    assert next(t.battery_percent for t in tools.telemetry if t.vehicle_id == "van-042") == 58
    assert any(r["id"] == "telemetry-van-042-old" for r in repo.trace)
    assert "telemetry-van-042-old" not in result.evidence
    assert result.assignments[0].duration_minutes == 11


@pytest.mark.parametrize("mode", ["stale", "future", "missing", "ownership"])
async def test_unusable_telemetry_is_an_error_and_preserves_prior_audit(store, mode):
    _, settings, repo = store
    request = ReviewRequest.model_validate(REQUEST)
    baseline = wire((await run_tool_review(repo, request, settings))[0])
    readings = await repo.telemetry("van-042")
    container = repo.database.get_container_client("telemetry")
    for item in readings:
        await container.delete_item(item["id"], partition_key="van-042")
    if mode != "missing":
        item = next(r for r in readings if r["id"].endswith("latest"))
        if mode == "stale":
            item["observedAt"] = "2026-10-19T11:59:59-07:00"
        elif mode == "future":
            item["observedAt"] = "2026-10-19T12:31:00-07:00"
        else:
            item["depotId"] = "PDX-02"
        await container.upsert_item(item)
    with pytest.raises(SourceDataError):
        await run_tool_review(repo, request, settings)
    audit = await repo.read("recommendations", baseline["auditId"], "SEA-01")
    assert audit["payload"] == baseline


async def test_freshness_boundary_tie_and_future_selection(store):
    _, settings, repo = store
    container = repo.database.get_container_client("telemetry")
    for item in await repo.telemetry("van-042"):
        await container.delete_item(item["id"], partition_key="van-042")
    for identity, when, battery in [
        ("a-reading", "2026-10-19T12:00:00-07:00", 58),
        ("z-reading", "2026-10-19T12:00:00-07:00", 95),
        ("future", "2026-10-19T12:31:00-07:00", 95),
    ]:
        await container.upsert_item(
            {
                "id": identity,
                "type": "batteryTelemetry",
                "vehicleId": "van-042",
                "depotId": "SEA-01",
                "observedAt": when,
                "batteryPercent": battery,
            }
        )
    result, tools = await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)
    assert "a-reading" in result.evidence
    assert "z-reading" not in result.evidence and "future" not in result.evidence
    assert wire(tools.telemetry[0])["batteryPercent"] == 58


async def test_missing_route_is_explicit_source_error(store):
    _, settings, repo = store
    await repo.database.get_container_client("routes").delete_item(
        "route-88", partition_key="SEA-01"
    )
    with pytest.raises(SourceDataError):
        await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)


async def test_invalid_source_type_fails_before_write(store):
    _, settings, repo = store
    vehicle = await repo.read("vehicles", "vehicle-van-042", "SEA-01")
    vehicle["maxChargeKw"] = True
    await repo.database.get_container_client("vehicles").upsert_item(vehicle)
    with pytest.raises((SourceDataError, ValueError)):
        await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)


async def test_clock_validation_before_departure(store):
    _, settings, repo = store
    with pytest.raises(SourceDataError):
        await run_tool_review(
            repo,
            ReviewRequest.model_validate(REQUEST),
            replace(settings, review_at="2026-10-19T14:00:00-07:00"),
        )
