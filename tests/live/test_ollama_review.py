import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.api import create_app
from app.fleet_rules import canonical_hash
from app.schemas import ReviewResponse

REQUEST = {"depotId": "SEA-01", "deliveryWaveId": "wave-2026-10-19-1400"}


async def test_local_llm_output_create_read_query_update_delete(store, request):
    client, settings, repo = store
    settings = replace(
        settings, mode="ollama", timeout_seconds=request.config.getoption("--ollama-review-timeout")
    )
    app = create_app(settings, client)
    golden = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "expected-golden.json").read_text()
    )
    container = repo.database.get_container_client("recommendations")

    async def audits():
        return [
            item
            async for item in container.query_items(
                "SELECT * FROM c WHERE c.depotId = @depot AND c.deliveryWaveId = @wave",
                parameters=[
                    {"name": "@depot", "value": REQUEST["depotId"]},
                    {"name": "@wave", "value": REQUEST["deliveryWaveId"]},
                ],
                partition_key="SEA-01",
            )
        ]

    assert await audits() == []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        timeout=settings.timeout_seconds + 10,
    ) as http:
        response = await http.post("/agent/review-delivery-wave", json=REQUEST)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result == golden
        created = await container.read_item(result["auditId"], partition_key="SEA-01")
        assert created["payload"] == result
        assert [item["payload"] for item in await audits()] == [result]
        for evidence in created["evidenceRecords"]:
            source = await repo.read(
                evidence["container"], evidence["id"], evidence["partitionKey"]
            )
            assert source["depotId"] == REQUEST["depotId"]
        with pytest.raises(CosmosResourceNotFoundError):
            await container.read_item(result["auditId"], partition_key="PDX-02")

        telemetry = repo.database.get_container_client("telemetry")
        source = await telemetry.read_item("telemetry-van-042-latest", partition_key="van-042")
        await telemetry.replace_item(source["id"], {**source, "batteryPercent": 90})
        assert (await telemetry.read_item(source["id"], partition_key="van-042"))[
            "batteryPercent"
        ] == 90
        response = await http.post("/agent/review-delivery-wave", json=REQUEST)
        assert response.status_code == 200, response.text
        updated = response.json()
        assert updated["recommendation"] == "noAction"
        assert updated["assignments"] == updated["routeRisks"] == []
        assert updated["auditId"] == result["auditId"]
        assert updated["decisionHash"] != result["decisionHash"]
        assert updated["decisionHash"] == canonical_hash(
            ReviewResponse.model_validate(updated).model_dump(
                by_alias=True, exclude={"decision_hash"}
            )
        )
        stored = await container.read_item(updated["auditId"], partition_key="SEA-01")
        assert stored["payload"] == updated
        assert stored["inputHash"] != created["inputHash"]
        assert [item["payload"] for item in await audits()] == [updated]

        await container.delete_item(updated["auditId"], partition_key="SEA-01")
        with pytest.raises(CosmosResourceNotFoundError):
            await container.read_item(updated["auditId"], partition_key="SEA-01")
        assert await audits() == []
