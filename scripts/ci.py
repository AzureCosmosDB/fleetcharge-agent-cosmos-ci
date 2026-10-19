"""Run the same bounded quality and real-emulator checks locally and in CI."""

from __future__ import annotations

import os
import subprocess
import traceback

from scripts.emulator import ROOT, Emulator


def run_phase(
    label: str, command: list[str], *, timeout: int = 180, env: dict[str, str] | None = None
) -> None:
    print(f"[ci] {label}: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, env=env, timeout=timeout, check=True, shell=False)


def main() -> int:
    artifacts = ROOT / ".artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "emulator.log").write_text("Emulator has not started.\n", encoding="utf-8")
    try:
        run_phase("Locked dependencies", ["uv", "sync", "--locked", "--extra", "test"], timeout=300)
        for label, args in (
            ("Lint", ["ruff", "check", "app", "scripts", "tests"]),
            ("Formatting", ["ruff", "format", "--check", "app", "scripts", "tests"]),
            ("Types", ["mypy", "app", "scripts"]),
        ):
            run_phase(label, ["uv", "run", "--no-sync", *args])
        with Emulator(log_path=artifacts / "emulator.log") as emulator:
            env = os.environ.copy()
            env.update(
                COSMOS_ENDPOINT=emulator.endpoint,
                COSMOS_READY_URL=emulator.ready_url,
                AGENT_MODEL_MODE="scripted",
            )
            run_phase(
                "All tests against isolated emulator",
                ["uv", "run", "--no-sync", "pytest", "--junitxml=.artifacts/results.xml"],
                timeout=600,
                env=env,
            )
    except Exception:
        traceback.print_exc()
        return 1
    print("[ci] All checks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
