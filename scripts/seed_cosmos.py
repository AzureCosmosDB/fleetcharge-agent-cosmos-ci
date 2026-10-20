import asyncio
import json
from pathlib import Path

from azure.cosmos.aio import CosmosClient

from app.cosmos_repository import provision
from app.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


async def seed(client: CosmosClient, settings: Settings) -> None:
    await provision(client, settings)
    database = client.get_database_client(settings.database)
    for name in ("depots", "routes", "vehicles", "chargers", "telemetry", "dispatchUpdates"):
        for document in json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8")):
            await database.get_container_client(name).upsert_item(document)


async def main() -> None:
    settings = Settings.from_env()
    async with CosmosClient(settings.endpoint, credential=settings.key) as client:
        await seed(client, settings)
    print(f"Seeded isolated emulator database {settings.database}")


if __name__ == "__main__":
    asyncio.run(main())
