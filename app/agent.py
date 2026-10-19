import asyncio
import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from agent_framework import (
    Agent,
    BaseChatClient,
    FunctionInvocationContext,
    FunctionMiddleware,
    FunctionTool,
)

from app.cosmos_repository import CosmosRepository
from app.model_client import model_client
from app.schemas import ReviewRequest, ReviewResponse
from app.scripted_model_client import ScriptedModelClient
from app.settings import Settings
from app.tools import TOOL_NAMES, ReviewTools

logger = logging.getLogger(__name__)


async def review_wave(
    repository: CosmosRepository,
    request: ReviewRequest,
    settings: Settings,
    model: BaseChatClient | None = None,
) -> tuple[ReviewResponse, ReviewTools]:
    tools = ReviewTools(repository, request, settings)

    def guarded(function: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(function)
        async def invoke(*args: Any, **kwargs: Any) -> Any:
            previous_calls = len(tools.calls)
            try:
                result = await function(*args, **kwargs)
                tools.calls[-1]["status"] = "success"
                return result
            except Exception as exc:
                # The framework may serialize tool failures; retain the original for API mapping.
                tools.error = exc
                if len(tools.calls) > previous_calls:
                    tools.calls[-1]["status"] = "error"
                raise

        return invoke

    registered = [
        FunctionTool(
            name=name,
            description=getattr(tools, name).__doc__ or name,
            func=guarded(getattr(tools, name)),
        )
        for name in TOOL_NAMES
    ]

    class OrderedToolExposure(FunctionMiddleware):
        async def process(
            self,
            context: FunctionInvocationContext,
            call_next: Callable[[], Awaitable[None]],
        ) -> None:
            await call_next()
            if context.tools is None:
                raise ValueError("Model run has no mutable tool context")
            context.tools[:] = registered[len(tools.calls) : len(tools.calls) + 1]

    try:
        async with asyncio.timeout(settings.timeout_seconds):
            async with model_client(settings, request, model) as client:
                agent = Agent(
                    client,
                    name="FleetCharge",
                    instructions=(
                        "Review the requested wave using exactly seven tool calls, one at a "
                        "time, in this order: get_depot_policy, get_delivery_wave, "
                        "get_route_requirements, get_vehicle_status, get_latest_telemetry, "
                        "find_available_chargers, write_charging_recommendation. "
                        "Use the request's depotId and deliveryWaveId. Derive sorted routeIds "
                        "from the wave, sorted vehicleIds from assignedVehicleId in routes, "
                        "and sorted unique connectorTypes from vehicles. "
                        f"For startAfter use {settings.review_at}; for endBefore use the "
                        "wave's startTime. Pass the complete decision object returned by "
                        "find_available_chargers unchanged to write_charging_recommendation. "
                        "After the write, return its complete JSON object unchanged, with "
                        "no markdown or commentary. Never invent data or repeat tools."
                    ),
                    tools=registered[:1] if settings.mode == "ollama" else registered,
                    middleware=[OrderedToolExposure()] if settings.mode == "ollama" else [],
                    default_options={
                        "allow_multiple_tool_calls": False,
                        "temperature": 0,
                        "tool_choice": "required" if settings.mode == "ollama" else "auto",
                    },
                )
                response = await agent.run(
                    (
                        f"Review depotId {request.depot_id}, deliveryWaveId "
                        f"{request.delivery_wave_id}. Begin with get_depot_policy using "
                        f'depotId="{request.depot_id}".'
                        if settings.mode == "ollama"
                        else json.dumps(
                            {
                                "depotId": request.depot_id,
                                "deliveryWaveId": request.delivery_wave_id,
                            }
                        )
                    ),
                    session=agent.create_session(),
                )
                if tools.error is not None:
                    raise tools.error
                if tools.persisted is None or len(tools.calls) != 7:
                    raise ValueError("Agent ended without the complete acknowledged tool sequence")
                if isinstance(client, ScriptedModelClient) and client.turn != 8:
                    raise ValueError("Unexpected scripted turn count")
                terminal = ReviewResponse.model_validate_json(response.text)
                if terminal != tools.persisted:
                    raise ValueError(
                        "Terminal model response does not match persisted recommendation"
                    )
                return terminal, tools
    except Exception as exc:
        logger.exception(
            "Review failed depot=%s wave=%s tool=%s write_started=%s persisted=%s exception=%s",
            request.depot_id,
            request.delivery_wave_id,
            tools.calls[-1]["name"] if tools.calls else None,
            tools.write_started,
            tools.persisted is not None,
            type(exc).__name__,
        )
        if tools.error is not None:
            raise tools.error from exc
        raise
