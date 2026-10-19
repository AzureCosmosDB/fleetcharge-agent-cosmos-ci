"""Strict domain documents and the public review contract."""

import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

COSMOS_METADATA = frozenset({"_rid", "_self", "_etag", "_attachments", "_ts"})


def finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("A JSON number is required.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Number must be finite.")
    return result


Identifier = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
Text = Annotated[StrictStr, Field(min_length=1)]
Number = Annotated[float, BeforeValidator(finite_number)]
Percent = Annotated[Number, Field(ge=0, le=100)]
PositiveNumber = Annotated[Number, Field(gt=0)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]


def timestamp_input(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("Timestamp must be an aware datetime or ISO timestamp string.")
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(timestamp_input)]


class WireModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", allow_inf_nan=False
    )


class Document(WireModel):
    id: Identifier
    depot_id: Identifier

    @model_validator(mode="before")
    @classmethod
    def ignore_sdk_metadata(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if key not in COSMOS_METADATA}
        return value


class DepotPolicy(Document):
    type: Literal["depotPolicy"]
    timezone: Text
    minimum_battery_buffer_percent: Percent
    telemetry_max_age_minutes: PositiveInt
    charger_reservation_window_minutes: PositiveInt
    allow_route_swap: StrictBool
    allow_partial_charge: StrictBool

    @model_validator(mode="after")
    def supported_policy(self) -> Self:
        if self.allow_route_swap or self.allow_partial_charge:
            raise ValueError("Route swapping and partial charging are unsupported.")
        return self


class DeliveryWave(Document):
    type: Literal["deliveryWave"]
    start_time: Timestamp
    route_ids: Annotated[list[Identifier], Field(min_length=1)]
    status: Literal["planning"]

    @field_validator("route_ids")
    @classmethod
    def distinct_routes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate route IDs.")
        return value


class Route(Document):
    type: Literal["route"]
    delivery_wave_id: Identifier
    assigned_vehicle_id: Identifier
    required_battery_percent: Percent
    weather_adjustment_percent: Percent


class Vehicle(Document):
    type: Literal["vehicle"]
    vehicle_id: Identifier
    status: Literal["available", "unavailable"]
    maintenance_hold: StrictBool
    connector_type: Text
    max_charge_kw: PositiveNumber
    usable_battery_kwh: PositiveNumber
    battery_percent: Percent
    assigned_route_id: Identifier | None


class Telemetry(Document):
    type: Literal["batteryTelemetry"]
    vehicle_id: Identifier
    observed_at: Timestamp
    battery_percent: Percent


class Reservation(WireModel):
    vehicle_id: Identifier
    start: Timestamp
    end: Timestamp

    @model_validator(mode="after")
    def positive_interval(self) -> Self:
        if self.end.astimezone(UTC) <= self.start.astimezone(UTC):
            raise ValueError("Reservation end must follow start.")
        return self


class Charger(Document):
    type: Literal["charger"]
    charger_id: Identifier
    status: Literal["available", "occupied", "offline"]
    connector_type: Text
    max_kw: PositiveNumber
    reservations: list[Reservation]


class ReviewRequest(WireModel):
    depot_id: Identifier
    delivery_wave_id: Identifier


class Assignment(WireModel):
    vehicle_id: Identifier
    charger_id: Identifier
    start: Timestamp
    duration_minutes: PositiveInt
    reason: Literal["Battery state is below route requirement with safety buffer"]


class RouteRisk(WireModel):
    route_id: Identifier
    vehicle_id: Identifier
    risk: Literal[
        "maintenanceHold",
        "vehicleUnavailable",
        "energyRequirementUnachievable",
        "batteryShortfall",
        "noFeasibleCharger",
    ]


class Decision(WireModel):
    recommendation: Literal["noAction", "rebalanceCharging", "unableToSchedule"]
    assignments: list[Assignment]
    route_risks: list[RouteRisk]
    evidence: list[Identifier]


class ReviewResponse(Decision):
    depot_id: Identifier
    delivery_wave_id: Identifier
    reviewed_at: Timestamp
    audit_id: Identifier
    decision_hash: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


Policy = DepotPolicy
Wave = DeliveryWave
