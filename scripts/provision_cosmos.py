import asyncio

from azure.cosmos.aio import CosmosClient

from app.cosmos_repository import provision
from app.settings import Settings


async def main() -> None:
    settings = Settings.from_env()
    async with CosmosClient(settings.endpoint, credential=settings.key) as client:
        await provision(client, settings)
    print(f"Provisioned isolated emulator database {settings.database}")


if __name__ == "__main__":
    asyncio.run(main())
