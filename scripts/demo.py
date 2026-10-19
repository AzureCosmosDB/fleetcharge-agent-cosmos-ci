"""One disposable emulator, seeded database and HTTP API; Ctrl+C cleans them up."""

import argparse
import asyncio
import json
import socket
from dataclasses import replace

import httpx
import uvicorn
from azure.cosmos.aio import CosmosClient

from app.api import create_app
from app.settings import Settings
from scripts.cleanup_cosmos import cleanup
from scripts.emulator import Emulator
from scripts.seed_cosmos import seed


async def serve(endpoint: str, port: int, smoke: bool) -> None:
    settings = replace(Settings.from_env(), endpoint=endpoint)
    async with CosmosClient(settings.endpoint, credential=settings.key) as client:
        try:
            await seed(client, settings)
            app = create_app(settings, client)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
                listener.listen(128)
                listener.setblocking(False)
                actual_port = listener.getsockname()[1]
                server = uvicorn.Server(uvicorn.Config(app, log_level="info"))
                task = asyncio.create_task(server.serve(sockets=[listener]))
                try:
                    async with asyncio.timeout(15):
                        while not server.started:
                            if task.done():
                                await task
                                raise RuntimeError("API exited before becoming ready")
                            await asyncio.sleep(0.05)
                    url = f"http://127.0.0.1:{actual_port}/agent/review-delivery-wave"
                    print(f"POST {url}", flush=True)
                    if smoke:
                        async with httpx.AsyncClient(timeout=settings.timeout_seconds + 10) as http:
                            response = await http.post(
                                url,
                                json={
                                    "depotId": "SEA-01",
                                    "deliveryWaveId": "wave-2026-10-19-1400",
                                },
                            )
                            response.raise_for_status()
                            result = response.json()
                            if result["assignments"][0]["durationMinutes"] != 11:
                                raise AssertionError("Unexpected golden charging result")
                            audit = (
                                await client.get_database_client(settings.database)
                                .get_container_client("recommendations")
                                .read_item(result["auditId"], partition_key="SEA-01")
                            )
                            if audit["payload"] != result:
                                raise AssertionError("HTTP response differs from stored audit")
                            print(json.dumps(result, indent=2))
                            print("PASS: real HTTP 200 and independent SDK audit read-back")
                    else:
                        print(
                            "Open /docs on the same host/port. Ctrl+C stops this demo.", flush=True
                        )
                        await task
                finally:
                    server.should_exit = True
                    await asyncio.wait_for(task, timeout=15)
        finally:
            await cleanup(client, settings)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Verify HTTP/audit then exit")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with Emulator() as emulator:
        asyncio.run(serve(emulator.endpoint, 0 if args.smoke else args.port, args.smoke))


if __name__ == "__main__":
    main()
