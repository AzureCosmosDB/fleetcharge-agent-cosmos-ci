from copy import deepcopy

import pytest
from azure.cosmos.exceptions import (
    CosmosResourceExistsError,
    CosmosResourceNotFoundError,
)

from app.agent import review_wave
from app.schemas import ReviewRequest


async def test_seeded_agent_output_audit_crud_and_recreation(store):
    _, settings, repo = store
    request = ReviewRequest(depotId="SEA-01", deliveryWaveId="wave-2026-10-19-1400")
    result, _ = await review_wave(repo, request, settings)
    container = repo.database.get_container_client("recommendations")
    stored = await container.read_item(result.audit_id, partition_key=request.depot_id)
    payload = result.model_dump(mode="json", by_alias=True)
    assert stored["payload"] == payload
    assert stored["payload"]["assignments"][0]["durationMinutes"] == 11
    with pytest.raises(CosmosResourceExistsError):
        await container.create_item(stored)

    replaced = await container.replace_item(
        stored["id"], {**stored, "reviewNote": "Checked against seeded data"}
    )
    assert replaced["payload"] == payload
    assert (await container.read_item(stored["id"], partition_key=request.depot_id))[
        "reviewNote"
    ] == "Checked against seeded data"
    await container.upsert_item({**replaced, "reviewNote": "Updated review note"})

    async def audits():
        return await repo.query(
            "recommendations",
            "SELECT * FROM c WHERE c.depotId = @depot AND c.id = @id",
            [
                {"name": "@depot", "value": request.depot_id},
                {"name": "@id", "value": result.audit_id},
            ],
            request.depot_id,
        )

    found = await audits()
    assert len(found) == 1
    assert found[0]["reviewNote"] == "Updated review note"
    assert found[0]["payload"] == payload
    await container.delete_item(result.audit_id, partition_key=request.depot_id)
    with pytest.raises(CosmosResourceNotFoundError):
        await container.read_item(result.audit_id, partition_key=request.depot_id)
    assert await audits() == []

    recreated, _ = await review_wave(repo, request, settings)
    assert recreated == result
    found = await audits()
    assert len(found) == 1
    assert found[0]["payload"] == payload
    assert "reviewNote" not in found[0]


async def test_seeded_point_reads_and_queries_are_partition_scoped(store):
    _, _, repo = store
    sea = await repo.read("chargers", "charger-fast-03", "SEA-01")
    pdx = await repo.read("chargers", "charger-fast-03", "PDX-02")
    assert sea["maxKw"] == 150
    assert pdx["maxKw"] == 350
    assert sea["id"] == pdx["id"]

    available = await repo.query(
        "chargers",
        "SELECT * FROM c WHERE c.depotId = @depot AND c.status = @status",
        [
            {"name": "@depot", "value": "SEA-01"},
            {"name": "@status", "value": "available"},
        ],
        "SEA-01",
    )
    assert [(c["id"], c["depotId"], c["maxKw"]) for c in available] == [
        ("charger-fast-03", "SEA-01", 150)
    ]
    assert (
        await repo.query(
            "chargers",
            "SELECT * FROM c WHERE c.depotId = @depot",
            [{"name": "@depot", "value": "PDX-02"}],
            "SEA-01",
        )
        == []
    )


async def test_create_replace_upsert_query_and_delete_seed_derived_document(store):
    _, _, repo = store
    container = repo.database.get_container_client("chargers")
    seed = await container.read_item("charger-fast-03", partition_key="SEA-01")
    document = {key: value for key, value in deepcopy(seed).items() if not key.startswith("_")}
    document.update(id="charger-crud", chargerId="charger-crud")

    created = await container.create_item(document)
    assert created["id"] == "charger-crud"
    assert created["maxKw"] == 150
    with pytest.raises(CosmosResourceExistsError):
        await container.create_item(document)
    with pytest.raises(CosmosResourceNotFoundError):
        await container.read_item(document["id"], partition_key="PDX-02")

    other = await container.create_item({**document, "depotId": "PDX-02", "maxKw": 350})
    read = await container.read_item(document["id"], partition_key="SEA-01")
    assert read["maxKw"] == 150
    replaced = await container.replace_item(read["id"], {**document, "maxKw": 75})
    assert replaced["maxKw"] == 75
    assert replaced["_etag"] != read["_etag"]
    assert (await container.read_item(read["id"], partition_key="SEA-01"))["maxKw"] == 75

    await container.upsert_item({**document, "maxKw": 100, "status": "occupied"})
    found = await repo.query(
        "chargers",
        "SELECT * FROM c WHERE c.depotId = @depot AND c.id = @id AND c.status = @status",
        [
            {"name": "@depot", "value": "SEA-01"},
            {"name": "@id", "value": document["id"]},
            {"name": "@status", "value": "occupied"},
        ],
        "SEA-01",
    )
    assert len(found) == 1
    assert found[0]["maxKw"] == 100
    assert (await container.read_item(other["id"], partition_key="PDX-02"))["maxKw"] == 350
    await container.delete_item(document["id"], partition_key="SEA-01")
    with pytest.raises(CosmosResourceNotFoundError):
        await container.read_item(document["id"], partition_key="SEA-01")
    assert (
        await repo.query(
            "chargers",
            "SELECT * FROM c WHERE c.depotId = @depot AND c.id = @id",
            [
                {"name": "@depot", "value": "SEA-01"},
                {"name": "@id", "value": document["id"]},
            ],
            "SEA-01",
        )
        == []
    )
    assert (await container.read_item(other["id"], partition_key="PDX-02"))["maxKw"] == 350

    await container.upsert_item(document)
    assert (await container.read_item(document["id"], partition_key="SEA-01"))["maxKw"] == 150
    await container.delete_item(document["id"], partition_key="SEA-01")
    with pytest.raises(CosmosResourceNotFoundError):
        await container.delete_item(document["id"], partition_key="SEA-01")
    assert (await container.read_item(seed["id"], partition_key="SEA-01"))["maxKw"] == 150
