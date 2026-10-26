"""Run one coding task's component checks against its own disposable emulator."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from app.settings import EMULATOR_KEY
from scripts.ci import run_phase
from scripts.emulator import ROOT, Emulator

TASKS = {
    "dispatch": (
        "tests/unit/test_dispatch.py",
        "tests/integration/test_dispatch_feed.py",
    ),
    "fleet-rules": (
        "tests/unit/test_fleet_rules.py",
        "tests/integration/test_delivery_wave_tools.py",
    ),
}


def run_task(task: str, artifacts: Path) -> dict[str, object]:
    targets = TASKS[task]
    artifacts.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    print(f"[agent-ci] Component task: {task}; no model or coding agent is invoked", flush=True)
    with Emulator(log_path=artifacts / "emulator.log") as emulator:
        environment = os.environ.copy()
        environment.update(
            COSMOS_ENDPOINT=emulator.endpoint,
            COSMOS_READY_URL=emulator.ready_url,
            COSMOS_DATABASE=f"fleetchargetest-agent-{task}",
            COSMOS_KEY=EMULATOR_KEY,
            AGENT_MODEL_MODE="ollama",
            FLEETCHARGE_TIMEOUT_SECONDS="60",
        )
        run_phase(
            f"Isolated {task} checks",
            [
                "uv",
                "run",
                "--no-sync",
                "pytest",
                *targets,
                f"--junitxml={artifacts / 'results.xml'}",
            ],
            timeout=600,
            env=environment,
        )
    emulator.verify_removed()
    report: dict[str, object] = {
        "kind": "component-task-check",
        "task": task,
        "tests": list(targets),
        "owned_container_removed": True,
        "total_seconds": round(time.monotonic() - started, 3),
    }
    (artifacts / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"[agent-ci] Passed; evidence: {artifacts}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=tuple(TASKS), required=True)
    args = parser.parse_args()
    run_task(args.task, ROOT / ".artifacts" / "agent-ci" / args.task / uuid4().hex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
