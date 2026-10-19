import asyncio
import logging

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.settings import Settings


async def cleanup(client: CosmosClient, settings: Settings) -> None:
    # Settings validates loopback endpoints and the owned demo/test database prefix.
    try:
        await client.delete_database(settings.database)
    except CosmosResourceNotFoundError:
        logging.getLogger(__name__).info("Database already absent: %s", settings.database)


async def main() -> None:
    settings = Settings.from_env()
    async with CosmosClient(settings.endpoint, credential=settings.key) as client:
        await cleanup(client, settings)
    print(f"Removed isolated emulator database {settings.database}")


if __name__ == "__main__":
    asyncio.run(main())
