"""Prove two disposable coding-agent databases stay isolated; no model is invoked."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from azure.cosmos.aio import CosmosClient

from app.settings import Settings
from scripts.emulator import IMAGE, ROOT, Emulator
from scripts.seed_cosmos import seed

DATABASE = "fleetchargetest-agent-isolation"


class IsolationError(RuntimeError):
    """An isolation, fixture, or read-back invariant failed."""


@dataclass(frozen=True)
class Sandbox:
    name: str
    emulator: Emulator
    bay: str

    @property
    def settings(self) -> Settings:
        return Settings(endpoint=self.emulator.endpoint, database=DATABASE)

    @property
    def update_id(self) -> str:
        return f"{self.name}-dispatch"


def check_dispatch(
    document: Mapping[str, object], *, bay: str, update_id: str, depot: str = "SEA-01"
) -> None:
    expected = {
        "id": "current-dispatch",
        "depotId": depot,
        "pickupBay": bay,
        "updateId": update_id,
    }
    for field, value in expected.items():
        if document.get(field) != value:
            raise IsolationError(
                f"Dispatch {field}: expected {value!r}, received {document.get(field)!r}"
            )


def check_environments(sandboxes: tuple[Sandbox, Sandbox]) -> None:
    identifiers = {sandbox.emulator.container_id for sandbox in sandboxes}
    ports = {
        url.removesuffix("/ready")
        for sandbox in sandboxes
        for url in (sandbox.emulator.endpoint, sandbox.emulator.ready_url)
    }
    if None in identifiers or len(identifiers) != 2 or "" in ports or len(ports) != 4:
        raise IsolationError("Expected two owned containers and four distinct loopback ports")


async def read_dispatch(
    client: CosmosClient, sandbox: Sandbox, *, depot: str = "SEA-01"
) -> dict[str, Any]:
    return (
        await client.get_database_client(sandbox.settings.database)
        .get_container_client("dispatchUpdates")
        .read_item("current-dispatch", partition_key=depot)
    )


async def write_dispatch(client: CosmosClient, sandbox: Sandbox, document: dict[str, Any]) -> None:
    document.update(pickupBay=sandbox.bay, updateId=sandbox.update_id)
    container = client.get_database_client(DATABASE).get_container_client("dispatchUpdates")
    await container.upsert_item(document)


async def exercise_pair(sandboxes: tuple[Sandbox, Sandbox]) -> list[dict[str, object]]:
    async with (
        asyncio.timeout(120),
        CosmosClient(sandboxes[0].settings.endpoint, credential=sandboxes[0].settings.key) as first,
        CosmosClient(
            sandboxes[1].settings.endpoint, credential=sandboxes[1].settings.key
        ) as second,
    ):
        clients = (first, second)
        async with asyncio.TaskGroup() as group:
            for client, sandbox in zip(clients, sandboxes, strict=True):
                group.create_task(seed(client, sandbox.settings))

        documents = []
        for client, sandbox in zip(clients, sandboxes, strict=True):
            document = await read_dispatch(client, sandbox)
            check_dispatch(document, bay="BAY-2", update_id="dispatch-001")
            documents.append(
                {key: value for key, value in document.items() if not key.startswith("_")}
            )

        async with asyncio.TaskGroup() as group:
            for client, sandbox, document in zip(clients, sandboxes, documents, strict=True):
                group.create_task(write_dispatch(client, sandbox, document))

        results: list[dict[str, object]] = []
        for client, sandbox in zip(clients, sandboxes, strict=True):
            stored = await read_dispatch(client, sandbox)
            check_dispatch(stored, bay=sandbox.bay, update_id=sandbox.update_id)
            peer = await read_dispatch(client, sandbox, depot="PDX-02")
            check_dispatch(peer, bay="BAY-99", update_id="dispatch-099", depot="PDX-02")
            results.append(
                {
                    "agent": sandbox.name,
                    "container_id": sandbox.emulator.container_id,
                    "endpoint": sandbox.emulator.endpoint,
                    "ready_url": sandbox.emulator.ready_url,
                    "database": DATABASE,
                    "document_id": stored["id"],
                    "partition_key": stored["depotId"],
                    "pickup_bay": stored["pickupBay"],
                    "update_id": stored["updateId"],
                    "other_depot_unchanged": True,
                }
            )
        return results


async def check_surviving_peer(sandbox: Sandbox) -> None:
    async with (
        asyncio.timeout(30),
        CosmosClient(sandbox.settings.endpoint, credential=sandbox.settings.key) as client,
    ):
        stored = await read_dispatch(client, sandbox)
        check_dispatch(stored, bay=sandbox.bay, update_id=sandbox.update_id)


def run_proof(artifacts: Path) -> dict[str, object]:
    artifacts.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    startup_seconds: dict[str, float] = {}
    print("[isolation] Component proof only; no coding agent or application model runs", flush=True)
    with ExitStack() as stack:
        sandboxes = []
        for name, bay in (("agent-a", "BAY-7"), ("agent-b", "BAY-8")):
            beginning = time.monotonic()
            emulator = stack.enter_context(Emulator(log_path=artifacts / f"{name}.log"))
            startup_seconds[name] = round(time.monotonic() - beginning, 3)
            sandboxes.append(Sandbox(name, emulator, bay))
        pair = (sandboxes[0], sandboxes[1])
        check_environments(pair)
        print(
            "[isolation] Seed both environments, then write the same item concurrently", flush=True
        )
        results = asyncio.run(exercise_pair(pair))
        pair[0].emulator.close()
        pair[0].emulator.verify_removed()
        print("[isolation] Agent A removed; independently re-read agent B", flush=True)
        asyncio.run(check_surviving_peer(pair[1]))
    for sandbox in pair:
        sandbox.emulator.verify_removed()

    report: dict[str, object] = {
        "kind": "component-isolation-proof",
        "image": IMAGE,
        "startup_seconds": startup_seconds,
        "total_seconds": round(time.monotonic() - started, 3),
        "agents": results,
        "peer_survived_cleanup": True,
        "owned_containers_removed": True,
    }
    (artifacts / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"[isolation] Passed; evidence: {artifacts}", flush=True)
    return report


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    run_proof(ROOT / ".artifacts" / "agent-isolation" / uuid4().hex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
