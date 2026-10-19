"""Deterministic model responses; function dispatch remains inside Agent Framework."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatResponse,
    Content,
    FunctionInvocationLayer,
    Message,
)


class ScriptedModelClient(FunctionInvocationLayer, BaseChatClient):
    def __init__(self, depot_id: str, wave_id: str, review_at: str) -> None:
        super().__init__(
            function_invocation_configuration={
                "max_iterations": 20,
                "max_function_calls": 7,
                "allow_concurrent_invocation": False,
                "terminate_on_unknown_calls": True,
            }
        )
        self.depot_id = depot_id
        self.wave_id = wave_id
        self.review_at = review_at
        self.turn = 0
        self.wave: dict[str, Any] = {}
        self.vehicles: list[dict[str, Any]] = []
        self.vehicle_ids: list[str] = []

    def next_call(self, result: Any) -> tuple[str, dict[str, Any]] | None:
        depot = {"depotId": self.depot_id}
        match self.turn:
            case 0:
                return "get_depot_policy", depot
            case 1:
                return "get_delivery_wave", {**depot, "deliveryWaveId": self.wave_id}
            case 2:
                self.wave = result
                return "get_route_requirements", {**depot, "routeIds": sorted(result["routeIds"])}
            case 3:
                self.vehicle_ids = sorted(r["assignedVehicleId"] for r in result)
                return "get_vehicle_status", {**depot, "vehicleIds": self.vehicle_ids}
            case 4:
                self.vehicles = result
                return "get_latest_telemetry", {"vehicleIds": self.vehicle_ids}
            case 5:
                return "find_available_chargers", {
                    **depot,
                    "connectorTypes": sorted({v["connectorType"] for v in self.vehicles}),
                    "startAfter": self.review_at,
                    "endBefore": self.wave["startTime"],
                }
            case 6:
                return "write_charging_recommendation", {
                    **depot,
                    "deliveryWaveId": self.wave_id,
                    "decision": result["decision"],
                }
            case 7:
                return None
            case _:
                raise ValueError("Unexpected scripted turn")

    async def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> ChatResponse:
        if stream:
            raise ValueError("The demo supports non-streaming reviews only")
        if self.turn >= 20:
            raise ValueError("Model turn limit exceeded")
        result: Any = None
        if self.turn:
            results = [
                content
                for message in messages
                for content in message.contents
                if content.type == "function_result"
            ]
            if len(results) != self.turn or results[-1].call_id != f"call-{self.turn - 1}":
                raise ValueError("Unexpected tool result count or call ID")
            content = results[-1]
            if content.exception:
                raise ValueError("Tool failed; refusing to continue the model script")
            result = content.result
            if isinstance(result, str):
                result = json.loads(result)
        call = self.next_call(result)
        if call is None:
            content = Content.from_text(json.dumps(result, sort_keys=True))
        else:
            name, arguments = call
            content = Content.from_function_call(f"call-{self.turn}", name, arguments=arguments)
        self.turn += 1
        return ChatResponse(messages=Message("assistant", [content]))
