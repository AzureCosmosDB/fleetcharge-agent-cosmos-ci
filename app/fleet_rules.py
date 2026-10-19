"""Pure deterministic review rules; recommendations do not reserve chargers."""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from app.schemas import (
    COSMOS_METADATA,
    Assignment,
    Charger,
    Decision,
    DeliveryWave,
    DepotPolicy,
    Route,
    RouteRisk,
    Telemetry,
    Vehicle,
)

RULES_VERSION = "fleetcharge-demo-v1"
CHARGE_EFFICIENCY = Decimal("0.90")
ASSIGNMENT_REASON: Final = "Battery state is below route requirement with safety buffer"


class SourceDataError(ValueError):
    """Source documents are missing, invalid, or disagree about ownership."""


def canonical_hash(value: object) -> str:
    """Hash canonical JSON, with numeric spelling and timestamp offsets normalized."""

    def encode(item: object) -> str:
        if isinstance(item, BaseModel):
            return encode(item.model_dump(by_alias=True))
        if isinstance(item, datetime):
            if item.tzinfo is None or item.utcoffset() is None:
                raise SourceDataError("Timestamp must be timezone-aware.")
            return json.dumps(item.astimezone(UTC).isoformat(timespec="microseconds"))
        if item is None or isinstance(item, (str, bool)):
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, (int, float, Decimal)):
            number = Decimal(str(item))
            if not number.is_finite():
                raise SourceDataError("Number must be finite.")
            text = format(number, "f")
            return "0" if number == 0 else text.rstrip("0").rstrip(".") if "." in text else text
        if isinstance(item, Mapping):
            if any(not isinstance(key, str) for key in item):
                raise SourceDataError("Canonical object keys must be strings.")
            return (
                "{"
                + ",".join(
                    json.dumps(key, ensure_ascii=False) + ":" + encode(item[key])
                    for key in sorted(item)
                    if key not in COSMOS_METADATA
                )
                + "}"
            )
        if isinstance(item, (list, tuple)):
            return "[" + ",".join(encode(element) for element in item) + "]"
        raise SourceDataError(f"Unsupported canonical value: {type(item).__name__}.")

    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def compute_decision(
    policy: DepotPolicy,
    wave: DeliveryWave,
    routes: list[Route],
    vehicles: list[Vehicle],
    telemetry: list[Telemetry],
    chargers: list[Charger],
    review_at: datetime,
) -> Decision:
    """Evaluate complete wave data using one already-selected reading per vehicle."""
    try:
        # Revalidate even model_copy/model_construct values at this trust boundary.
        policy = DepotPolicy.model_validate(policy.model_dump())
        wave = DeliveryWave.model_validate(wave.model_dump())
        routes = [Route.model_validate(item.model_dump()) for item in routes]
        vehicles = [Vehicle.model_validate(item.model_dump()) for item in vehicles]
        telemetry = [Telemetry.model_validate(item.model_dump()) for item in telemetry]
        chargers = [Charger.model_validate(item.model_dump()) for item in chargers]
    except (ValidationError, AttributeError, TypeError, ValueError) as exc:
        raise SourceDataError("Invalid source document.") from exc
    if not isinstance(review_at, datetime) or review_at.utcoffset() is None:
        raise SourceDataError("Review time must be timezone-aware.")
    if wave.depot_id != policy.depot_id or wave.start_time.astimezone(UTC) <= review_at.astimezone(
        UTC
    ):
        raise SourceDataError("Wave ownership or departure is invalid.")
    if policy.id != f"policy-{policy.depot_id}":
        raise SourceDataError("Policy identity is invalid.")
    for item in [*routes, *vehicles, *telemetry, *chargers]:
        if item.depot_id != policy.depot_id:
            raise SourceDataError("Source depot ownership is invalid.")
    if len({item.id for item in routes}) != len(routes):
        raise SourceDataError("Duplicate routes.")
    if {item.id for item in routes} != set(wave.route_ids):
        raise SourceDataError("Wave route references are incomplete.")
    expected_vehicles = {item.assigned_vehicle_id for item in routes}
    if len(expected_vehicles) != len(routes):
        raise SourceDataError("Routes must have distinct assigned vehicles.")
    if (
        {item.vehicle_id for item in vehicles} != expected_vehicles
        or len(vehicles) != len(expected_vehicles)
        or {item.vehicle_id for item in telemetry} != expected_vehicles
        or len(telemetry) != len(expected_vehicles)
    ):
        raise SourceDataError("Vehicle or selected telemetry set is incomplete.")
    if len({item.charger_id for item in chargers}) != len(chargers):
        raise SourceDataError("Duplicate chargers.")
    if any(item.id != item.charger_id for item in chargers):
        raise SourceDataError("Charger identity is invalid.")
    by_vehicle = {item.vehicle_id: item for item in vehicles}
    by_telemetry = {item.vehicle_id: item for item in telemetry}
    for route in routes:
        vehicle = by_vehicle[route.assigned_vehicle_id]
        reading = by_telemetry[vehicle.vehicle_id]
        if (
            route.delivery_wave_id != wave.id
            or vehicle.id != f"vehicle-{vehicle.vehicle_id}"
            or vehicle.assigned_route_id != route.id
        ):
            raise SourceDataError("Route and vehicle references disagree.")
        age = review_at.astimezone(UTC) - reading.observed_at.astimezone(UTC)
        if not timedelta(0) <= age <= timedelta(minutes=policy.telemetry_max_age_minutes):
            raise SourceDataError(
                f"Latest valid telemetry is unavailable for vehicle {vehicle.vehicle_id}."
            )

    assignments: list[Assignment] = []
    risks: list[RouteRisk] = []
    evidence = {policy.id, wave.id}
    evidence.update(item.id for item in [*routes, *vehicles, *telemetry])
    blocked = {
        charger.charger_id: [
            (reservation.start.astimezone(UTC), reservation.end.astimezone(UTC))
            for reservation in charger.reservations
        ]
        for charger in chargers
    }
    unable = False
    for route in sorted(routes, key=lambda item: item.id):
        vehicle = by_vehicle[route.assigned_vehicle_id]
        reading = by_telemetry[vehicle.vehicle_id]
        target = (
            Decimal(str(route.required_battery_percent))
            + Decimal(str(route.weather_adjustment_percent))
            + Decimal(str(policy.minimum_battery_buffer_percent))
        )

        def add_risk(
            risk: Any, route_id: str = route.id, vehicle_id: str = vehicle.vehicle_id
        ) -> None:
            risks.append(RouteRisk(route_id=route_id, vehicle_id=vehicle_id, risk=risk))

        if vehicle.maintenance_hold:
            add_risk("maintenanceHold")
            unable = True
            continue
        if vehicle.status != "available":
            add_risk("vehicleUnavailable")
            unable = True
            continue
        if target > 100:
            add_risk("energyRequirementUnachievable")
            unable = True
            continue
        shortfall = target - Decimal(str(reading.battery_percent))
        if shortfall <= 0:
            continue
        add_risk("batteryShortfall")
        energy = Decimal(str(vehicle.usable_battery_kwh)) * shortfall / 100
        candidates: list[tuple[datetime, datetime, str, int, Charger]] = []
        for charger in chargers:
            if charger.status != "available" or charger.connector_type != vehicle.connector_type:
                continue
            power = min(Decimal(str(vehicle.max_charge_kw)), Decimal(str(charger.max_kw)))
            duration = int(
                (energy / (power * CHARGE_EFFICIENCY) * 60).to_integral_value(
                    rounding=ROUND_CEILING
                )
            )
            if duration <= 0 or duration > policy.charger_reservation_window_minutes:
                continue
            start = review_at.astimezone(UTC)
            length = timedelta(minutes=duration)
            for reserved_start, reserved_end in sorted(blocked[charger.charger_id]):
                if reserved_end <= start:
                    continue
                if start + length <= reserved_start:
                    break
                start = reserved_end
            end = start + length
            if end <= wave.start_time.astimezone(UTC):
                candidates.append((end, start, charger.charger_id, duration, charger))
        if not candidates:
            add_risk("noFeasibleCharger")
            unable = True
            continue
        end, start, charger_id, duration, selected = min(candidates, key=lambda item: item[:3])
        blocked[charger_id].append((start, end))
        assignments.append(
            Assignment(
                vehicle_id=vehicle.vehicle_id,
                charger_id=charger_id,
                start=start.astimezone(review_at.tzinfo),
                duration_minutes=duration,
                reason=ASSIGNMENT_REASON,
            )
        )
        evidence.add(selected.id)
    return Decision(
        recommendation=(
            "unableToSchedule" if unable else "rebalanceCharging" if assignments else "noAction"
        ),
        assignments=sorted(
            assignments, key=lambda item: (item.start, item.vehicle_id, item.charger_id)
        ),
        route_risks=sorted(risks, key=lambda item: (item.route_id, item.vehicle_id, item.risk)),
        evidence=sorted(evidence),
    )
