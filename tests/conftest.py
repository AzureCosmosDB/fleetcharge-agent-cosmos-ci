import os
from dataclasses import replace
from uuid import uuid4

import pytest
from azure.cosmos.aio import CosmosClient

from app.cosmos_repository import CosmosRepository
from app.settings import Settings
from scripts.cleanup_cosmos import cleanup
from scripts.seed_cosmos import seed


def pytest_addoption(parser):
    parser.addoption("--ollama", action="store_true", help="Include actual local-model tests")


def pytest_ignore_collect(collection_path, config):
    return collection_path.name == "live" and not config.getoption("--ollama")


@pytest.fixture
async def store():
    if "COSMOS_ENDPOINT" not in os.environ:
        pytest.fail("Integration tests require the real emulator. Run: uv run python -m scripts.ci")
    settings = replace(Settings.from_env(), database=f"fleetchargetest-{uuid4().hex}")
    async with CosmosClient(settings.endpoint, credential=settings.key) as client:
        try:
            await seed(client, settings)
            yield client, settings, CosmosRepository(client, settings)
        finally:
            await cleanup(client, settings)
