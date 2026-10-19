import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.fleet_rules import SourceDataError, canonical_hash, compute_decision
from app.schemas import Charger, DeliveryWave, DepotPolicy, ReviewRequest, Route, Telemetry, Vehicle

FIXTURES = Path(__file__).parents[1] / "fixtures"
NOW = datetime.fromisoformat("2026-10-19T12:30:00-07:00")


def documents(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def inputs() -> dict[str, Any]:
    return {
        "policy": DepotPolicy.model_validate(documents("depots")[0]),
        "wave": DeliveryWave.model_validate(documents("routes")[0]),
        "routes": [Route.model_validate(v) for v in documents("routes")[1:]],
        "vehicles": [Vehicle.model_validate(v) for v in documents("vehicles")[:2]],
        "telemetry": [Telemetry.model_validate(v) for v in documents("telemetry")[1:3]],
        "chargers": [
            Charger.model_validate(v) for v in documents("chargers") if v["depotId"] == "SEA-01"
        ],
        "review_at": NOW,
    }


def test_golden() -> None:
    decision = compute_decision(**inputs())
    assert decision.recommendation == "rebalanceCharging"
    assert [a.model_dump(by_alias=True, mode="json") for a in decision.assignments] == [
        {
            "vehicleId": "van-042",
            "chargerId": "charger-fast-03",
            "start": "2026-10-19T12:30:00-07:00",
            "durationMinutes": 11,
            "reason": "Battery state is below route requirement with safety buffer",
        }
    ]
    assert [(r.route_id, r.risk) for r in decision.route_risks] == [
        ("route-77", "batteryShortfall")
    ]
    assert decision.evidence == sorted(
        [
            "policy-SEA-01",
            "wave-2026-10-19-1400",
            "route-77",
            "route-88",
            "vehicle-van-042",
            "vehicle-van-088",
            "telemetry-van-042-latest",
            "telemetry-van-088-latest",
            "charger-fast-03",
        ]
    )


def test_healthy_and_summary_is_not_used() -> None:
    data = inputs()
    data["telemetry"][0] = data["telemetry"][0].model_copy(update={"battery_percent": 82.0})
    result = compute_decision(**data)
    assert result.recommendation == "noAction"
    assert result.assignments == []
    assert result.route_risks == []
    assert "charger-fast-03" not in result.evidence


@pytest.mark.parametrize(
    "field,value,risk",
    [
        ("maintenance_hold", True, "maintenanceHold"),
        ("status", "unavailable", "vehicleUnavailable"),
    ],
)
def test_exclusions(field: str, value: object, risk: str) -> None:
    data = inputs()
    data["vehicles"][0] = data["vehicles"][0].model_copy(update={field: value})
    result = compute_decision(**data)
    assert result.recommendation == "unableToSchedule"
    assert not result.assignments
    assert [r.risk for r in result.route_risks] == [risk]


def test_target_above_100() -> None:
    data = inputs()
    data["routes"][0] = data["routes"][0].model_copy(update={"required_battery_percent": 95.0})
    result = compute_decision(**data)
    assert [r.risk for r in result.route_risks] == ["energyRequirementUnachievable"]


def test_no_charger() -> None:
    data = inputs()
    data["chargers"] = []
    result = compute_decision(**data)
    assert result.recommendation == "unableToSchedule"
    assert [r.risk for r in result.route_risks] == ["batteryShortfall", "noFeasibleCharger"]


@pytest.mark.parametrize("status", ["offline", "occupied", "available"])
def test_ownership_validated_even_rejected_charger(status: str) -> None:
    data = inputs()
    wrong = Charger.model_validate(documents("chargers")[-1]).model_copy(
        update={"status": status, "connector_type": "incompatible"}
    )
    data["chargers"].append(wrong)
    with pytest.raises(SourceDataError):
        compute_decision(**data)


@pytest.mark.parametrize(
    "change",
    [
        "missing-route",
        "missing-vehicle",
        "missing-telemetry",
        "foreign-telemetry",
        "wrong-wave",
        "wrong-assignment",
        "duplicate-vehicle",
        "past-departure",
        "stale",
        "future",
        "duplicate-telemetry",
    ],
)
def test_bad_source_references(change: str) -> None:
    data = inputs()
    if change.startswith("missing-"):
        key = {"route": "routes", "vehicle": "vehicles", "telemetry": "telemetry"}[
            change.removeprefix("missing-")
        ]
        data[key].pop()
    elif change == "foreign-telemetry":
        data["telemetry"][0] = data["telemetry"][0].model_copy(update={"depot_id": "PDX-02"})
    elif change == "wrong-wave":
        data["routes"][0] = data["routes"][0].model_copy(update={"delivery_wave_id": "other"})
    elif change == "wrong-assignment":
        data["vehicles"][0] = data["vehicles"][0].model_copy(update={"assigned_route_id": None})
    elif change == "duplicate-vehicle":
        data["routes"][1] = data["routes"][1].model_copy(update={"assigned_vehicle_id": "van-042"})
    elif change == "past-departure":
        data["review_at"] = data["wave"].start_time
    elif change in {"stale", "future"}:
        observed = NOW + (timedelta(seconds=1) if change == "future" else -timedelta(minutes=31))
        data["telemetry"][0] = data["telemetry"][0].model_copy(update={"observed_at": observed})
    else:
        data["telemetry"].append(data["telemetry"][0])
    with pytest.raises(SourceDataError):
        compute_decision(**data)


def test_freshness_boundary_and_order_independence() -> None:
    data = inputs()
    data["telemetry"][0] = data["telemetry"][0].model_copy(
        update={"observed_at": NOW - timedelta(minutes=30)}
    )
    expected = compute_decision(**data)
    for key in ("routes", "vehicles", "telemetry", "chargers"):
        data[key].reverse()
    assert compute_decision(**data) == expected


def test_reservations_half_open_and_deadline() -> None:
    data = inputs()
    raw = documents("chargers")[0]
    raw["reservations"] = [
        {
            "vehicleId": "other",
            "start": NOW.isoformat(),
            "end": (NOW + timedelta(minutes=79)).isoformat(),
        }
    ]
    data["chargers"] = [Charger.model_validate(raw)]
    result = compute_decision(**data)
    assert result.assignments[0].start == NOW + timedelta(minutes=79)
    raw["reservations"][0]["end"] = (NOW + timedelta(minutes=80)).isoformat()
    data["chargers"] = [Charger.model_validate(raw)]
    assert compute_decision(**data).recommendation == "unableToSchedule"


def test_multiple_assignments_do_not_overlap() -> None:
    data = inputs()
    data["telemetry"][1] = data["telemetry"][1].model_copy(update={"battery_percent": 0.0})
    result = compute_decision(**data)
    first, second = result.assignments
    assert first.start + timedelta(minutes=first.duration_minutes) <= second.start


@pytest.mark.parametrize("value", [True, "58", float("nan"), float("inf"), -1, 101])
def test_numbers_are_strict(value: object) -> None:
    raw = documents("telemetry")[1]
    raw["batteryPercent"] = value
    with pytest.raises(ValidationError):
        Telemetry.model_validate(raw)


def test_metadata_extra_fields_and_aware_dates() -> None:
    raw = documents("telemetry")[1]
    raw["_etag"] = "version"
    assert Telemetry.model_validate(raw).vehicle_id == "van-042"
    raw["unexpected"] = "no"
    with pytest.raises(ValidationError):
        Telemetry.model_validate(raw)
    raw.pop("unexpected")
    raw["observedAt"] = "2026-10-19T12:20:00"
    with pytest.raises(ValidationError):
        Telemetry.model_validate(raw)


@pytest.mark.parametrize(
    "raw",
    [
        {"depotId": 1, "deliveryWaveId": "wave"},
        {"depotId": " SEA-01", "deliveryWaveId": "wave"},
        {"depotId": "SEA-01", "deliveryWaveId": "wave", "extra": True},
        {"depotId": "SEA-01", "deliveryWaveId": "wave", "_etag": "not allowed"},
    ],
)
def test_request_strict(raw: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ReviewRequest.model_validate(raw)


def test_canonical_hash() -> None:
    assert canonical_hash({"n": Decimal("1.00"), "at": NOW, "_etag": "a"}) == canonical_hash(
        {
            "at": NOW.astimezone(UTC),
            "n": 1.0,
            "_etag": "b",
        }
    )
    assert canonical_hash({"n": -0.0}) == canonical_hash({"n": 0})
    assert canonical_hash({"n": 1}) != canonical_hash({"n": 2})
    with pytest.raises(SourceDataError):
        canonical_hash({"at": datetime(2026, 10, 19)})
    with pytest.raises(SourceDataError):
        canonical_hash(float("nan"))


def test_maintenance_fixture_is_considered() -> None:
    data = inputs()
    held = Vehicle.model_validate(documents("vehicles")[2]).model_copy(
        update={"assigned_route_id": "route-88"}
    )
    data["vehicles"][1] = held
    data["routes"][1] = data["routes"][1].model_copy(update={"assigned_vehicle_id": "van-099"})
    data["telemetry"][1] = Telemetry.model_validate(documents("telemetry")[3])
    result = compute_decision(**data)
    assert result.recommendation == "unableToSchedule"
    assert [a.vehicle_id for a in result.assignments] == ["van-042"]
    assert [(r.vehicle_id, r.risk) for r in result.route_risks] == [
        ("van-042", "batteryShortfall"),
        ("van-099", "maintenanceHold"),
    ]
    assert "vehicle-van-099" in result.evidence
    assert "vehicle-van-088" not in result.evidence


@pytest.mark.parametrize(
    "field,value",
    [
        ("maxKw", True),
        ("maxKw", 0),
        ("maxKw", float("inf")),
        ("reservations", [{"vehicleId": "van", "start": NOW.isoformat(), "end": NOW.isoformat()}]),
    ],
)
def test_charger_values_strict(field: str, value: object) -> None:
    raw = documents("chargers")[0]
    raw[field] = value
    with pytest.raises(ValidationError):
        Charger.model_validate(raw)


def test_aware_timestamp_not_numeric() -> None:
    raw = documents("telemetry")[1]
    raw["observedAt"] = 1792437600
    with pytest.raises(ValidationError):
        Telemetry.model_validate(raw)


@pytest.mark.parametrize("minutes,feasible", [(45, True), (46, False)])
def test_policy_duration_limit(minutes: int, feasible: bool) -> None:
    data = inputs()
    # At 16 kW, a 24-point deficit on an N kWh battery needs exactly N minutes.
    data["chargers"] = [data["chargers"][0]]
    data["vehicles"][0] = data["vehicles"][0].model_copy(
        update={"usable_battery_kwh": float(minutes)}
    )
    data["chargers"][0] = data["chargers"][0].model_copy(update={"max_kw": 16.0})
    assert bool(compute_decision(**data).assignments) is feasible


def test_charger_ties_use_id_and_instant_order() -> None:
    data = inputs()
    second = data["chargers"][0].model_copy(update={"id": "charger-a", "charger_id": "charger-a"})
    data["chargers"] = [data["chargers"][0], second]
    result = compute_decision(**data)
    assert result.assignments[0].charger_id == "charger-a"


def test_touching_and_merged_reservations() -> None:
    data = inputs()
    raw = documents("chargers")[0]
    raw["reservations"] = [
        {
            "vehicleId": "a",
            "start": NOW.isoformat(),
            "end": (NOW + timedelta(minutes=5)).isoformat(),
        },
        {
            "vehicleId": "b",
            "start": (NOW + timedelta(minutes=4)).isoformat(),
            "end": (NOW + timedelta(minutes=8)).isoformat(),
        },
        {
            "vehicleId": "c",
            "start": (NOW + timedelta(minutes=19)).isoformat(),
            "end": (NOW + timedelta(minutes=30)).isoformat(),
        },
    ]
    data["chargers"] = [Charger.model_validate(raw)]
    result = compute_decision(**data)
    assert result.assignments[0].start == NOW + timedelta(minutes=8)


def test_invalid_copied_document_is_source_error() -> None:
    data = inputs()
    data["chargers"][1] = data["chargers"][1].model_copy(update={"max_kw": float("nan")})
    with pytest.raises(SourceDataError):
        compute_decision(**data)


def test_canonical_decimal_precision_and_nested_metadata() -> None:
    assert canonical_hash({"nested": {"_ts": 1, "n": Decimal("100.000")}}) == canonical_hash(
        {"nested": {"_ts": 2, "n": 100}}
    )
    assert canonical_hash(Decimal("1.00000000000000000000000000001")) != canonical_hash(1)
