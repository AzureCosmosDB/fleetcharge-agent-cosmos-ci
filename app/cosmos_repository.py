import logging
from collections.abc import Mapping
from typing import Any

from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.settings import Settings

logger = logging.getLogger(__name__)
PARTITIONS = {
    "depots": "depotId",
    "routes": "depotId",
    "vehicles": "depotId",
    "chargers": "depotId",
    "telemetry": "vehicleId",
    "recommendations": "depotId",
}


class WaveNotFoundError(ValueError):
    pass


class CosmosRepository:
    def __init__(self, client: CosmosClient, settings: Settings) -> None:
        self.database = client.get_database_client(settings.database)
        self.settings = settings
        self.trace: list[dict[str, Any]] = []
        self.wave_id: str | None = None

    def record(self, container: str, document: Mapping[str, Any]) -> None:
        self.trace.append(
            {
                "container": container,
                "id": document["id"],
                "partitionKey": document[PARTITIONS[container]],
                "etag": document.get("_etag"),
            }
        )

    async def read(self, container: str, item_id: str, partition: str) -> dict[str, Any]:
        try:
            document: dict[str, Any] = await self.database.get_container_client(
                container
            ).read_item(item_id, partition_key=partition)
        except CosmosResourceNotFoundError as exc:
            logger.warning(
                "Missing source container=%s id=%s partition=%s", container, item_id, partition
            )
            if container == "routes" and item_id == getattr(self, "wave_id", None):
                raise WaveNotFoundError("Requested delivery wave was not found.") from exc
            from app.fleet_rules import SourceDataError

            raise SourceDataError(f"Required source document is unavailable: {item_id}.") from exc
        self.record(container, document)
        return document

    async def query(
        self, container: str, query: str, parameters: list[dict[str, Any]], partition: str
    ) -> list[dict[str, Any]]:
        items = self.database.get_container_client(container).query_items(
            query=query, parameters=parameters, partition_key=partition
        )
        result = [item async for item in items]
        for item in result:
            self.record(container, item)
        return result

    async def chargers(self, depot_id: str) -> list[dict[str, Any]]:
        return await self.query(
            "chargers",
            "SELECT * FROM c WHERE c.depotId = @depot",
            [{"name": "@depot", "value": depot_id}],
            depot_id,
        )

    async def telemetry(self, vehicle_id: str) -> list[dict[str, Any]]:
        return await self.query(
            "telemetry",
            "SELECT * FROM c WHERE c.vehicleId = @vehicle",
            [{"name": "@vehicle", "value": vehicle_id}],
            vehicle_id,
        )

    async def upsert(self, audit: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self.database.get_container_client(
            "recommendations"
        ).upsert_item(audit)
        return result


async def provision(client: CosmosClient, settings: Settings) -> None:
    database = await client.create_database_if_not_exists(settings.database)
    for name, partition in PARTITIONS.items():
        await database.create_container_if_not_exists(
            name, partition_key=PartitionKey(f"/{partition}")
        )
