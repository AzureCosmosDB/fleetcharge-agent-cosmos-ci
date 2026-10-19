from app.cosmos_repository import PARTITIONS


async def test_real_sdk_partitions_queries_upsert_readback(store):
    _, _, repo = store
    for name, partition in PARTITIONS.items():
        properties = await repo.database.get_container_client(name).read()
        assert properties["partitionKey"]["paths"] == [f"/{partition}"]
    sea = await repo.read("chargers", "charger-fast-03", "SEA-01")
    pdx = await repo.read("chargers", "charger-fast-03", "PDX-02")
    assert sea["depotId"] != pdx["depotId"] and sea["id"] == pdx["id"]
    assert all(c["depotId"] == "SEA-01" for c in await repo.chargers("SEA-01"))
    audit = {"id": "smoke", "depotId": "SEA-01", "value": 1}
    await repo.upsert(audit)
    audit["value"] = 2
    await repo.upsert(audit)
    assert (await repo.read("recommendations", "smoke", "SEA-01"))["value"] == 2
