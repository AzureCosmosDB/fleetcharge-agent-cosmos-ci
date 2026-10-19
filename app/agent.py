import asyncio
import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from agent_framework import Agent

from app.cosmos_repository import CosmosRepository
from app.schemas import ReviewRequest, ReviewResponse
from app.scripted_model_client import ScriptedModelClient
from app.settings import Settings
from app.tools import TOOL_NAMES, ReviewTools

logger = logging.getLogger(__name__)


async def review_wave(
    repository: CosmosRepository,
    request: ReviewRequest,
    settings: Settings,
    model: ScriptedModelClient | None = None,
) -> tuple[ReviewResponse, ReviewTools]:
    tools = ReviewTools(repository, request, settings)

    def guarded(function: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(function)
        async def invoke(*args: Any, **kwargs: Any) -> Any:
            try:
                result = await function(*args, **kwargs)
                tools.calls[-1]["status"] = "success"
                return result
            except Exception as exc:
                # The framework may serialize tool failures; retain the original for API mapping.
                tools.error = exc
                if tools.calls:
                    tools.calls[-1]["status"] = "error"
                raise

        return invoke

    client = model or ScriptedModelClient(
        request.depot_id, request.delivery_wave_id, settings.review_at
    )
    agent = Agent(
        client,
        name="FleetCharge",
        instructions="Review the requested wave using the registered data tools.",
        tools=[guarded(getattr(tools, name)) for name in TOOL_NAMES],
        default_options={"allow_multiple_tool_calls": False},
    )
    try:
        async with asyncio.timeout(settings.timeout_seconds):
            response = await agent.run(
                json.dumps(
                    {"depotId": request.depot_id, "deliveryWaveId": request.delivery_wave_id}
                ),
                session=agent.create_session(),
            )
            if tools.error is not None:
                raise tools.error
            if tools.persisted is None or len(tools.calls) != 7 or client.turn != 8:
                raise ValueError("Agent ended without the complete acknowledged tool sequence")
            terminal = ReviewResponse.model_validate_json(response.text)
            if terminal != tools.persisted:
                raise ValueError("Terminal model response does not match persisted recommendation")
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
