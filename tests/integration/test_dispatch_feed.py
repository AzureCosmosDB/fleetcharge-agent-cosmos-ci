import httpx
import pytest

from app.api import create_app
from app.dispatch import read_dispatch
from app.fleet_rules import SourceDataError

FEED = {"depotId": "SEA-01", "updateId": "dispatch-007", "pickupBay": "BAY-7"}


async def test_feed_replaces_current_snapshot_in_only_the_requested_partition(store):
    client, settings, repo = store
    assert (await read_dispatch(repo, "SEA-01")).pickup_bay == "BAY-2"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, client)), base_url="http://test"
    ) as http:
        for _ in range(2):
            response = await http.post("/feeds/dispatch-updates", json=FEED)
            assert response.status_code == 200, response.text
            assert response.json() == {
                **FEED,
                "id": "current-dispatch",
                "type": "dispatchUpdate",
            }
    stored = await repo.read("dispatchUpdates", "current-dispatch", "SEA-01")
    assert stored["pickupBay"] == "BAY-7"
    assert stored["updateId"] == "dispatch-007"
    assert (await read_dispatch(repo, "PDX-02")).pickup_bay == "BAY-99"
    rows = await repo.query(
        "dispatchUpdates",
        "SELECT * FROM c WHERE c.depotId = @depot",
        [{"name": "@depot", "value": "SEA-01"}],
        "SEA-01",
    )
    assert len(rows) == 1


@pytest.mark.parametrize(
    "path,body",
    [
        ("/feeds/dispatch-updates", {**FEED, "pickupBay": "bad"}),
        ("/feeds/dispatch-updates", {**FEED, "extra": True}),
        ("/agent/ask-dispatch", {"depotId": "SEA-01", "question": ""}),
    ],
)
async def test_invalid_dispatch_requests_fail_before_inference(store, path, body):
    client, settings, repo = store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, client)), base_url="http://test"
    ) as http:
        response = await http.post(path, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalidRequest"
    assert (await read_dispatch(repo, "SEA-01")).pickup_bay == "BAY-2"


async def test_missing_dispatch_snapshot_fails_explicitly_without_inference(store):
    client, settings, repo = store
    await repo.database.get_container_client("dispatchUpdates").delete_item(
        "current-dispatch", partition_key="SEA-01"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, client)), base_url="http://test"
    ) as http:
        response = await http.post(
            "/agent/ask-dispatch", json={"depotId": "SEA-01", "question": "Where do I go?"}
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sourceDataInvalid"


async def test_malformed_dispatch_source_does_not_become_a_prompt(store):
    _, _, repo = store
    await repo.database.get_container_client("dispatchUpdates").upsert_item(
        {"id": "current-dispatch", "type": "dispatchUpdate", **FEED, "pickupBay": "invalid"}
    )
    with pytest.raises(SourceDataError):
        await read_dispatch(repo, "SEA-01")
