"""Run optional actual-model/output CRUD verification against an owned emulator."""

import argparse
import json
import os
import traceback

import httpx

from app.settings import Settings
from scripts.ci import run_phase
from scripts.emulator import ROOT, Emulator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", Settings.ollama_model))
    args = parser.parse_args()
    try:
        settings = Settings(
            mode="ollama",
            ollama_model=args.model,
            ollama_endpoint=os.environ.get("OLLAMA_ENDPOINT", Settings.ollama_endpoint),
            timeout_seconds=300,
        )
        url = settings.ollama_endpoint.removesuffix("/").removesuffix("/v1")
        with httpx.Client(timeout=10, trust_env=False) as http:
            response = http.post(f"{url}/api/show", json={"model": settings.ollama_model})
            response.raise_for_status()
            metadata = response.json()
            if "tools" not in metadata.get("capabilities", []) or metadata.get("remote_host"):
                raise ValueError("The installed model must support local tool calling")
            response = http.get(f"{url}/api/tags")
            response.raise_for_status()
            installed = next(
                (
                    item
                    for item in response.json()["models"]
                    if item["name"] == settings.ollama_model
                ),
                None,
            )
            if installed is None:
                raise ValueError("Select the exact tag of an installed local model")
        artifacts = ROOT / ".artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "ollama-model.json").write_text(
            json.dumps(installed, indent=2), encoding="utf-8"
        )
        print(f"[ollama] Testing installed model {settings.ollama_model}", flush=True)
        with Emulator(log_path=artifacts / "ollama-emulator.log") as emulator:
            env = os.environ.copy()
            env.update(
                COSMOS_ENDPOINT=emulator.endpoint,
                COSMOS_READY_URL=emulator.ready_url,
                AGENT_MODEL_MODE="scripted",
                OLLAMA_ENDPOINT=settings.ollama_endpoint,
                OLLAMA_MODEL=settings.ollama_model,
                FLEETCHARGE_TIMEOUT_SECONDS="60",
            )
            run_phase(
                "Actual LLM and persisted output CRUD",
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "pytest",
                    "--ollama",
                    str(ROOT / "tests" / "live"),
                    "--junitxml=.artifacts/ollama-results.xml",
                ],
                timeout=700,
                env=env,
            )
    except Exception:
        traceback.print_exc()
        return 1
    print("[ollama] Live model, seeded data and output CRUD passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
