"""Direct tool/SDK component setup; never invokes or substitutes for an agent."""

import httpx

from app.api import create_app
from app.schemas import ReviewResponse
from app.tools import ReviewTools

REQUEST = {"depotId": "SEA-01", "deliveryWaveId": "wave-2026-10-19-1400"}


async def run_tool_review(repo, request, settings):
    tools = ReviewTools(repo, request, settings)
    await tools.get_depot_policy(request.depot_id)
    wave = await tools.get_delivery_wave(request.depot_id, request.delivery_wave_id)
    routes = await tools.get_route_requirements(request.depot_id, sorted(wave["routeIds"]))
    vehicle_ids = sorted(route["assignedVehicleId"] for route in routes)
    vehicles = await tools.get_vehicle_status(request.depot_id, vehicle_ids)
    await tools.get_latest_telemetry(vehicle_ids)
    result = await tools.find_available_chargers(
        request.depot_id,
        sorted({vehicle["connectorType"] for vehicle in vehicles}),
        settings.review_at,
        wave["startTime"],
    )
    saved = await tools.write_charging_recommendation(
        request.depot_id, request.delivery_wave_id, result["decision"]
    )
    return ReviewResponse.model_validate(saved), tools


async def call_api(client, settings, payload=REQUEST):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, client)), base_url="http://test"
    ) as http:
        return await http.post("/agent/review-delivery-wave", json=payload)
