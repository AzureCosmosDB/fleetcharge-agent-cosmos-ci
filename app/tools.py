from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError

from app.cosmos_repository import CosmosRepository
from app.fleet_rules import SourceDataError, canonical_hash, compute_decision
from app.schemas import (
    Charger,
    Decision,
    Policy,
    ReviewRequest,
    ReviewResponse,
    Route,
    Telemetry,
    Vehicle,
    Wave,
)
from app.settings import Settings

TOOL_NAMES = (
    "get_depot_policy",
    "get_delivery_wave",
    "get_route_requirements",
    "get_vehicle_status",
    "get_latest_telemetry",
    "find_available_chargers",
    "write_charging_recommendation",
)


def parse_document[ModelT: BaseModel](model: type[ModelT], raw: dict[str, Any]) -> ModelT:
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise SourceDataError(f"Invalid {model.__name__} source document.") from exc


def wire(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)


class ReviewTools:
    def __init__(
        self, repository: CosmosRepository, request: ReviewRequest, settings: Settings
    ) -> None:
        self.repository = repository
        self.request = request
        self.settings = settings
        self.policy: Policy | None = None
        self.wave: Wave | None = None
        self.routes: list[Route] = []
        self.vehicles: list[Vehicle] = []
        self.telemetry: list[Telemetry] = []
        self.chargers: list[Charger] = []
        self.decision: Decision | None = None
        self.persisted: ReviewResponse | None = None
        self.write_started = False
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None
        self.repository.wave_id = request.delivery_wave_id

    def enter(self, name: str, arguments: dict[str, Any]) -> None:
        if len(self.calls) >= len(TOOL_NAMES) or TOOL_NAMES[len(self.calls)] != name:
            raise ValueError("Unexpected, duplicate or reordered tool invocation")
        if "depotId" in arguments and arguments["depotId"] != self.request.depot_id:
            raise ValueError("Tool depot does not match request")
        if (
            "deliveryWaveId" in arguments
            and arguments["deliveryWaveId"] != self.request.delivery_wave_id
        ):
            raise ValueError("Tool wave does not match request")
        self.calls.append(
            {
                "name": name,
                "arguments": arguments,
                "callId": f"call-{len(self.calls)}",
                "status": "started",
            }
        )

    def owned(self, document: BaseModel) -> None:
        if getattr(document, "depot_id", None) != self.request.depot_id:
            raise SourceDataError("Source document belongs to another depot.")

    async def get_depot_policy(self, depotId: str) -> dict[str, Any]:
        """Read the requested depot's charging policy."""
        self.enter("get_depot_policy", {"depotId": depotId})
        self.policy = parse_document(
            Policy, await self.repository.read("depots", f"policy-{depotId}", depotId)
        )
        self.owned(self.policy)
        return wire(self.policy)

    async def get_delivery_wave(self, depotId: str, deliveryWaveId: str) -> dict[str, Any]:
        """Read the requested delivery wave."""
        self.enter("get_delivery_wave", {"depotId": depotId, "deliveryWaveId": deliveryWaveId})
        self.wave = parse_document(
            Wave, await self.repository.read("routes", deliveryWaveId, depotId)
        )
        self.owned(self.wave)
        if self.wave.start_time <= self.settings.clock:
            raise SourceDataError("Wave departure must be after review time.")
        return wire(self.wave)

    async def get_route_requirements(
        self, depotId: str, routeIds: list[str]
    ) -> list[dict[str, Any]]:
        """Read every route referenced by the wave."""
        self.enter("get_route_requirements", {"depotId": depotId, "routeIds": routeIds})
        if self.wave is None or routeIds != sorted(self.wave.route_ids):
            raise ValueError("Tool route IDs must exactly match the wave")
        self.routes = [
            parse_document(Route, await self.repository.read("routes", route_id, depotId))
            for route_id in routeIds
        ]
        for route in self.routes:
            self.owned(route)
            if route.delivery_wave_id != self.request.delivery_wave_id:
                raise SourceDataError("Route does not belong to the wave.")
        return [wire(route) for route in self.routes]

    async def get_vehicle_status(self, depotId: str, vehicleIds: list[str]) -> list[dict[str, Any]]:
        """Read the assigned vehicles and maintenance flags."""
        self.enter("get_vehicle_status", {"depotId": depotId, "vehicleIds": vehicleIds})
        if vehicleIds != sorted(r.assigned_vehicle_id for r in self.routes):
            raise ValueError("Tool vehicle IDs must exactly match assigned vehicles")
        self.vehicles = [
            parse_document(
                Vehicle, await self.repository.read("vehicles", f"vehicle-{vehicle_id}", depotId)
            )
            for vehicle_id in vehicleIds
        ]
        for vehicle in self.vehicles:
            self.owned(vehicle)
        return [wire(vehicle) for vehicle in self.vehicles]

    async def get_latest_telemetry(self, vehicleIds: list[str]) -> list[dict[str, Any]]:
        """Select fresh current telemetry, never vehicle battery summaries."""
        self.enter("get_latest_telemetry", {"vehicleIds": vehicleIds})
        if vehicleIds != sorted(v.vehicle_id for v in self.vehicles):
            raise ValueError("Telemetry IDs must exactly match the vehicles")
        if self.policy is None:
            raise ValueError("Policy has not been loaded")
        for vehicle_id in vehicleIds:
            readings = [
                parse_document(Telemetry, raw)
                for raw in await self.repository.telemetry(vehicle_id)
            ]
            for reading in readings:
                self.owned(reading)
                if reading.vehicle_id != vehicle_id:
                    raise SourceDataError("Telemetry vehicle ownership is inconsistent.")
            eligible = [r for r in readings if r.observed_at <= self.settings.clock]
            eligible.sort(key=lambda r: (-r.observed_at.timestamp(), r.id))
            if not eligible or self.settings.clock - eligible[0].observed_at > timedelta(
                minutes=self.policy.telemetry_max_age_minutes
            ):
                raise SourceDataError(
                    f"Latest valid telemetry is unavailable for vehicle {vehicle_id}."
                )
            self.telemetry.append(eligible[0])
        return [wire(reading) for reading in self.telemetry]

    async def find_available_chargers(
        self, depotId: str, connectorTypes: list[str], startAfter: str, endBefore: str
    ) -> dict[str, Any]:
        """Compute a validated decision from compatible, owned charger candidates."""
        self.enter(
            "find_available_chargers",
            {
                "depotId": depotId,
                "connectorTypes": connectorTypes,
                "startAfter": startAfter,
                "endBefore": endBefore,
            },
        )
        if self.wave is None or self.policy is None:
            raise ValueError("Missing source context")
        if (
            connectorTypes != sorted({v.connector_type for v in self.vehicles})
            or datetime.fromisoformat(startAfter) != self.settings.clock
            or datetime.fromisoformat(endBefore) != self.wave.start_time
        ):
            raise ValueError("Charger arguments do not match review context")
        self.chargers = [
            parse_document(Charger, raw) for raw in await self.repository.chargers(depotId)
        ]
        for charger in self.chargers:
            self.owned(charger)
        self.decision = compute_decision(
            self.policy,
            self.wave,
            self.routes,
            self.vehicles,
            self.telemetry,
            self.chargers,
            self.settings.clock,
        )
        return {"candidates": [wire(c) for c in self.chargers], "decision": wire(self.decision)}

    async def write_charging_recommendation(
        self, depotId: str, deliveryWaveId: str, decision: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the proposal and persist one deterministic audit identity."""
        self.enter(
            "write_charging_recommendation",
            {"depotId": depotId, "deliveryWaveId": deliveryWaveId, "decision": decision},
        )
        if self.decision is None or Decision.model_validate(decision) != self.decision:
            raise ValueError("Proposed decision does not match computed source-grounded decision")
        import hashlib

        audit_id = "review-" + hashlib.sha256(deliveryWaveId.encode("utf-8")).hexdigest()
        payload = {
            **wire(self.decision),
            "depotId": depotId,
            "deliveryWaveId": deliveryWaveId,
            "reviewedAt": self.settings.review_at,
            "auditId": audit_id,
        }
        response = ReviewResponse.model_validate({**payload, "decisionHash": "0" * 64})
        payload["decisionHash"] = canonical_hash(
            response.model_dump(by_alias=True, exclude={"decision_hash"})
        )
        response = ReviewResponse.model_validate(payload)
        sources = [
            r
            for r in self.repository.trace
            if r["id"] in self.decision.evidence
            and r["partitionKey"] in {depotId, *(v.vehicle_id for v in self.vehicles)}
        ]
        # Only selected telemetry/chargers count as evidence, not every queried candidate.
        unique = {(r["container"], r["id"], r["partitionKey"]): r for r in sources}
        versions = [unique[key] for key in sorted(unique)]
        input_data = [
            document.model_dump(by_alias=True)
            for document in [
                self.policy,
                self.wave,
                *self.routes,
                *self.vehicles,
                *self.telemetry,
                *(
                    c
                    for c in sorted(self.chargers, key=lambda c: c.id)
                    if c.id in self.decision.evidence
                ),
            ]
            if document is not None
        ]
        audit = {
            "id": audit_id,
            "depotId": depotId,
            "type": "chargingRecommendation",
            "deliveryWaveId": deliveryWaveId,
            "reviewedAt": self.settings.review_at,
            "rulesVersion": "fleetcharge-demo-v1",
            "decisionHash": payload["decisionHash"],
            "inputHash": canonical_hash(
                {
                    "documents": input_data,
                    "reviewedAt": self.settings.clock,
                    "rulesVersion": "fleetcharge-demo-v1",
                }
            ),
            "payload": wire(response),
            "sourceVersions": versions,
            "evidenceRecords": [
                {key: value for key, value in record.items() if key != "etag"}
                for record in versions
            ],
        }
        self.write_started = True
        stored = await self.repository.upsert(audit)
        self.persisted = ReviewResponse.model_validate(stored["payload"])
        return wire(self.persisted)
