import asyncio
import json
import time
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from agent_framework import ChatResponse
from agent_framework.openai import OpenAIChatCompletionClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.api import create_app
from app.fleet_rules import canonical_hash
from app.schemas import ReviewResponse

REQUEST = {"depotId": "SEA-01", "deliveryWaveId": "wave-2026-10-19-1400"}


async def test_real_agent_grounded_counts_and_output_crud(store, request, monkeypatch):
    client, settings, repo = store
    settings = replace(
        settings, mode="ollama", timeout_seconds=request.config.getoption("--ollama-review-timeout")
    )
    app = create_app(settings, client)
    golden = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "expected-golden.json").read_text()
    )
    container = repo.database.get_container_client("recommendations")
    evidence = {
        "request": REQUEST,
        "reviews": [],
        "questions": [],
        "dispatch": [],
        "checks": [],
        "completed": False,
    }
    output = Path(__file__).parents[2] / ".artifacts" / "ollama-review-output.json"
    output.parent.mkdir(exist_ok=True)
    transcript = []
    transcript_path = output.with_name("ollama-inference.json")
    original = OpenAIChatCompletionClient._inner_get_response

    async def observed_inference(self, *, messages, options, stream=False, **kwargs):
        assert not stream, "The live test requires inspectable non-streaming responses"
        started = time.monotonic()
        item = {
            "call": len(transcript) + 1,
            "messages": [{"role": message.role, "text": message.text} for message in messages],
            "completed": False,
        }
        transcript.append(item)

        def save_transcript():
            transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")

        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                print(
                    f"[ollama] call {item['call']} still running "
                    f"({time.monotonic() - started:.0f}s)",
                    flush=True,
                )

        save_transcript()
        print(f"[ollama] starting real inference call {item['call']}", flush=True)
        progress = asyncio.create_task(heartbeat())
        try:
            response = await original(
                self, messages=messages, options=options, stream=False, **kwargs
            )
            assert isinstance(response, ChatResponse)
            assert response.model == settings.ollama_model
            assert response.response_id
            item.update(
                completed=True,
                model=response.model,
                responseId=response.response_id,
                rawResponse="".join(message.text for message in response.messages),
                usageDetails=response.usage_details,
                durationSeconds=round(time.monotonic() - started, 3),
            )
            print(
                f"[ollama] completed call {item['call']} "
                f"in {item['durationSeconds']}s model={response.model}",
                flush=True,
            )
            return response
        finally:
            progress.cancel()
            with suppress(asyncio.CancelledError):
                await progress
            save_transcript()

    monkeypatch.setattr(OpenAIChatCompletionClient, "_inner_get_response", observed_inference)

    def save_evidence():
        output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    def record_response(scenario, response, expected, comparison, bucket="reviews", body=REQUEST):
        actual = response.json()
        matches = (
            actual == expected
            if comparison == "exact JSON"
            else all(
                sorted(actual.get(key, [])) == value
                if key == "vehicleIds"
                else actual.get(key) == value
                for key, value in expected.items()
            )
        )
        evidence[bucket].append(
            {
                "scenario": scenario,
                "status": response.status_code,
                "comparison": comparison,
                "matchesExpected": matches,
                "expected": expected,
                "actual": actual,
                "request": body,
            }
        )
        save_evidence()

    save_evidence()

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
        dispatch_question = {
            "depotId": "SEA-01",
            "question": "Where should drivers collect dispatch paperwork? "
            "Include the update reference.",
        }

        async def verify_dispatch(bay, update_id):
            stored = await repo.read("dispatchUpdates", "current-dispatch", "SEA-01")
            assert stored["pickupBay"] == bay and stored["updateId"] == update_id
            response = await http.post("/agent/ask-dispatch", json=dispatch_question)
            record_response(
                f"Stored dispatch update {update_id} directs drivers to {bay}",
                response,
                {"pickupBay": bay, "updateId": update_id},
                "exact bay/reference plus literal evidence in generated sentence",
                bucket="dispatch",
                body=dispatch_question,
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["pickupBay"] == bay and result["updateId"] == update_id
            assert bay in result["answer"] and update_id in result["answer"]
            context = json.loads(transcript[-1]["messages"][-1]["text"])
            assert context["dispatchUpdate"]["pickupBay"] == bay
            assert context["dispatchUpdate"]["updateId"] == update_id
            assert context["dispatchUpdate"]["depotId"] == "SEA-01"
            assert context["question"] == dispatch_question["question"]
            print(f"[dispatch answer] {result['answer']}", flush=True)

        await verify_dispatch("BAY-2", "dispatch-001")
        feed = {"depotId": "SEA-01", "updateId": "dispatch-007", "pickupBay": "BAY-7"}
        receipt = await http.post("/feeds/dispatch-updates", json=feed)
        assert receipt.status_code == 200, receipt.text
        assert all(receipt.json()[key] == value for key, value in feed.items())
        assert (await repo.read("dispatchUpdates", "current-dispatch", "PDX-02"))[
            "pickupBay"
        ] == "BAY-99"
        await verify_dispatch("BAY-7", "dispatch-007")
        evidence["checks"].append(
            "Feed API stored BAY-7/dispatch-007 in SEA-01 only; independent SDK reads, "
            "actual provider context and generated answers verified before and after update"
        )
        save_evidence()
        question = {
            "depotId": "SEA-01",
            "question": "How many vehicles are stored for this depot? List their vehicle IDs.",
        }
        expected_ids = ["van-042", "van-088", "van-099"]

        async def verify_count(ids):
            response = await http.post("/agent/ask-vehicles", json=question)
            record_response(
                f"Database contains {len(ids)} vehicles",
                response,
                {"vehicleCount": len(ids), "vehicleIds": ids},
                "count and IDs from independently verified SDK records",
                bucket="questions",
                body=question,
            )
            assert response.status_code == 200, response.text
            answer = response.json()
            assert answer["vehicleCount"] == len(ids)
            assert sorted(answer["vehicleIds"]) == ids
            assert str(len(ids)) in answer["answer"]
            print(f"[grounded answer] {answer['answer']}", flush=True)

        vehicles = repo.database.get_container_client("vehicles")
        actual = [
            item
            async for item in vehicles.query_items(
                "SELECT * FROM c WHERE c.depotId = @depot",
                parameters=[{"name": "@depot", "value": "SEA-01"}],
                partition_key="SEA-01",
            )
        ]
        assert sorted(item["vehicleId"] for item in actual) == expected_ids
        await verify_count(expected_ids)
        source = await vehicles.read_item("vehicle-van-042", partition_key="SEA-01")
        await vehicles.create_item(
            {
                **{key: value for key, value in source.items() if not key.startswith("_")},
                "id": "vehicle-van-150",
                "vehicleId": "van-150",
                "batteryPercent": 50,
                "assignedRouteId": None,
            }
        )
        assert (await vehicles.read_item("vehicle-van-150", partition_key="SEA-01"))[
            "batteryPercent"
        ] == 50
        expected_ids = [*expected_ids, "van-150"]
        await verify_count(expected_ids)
        evidence["checks"].append(
            "Actual model counted 3 then 4 after a real SDK vehicle insertion"
        )
        save_evidence()
        print("[crud] verifying real agent recommendation and persisted output", flush=True)
        response = await http.post("/agent/review-delivery-wave", json=REQUEST)
        record_response("Seeded battery at 58 percent", response, golden, "exact JSON")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result == golden
        created = await container.read_item(result["auditId"], partition_key="SEA-01")
        assert created["payload"] == result
        assert [item["payload"] for item in await audits()] == [result]
        for source_evidence in created["evidenceRecords"]:
            source = await repo.read(
                source_evidence["container"],
                source_evidence["id"],
                source_evidence["partitionKey"],
            )
            assert source["depotId"] == REQUEST["depotId"]
        with pytest.raises(CosmosResourceNotFoundError):
            await container.read_item(result["auditId"], partition_key="PDX-02")
        evidence["checks"].append("Seeded audit read/query, evidence ownership and wrong partition")
        save_evidence()

        telemetry = repo.database.get_container_client("telemetry")
        source = await telemetry.read_item("telemetry-van-042-latest", partition_key="van-042")
        await telemetry.replace_item(source["id"], {**source, "batteryPercent": 90})
        assert (await telemetry.read_item(source["id"], partition_key="van-042"))[
            "batteryPercent"
        ] == 90
        print("[crud] updated telemetry; starting second actual agent review", flush=True)
        response = await http.post("/agent/review-delivery-wave", json=REQUEST)
        record_response(
            "Latest battery telemetry updated to 90 percent",
            response,
            {
                "recommendation": "noAction",
                "assignments": [],
                "routeRisks": [],
                "auditId": result["auditId"],
            },
            "required fields plus independent hash and persistence assertions",
        )
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
        evidence["checks"].append(
            "Updated audit read/query, stable identity and changed decision/input hashes"
        )
        save_evidence()

        await container.delete_item(updated["auditId"], partition_key="SEA-01")
        with pytest.raises(CosmosResourceNotFoundError):
            await container.read_item(updated["auditId"], partition_key="SEA-01")
        assert await audits() == []
        evidence["checks"].append("Audit deletion, independent not-found read and empty query")
        evidence["completed"] = True
        assert len(transcript) == 20 and all(item["completed"] for item in transcript)
        print("[crud] deletion verified; all 20 real inference calls completed", flush=True)
        save_evidence()
