"""Run actual-model/feed/output CRUD verification against an owned emulator."""

import argparse
import json
import os
import traceback
from dataclasses import replace

import httpx

from app.settings import Settings
from scripts.ci import run_phase
from scripts.emulator import ROOT, Emulator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument("--review-timeout", type=int, default=300)
    args = parser.parse_args()
    try:
        artifacts = ROOT / ".artifacts"
        artifacts.mkdir(exist_ok=True)
        for name in (
            "ollama-results.xml",
            "ollama-review-output.json",
            "ollama-report.md",
            "ollama-inference.json",
        ):
            (artifacts / name).unlink(missing_ok=True)
        defaults = Settings.from_env()
        settings = replace(
            defaults,
            ollama_model=args.model if args.model is not None else defaults.ollama_model,
            timeout_seconds=args.review_timeout,
        )
        url = settings.ollama_endpoint.removesuffix("/").removesuffix("/v1")
        with httpx.Client(timeout=10, trust_env=False) as http:
            response = http.post(f"{url}/api/show", json={"model": settings.ollama_model})
            response.raise_for_status()
            metadata = response.json()
            if "completion" not in metadata.get("capabilities", []) or metadata.get("remote_host"):
                raise ValueError("The installed model must support local chat completion")
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
        (artifacts / "ollama-model.json").write_text(
            json.dumps(installed, indent=2), encoding="utf-8"
        )
        print(f"[ollama] Testing installed model {settings.ollama_model}", flush=True)
        with Emulator(log_path=artifacts / "ollama-emulator.log") as emulator:
            env = os.environ.copy()
            env.update(
                COSMOS_ENDPOINT=emulator.endpoint,
                COSMOS_READY_URL=emulator.ready_url,
                AGENT_MODEL_MODE="ollama",
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
                    "--capture=tee-sys",
                    "--ollama-review-timeout",
                    str(args.review_timeout),
                    str(ROOT / "tests" / "live"),
                    "--junitxml=.artifacts/ollama-results.xml",
                ],
                timeout=2 * args.review_timeout + 820,
                env=env,
            )
    except Exception:
        traceback.print_exc()
        return 1
    print("[ollama] Live model, seeded data and output CRUD passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
