"""Run several coding tasks in parallel Git worktrees, each with its own emulator.

The agent step is replaceable. By default a deterministic stand-in agent makes one
code change and one database write per task, so the isolation, cleanup, and merge
checks run without a model. Pass --agent-command to run a real coding agent instead.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from azure.cosmos.aio import CosmosClient

from app.settings import EMULATOR_KEY, Settings
from scripts.agent_ci import TASKS
from scripts.agent_isolation import IsolationError, check_dispatch
from scripts.emulator import ROOT, Emulator
from scripts.seed_cosmos import seed

DATABASE = "fleetchargetest-swarm"
CONTAINER = "dispatchUpdates"
STANDIN_FLAG = "--standin-agent"

PROMPT = (
    "You are coding task {agent}. Work only inside this Git worktree. Make one small, "
    "reviewable change for the {task} area and add a note describing it under "
    "docs/agent-notes/{agent}.md. Run Python only with the interpreter named by the "
    "SWARM_PYTHON environment variable; it has the Azure Cosmos DB SDK and test tools "
    "installed. Using the COSMOS_ENDPOINT, COSMOS_KEY, and COSMOS_DATABASE environment "
    "variables, record your work by setting item 'current-dispatch' (partition key "
    "'SEA-01') in container 'dispatchUpdates' to pickupBay '{bay}' and updateId "
    "'{agent}-dispatch'. Do not read or write any other endpoint, and do not start or "
    "stop containers. Commit your change."
)

RESOLVE_PROMPT = (
    "Merging {agent}'s branch into the integration branch stopped with conflicts in: {files}. "
    "Keep the intent of both sides and preserve every test and note either side added. "
    "Resolve the conflict markers, run the affected tests with the interpreter named by the "
    "SWARM_PYTHON environment variable (python -m pytest; the COSMOS_* variables are already "
    "set), then git add the files and finish the merge with git commit --no-edit. Do not "
    "abort the merge, reset, or change any other branch."
)


class SwarmError(RuntimeError):
    """A swarm isolation, merge, or cleanup invariant failed."""


@dataclass(frozen=True)
class Task:
    agent: str
    preset: str
    bay: str

    @property
    def update_id(self) -> str:
        return f"{self.agent}-dispatch"

    @property
    def prompt(self) -> str:
        return PROMPT.format(agent=self.agent, task=self.preset, bay=self.bay)


DEFAULT_TASKS = (
    Task("agent-a", "dispatch", "BAY-7"),
    Task("agent-b", "dispatch", "BAY-8"),
    Task("agent-c", "fleet-rules", "BAY-9"),
)


def build_agent_command(template: str | None, task: Task, prompt: str | None = None) -> list[str]:
    if template is None:
        return [sys.executable, str(Path(__file__).resolve()), STANDIN_FLAG]
    words = shlex.split(template, posix=os.name != "nt")
    if os.name == "nt":
        words = [w[1:-1] if len(w) > 1 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]
    text = prompt or task.prompt
    return [word.replace("{prompt}", text).replace("{agent}", task.agent) for word in words]


def agent_environment(task: Task, emulator: Emulator, standin: bool = False) -> dict[str, str]:
    environment = os.environ.copy()
    if standin:
        # The worktree is cut from HEAD and may not contain this runner yet.
        environment["PYTHONPATH"] = str(ROOT)
    environment.update(
        COSMOS_ENDPOINT=emulator.endpoint,
        COSMOS_READY_URL=emulator.ready_url,
        COSMOS_DATABASE=DATABASE,
        COSMOS_KEY=EMULATOR_KEY,
        SWARM_AGENT=task.agent,
        SWARM_BAY=task.bay,
        SWARM_PROMPT=task.prompt,
        SWARM_PYTHON=sys.executable,
        AGENT_MODEL_MODE="ollama",
        FLEETCHARGE_TIMEOUT_SECONDS="60",
    )
    return environment


def git_command(*arguments: str) -> list[str]:
    return [
        "git",
        "-c",
        "user.name=swarm-check",
        "-c",
        "user.email=swarm@example.invalid",
        *arguments,
    ]


def git(*arguments: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        git_command(*arguments), cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise SwarmError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def merge_branch(worktree: Path, agent: str, commit: str) -> list[str]:
    """Merge one task commit; return conflicted paths, leaving the merge open if any."""
    result = subprocess.run(
        git_command("merge", "--no-ff", "-m", f"merge {agent}", commit),
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.returncode:
        return []
    files = git("diff", "--name-only", "--diff-filter=U", cwd=worktree).splitlines()
    if not files:
        raise SwarmError(f"git merge failed: {(result.stderr or result.stdout).strip()}")
    return files


def merge_in_progress(worktree: Path) -> bool:
    result = subprocess.run(
        git_command("rev-parse", "-q", "--verify", "MERGE_HEAD"),
        cwd=worktree,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def has_conflict_markers(worktree: Path, files: list[str]) -> bool:
    result = subprocess.run(
        git_command("grep", "-l", "-E", "^(<{7}|>{7})( |$)", "--", *files),
        cwd=worktree,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def run_logged(
    command: list[str], *, cwd: Path, env: dict[str, str], log: Path, timeout: float
) -> None:
    with log.open("ab") as output:
        try:
            result = subprocess.run(
                command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=timeout
            )
        except subprocess.TimeoutExpired as error:
            raise SwarmError(f"Timed out after {timeout:g}s: {command[0]} (log: {log})") from error
    if result.returncode:
        raise SwarmError(f"Exit {result.returncode}: {' '.join(command[:3])} (log: {log})")


def commit_worktree(worktree: Path, task: Task) -> str:
    git("add", "-A", cwd=worktree)
    if git("status", "--porcelain", cwd=worktree):
        git("commit", "-m", f"{task.agent}: {task.preset} change", cwd=worktree)
    return git("rev-parse", "HEAD", cwd=worktree)


async def read_state(endpoint: str) -> dict[str, Any]:
    async with CosmosClient(endpoint, credential=EMULATOR_KEY) as client:
        container = client.get_database_client(DATABASE).get_container_client(CONTAINER)
        return {
            "sea": await container.read_item("current-dispatch", partition_key="SEA-01"),
            "pdx": await container.read_item("current-dispatch", partition_key="PDX-02"),
        }


async def seed_environment(endpoint: str) -> None:
    async with CosmosClient(endpoint, credential=EMULATOR_KEY) as client:
        await seed(client, Settings(endpoint=endpoint, database=DATABASE))


def verify_state(task: Task, endpoint: str) -> None:
    state = asyncio.run(asyncio.wait_for(read_state(endpoint), 30))
    check_dispatch(state["sea"], bay=task.bay, update_id=task.update_id)
    check_dispatch(state["pdx"], bay="BAY-99", update_id="dispatch-099", depot="PDX-02")


async def standin_write() -> None:
    endpoint, bay, agent = (
        os.environ[name] for name in ("COSMOS_ENDPOINT", "SWARM_BAY", "SWARM_AGENT")
    )
    async with CosmosClient(endpoint, credential=EMULATOR_KEY) as client:
        container = client.get_database_client(DATABASE).get_container_client(CONTAINER)
        document = await container.read_item("current-dispatch", partition_key="SEA-01")
        document.update(pickupBay=bay, updateId=f"{agent}-dispatch")
        await container.upsert_item({k: v for k, v in document.items() if not k.startswith("_")})


def standin_agent() -> int:
    agent, bay = os.environ["SWARM_AGENT"], os.environ["SWARM_BAY"]
    note = Path("docs") / "agent-notes" / f"{agent}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f"# {agent}\n\nStand-in task change; dispatch bay {bay}.\n", encoding="utf-8")
    asyncio.run(asyncio.wait_for(standin_write(), 30))
    return 0


def run_task(
    task: Task, worktree: Path, artifacts: Path, agent_command: str | None
) -> dict[str, Any]:
    folder = artifacts / task.agent
    folder.mkdir()
    started = time.monotonic()
    with Emulator(log_path=folder / "emulator.log") as emulator:
        environment = agent_environment(task, emulator)
        asyncio.run(asyncio.wait_for(seed_environment(emulator.endpoint), 120))
        run_logged(
            build_agent_command(agent_command, task),
            cwd=worktree,
            env=agent_environment(task, emulator, standin=agent_command is None),
            log=folder / "agent.log",
            timeout=900,
        )
        commit = commit_worktree(worktree, task)
        (folder / "change.patch").write_text(
            git("show", "--format=", "--patch", commit, cwd=worktree) + "\n", encoding="utf-8"
        )
        verify_state(task, emulator.endpoint)
        environment["COSMOS_DATABASE"] = f"fleetchargetest-swarm-{task.agent}"
        run_logged(
            [
                sys.executable,
                "-m",
                "pytest",
                *TASKS[task.preset],
                f"--junitxml={folder / 'results.xml'}",
            ],
            cwd=worktree,
            env=environment,
            log=folder / "pytest.log",
            timeout=600,
        )
        identity = {"container_id": emulator.container_id, "endpoint": emulator.endpoint}
    emulator.verify_removed()
    return {
        "agent": task.agent,
        "preset": task.preset,
        "commit": commit,
        "pickup_bay": task.bay,
        "own_state_verified": True,
        "tests_passed": True,
        "seconds": round(time.monotonic() - started, 3),
        **identity,
    }


def shared_emulator_control(
    tasks: tuple[Task, ...], worktrees: dict[str, Path], artifacts: Path
) -> dict[str, Any]:
    """Run the same agents against one emulator and require a detectable lost update."""
    with Emulator(log_path=artifacts / "shared-control.log") as emulator:
        asyncio.run(asyncio.wait_for(seed_environment(emulator.endpoint), 120))

        def work(task: Task) -> None:
            run_logged(
                build_agent_command(None, task),
                cwd=worktrees[task.agent],
                env=agent_environment(task, emulator, standin=True),
                log=artifacts / f"shared-control-{task.agent}.log",
                timeout=300,
            )

        with ThreadPoolExecutor(len(tasks)) as pool:
            for future in [pool.submit(work, task) for task in tasks]:
                future.result()
        survivors = []
        for task in tasks:
            try:
                verify_state(task, emulator.endpoint)
                survivors.append(task.agent)
            except IsolationError:
                pass
    emulator.verify_removed()
    if len(survivors) != 1:
        raise SwarmError(f"Shared-emulator control should keep exactly one write, kept {survivors}")
    return {
        "agents": [task.agent for task in tasks],
        "surviving_write": survivors[0],
        "lost_updates": len(tasks) - 1,
        "collision_detected": True,
    }


def resolve_conflict(
    worktree: Path,
    agent: str,
    files: list[str],
    environment: dict[str, str],
    agent_command: str,
    artifacts: Path,
) -> dict[str, Any]:
    """Ask the configured agent to finish an open merge; accept only a clean, marker-free result."""
    conflict: dict[str, Any] = {"agent": agent, "files": files, "resolved": False}
    prompt = RESOLVE_PROMPT.format(agent=agent, files=", ".join(files))
    environment = {**environment, "SWARM_AGENT": "integrator", "SWARM_PROMPT": prompt}
    try:
        run_logged(
            build_agent_command(agent_command, Task("integrator", "integration", ""), prompt),
            cwd=worktree,
            env=environment,
            log=artifacts / f"resolve-{agent}.log",
            timeout=900,
        )
    except SwarmError as error:
        conflict["resolver_error"] = str(error)
    if merge_in_progress(worktree) or git("status", "--porcelain", cwd=worktree):
        return conflict
    if has_conflict_markers(worktree, files):
        git("reset", "--hard", "HEAD^1", cwd=worktree)
        conflict["resolver_error"] = "Conflict markers were committed; merge reverted"
        return conflict
    conflict["resolved"] = True
    return conflict


def integrate(
    tasks: tuple[Task, ...],
    results: list[dict[str, Any]],
    run: str,
    artifacts: Path,
    agent_command: str | None,
) -> dict[str, Any]:
    worktree = artifacts / "integration"
    git("worktree", "add", "-b", f"swarm/{run}/integration", str(worktree), "HEAD")
    base = git("rev-parse", "HEAD", cwd=worktree)
    presets = sorted({task.preset for task in tasks})
    targets = [target for preset in presets for target in TASKS[preset]]
    merged: list[str] = []
    conflicts: list[dict[str, Any]] = []
    tests_passed: bool | None = None
    test_error: str | None = None
    with Emulator(log_path=artifacts / "integration-emulator.log") as emulator:
        environment = agent_environment(tasks[0], emulator)
        environment["COSMOS_DATABASE"] = "fleetchargetest-swarm-integration"
        for result in results:
            files = merge_branch(worktree, result["agent"], result["commit"])
            if not files:
                merged.append(result["agent"])
                continue
            print(f"[swarm] Merge conflict from {result['agent']}: {', '.join(files)}", flush=True)
            if agent_command is None:
                conflict: dict[str, Any] = {"agent": result["agent"], "files": files}
                conflict["resolved"] = False
            else:
                conflict = resolve_conflict(
                    worktree, result["agent"], files, environment, agent_command, artifacts
                )
            if conflict["resolved"]:
                merged.append(result["agent"])
            elif merge_in_progress(worktree):
                git("merge", "--abort", cwd=worktree)
            conflicts.append(conflict)
        if all(conflict["resolved"] for conflict in conflicts):
            (artifacts / "integration.patch").write_text(
                git("diff", "--patch", base, "HEAD", cwd=worktree) + "\n", encoding="utf-8"
            )
            try:
                run_logged(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        *targets,
                        f"--junitxml={artifacts / 'integration.xml'}",
                    ],
                    cwd=worktree,
                    env=environment,
                    log=artifacts / "integration-pytest.log",
                    timeout=900,
                )
                tests_passed = True
            except SwarmError as error:
                tests_passed = False
                test_error = str(error)
    emulator.verify_removed()
    return {
        "merged": merged,
        "conflicts": conflicts,
        "integrated_tests_passed": tests_passed,
        **({"test_error": test_error} if test_error else {}),
    }


def swarm_status(integration: dict[str, Any]) -> str:
    if any(not conflict["resolved"] for conflict in integration["conflicts"]):
        return "unresolved-conflict"
    return "passed" if integration["integrated_tests_passed"] else "integration-tests-failed"


def run_swarm(
    artifacts: Path, tasks: tuple[Task, ...], agent_command: str | None
) -> dict[str, Any]:
    artifacts.mkdir(parents=True, exist_ok=False)
    run = artifacts.name[:8]
    started = time.monotonic()
    worktrees: dict[str, Path] = {}
    branches = [f"swarm/{run}/{task.agent}" for task in tasks] + [f"swarm/{run}/integration"]
    kind = "stand-in agents" if agent_command is None else "custom agent command"
    print(f"[swarm] {len(tasks)} worktrees, {len(tasks)} emulators, {kind}", flush=True)
    try:
        for task in tasks:
            worktrees[task.agent] = artifacts / "worktrees" / task.agent
            git(
                "worktree",
                "add",
                "-b",
                f"swarm/{run}/{task.agent}",
                str(worktrees[task.agent]),
                "HEAD",
            )
        with ThreadPoolExecutor(len(tasks)) as pool:
            futures = [
                pool.submit(run_task, task, worktrees[task.agent], artifacts, agent_command)
                for task in tasks
            ]
            results = [future.result() for future in futures]
        if len({r["container_id"] for r in results}) != len(tasks) or len(
            {r["endpoint"] for r in results}
        ) != len(tasks):
            raise SwarmError("Agents did not receive distinct emulators")
        print(
            "[swarm] All agents verified in isolation; running shared-emulator control", flush=True
        )
        control = shared_emulator_control(tasks[:2], worktrees, artifacts)
        print(
            "[swarm] Collision reproduced without isolation; merging and testing integration",
            flush=True,
        )
        integration = integrate(tasks, results, run, artifacts, agent_command)
    finally:
        for worktree in [*worktrees.values(), artifacts / "integration"]:
            if worktree.exists():
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)], cwd=ROOT, check=False
                )
        for branch in branches:
            subprocess.run(
                ["git", "branch", "-D", branch], cwd=ROOT, capture_output=True, check=False
            )
        shutil.rmtree(artifacts / "worktrees", ignore_errors=True)
    status = swarm_status(integration)
    report: dict[str, Any] = {
        "kind": "agent-swarm-check",
        "status": status,
        "agent_step": kind,
        "agents": results,
        "shared_emulator_control": control,
        "integration": integration,
        "owned_containers_removed": True,
        "total_seconds": round(time.monotonic() - started, 3),
    }
    (artifacts / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(
        f"[swarm] {'Passed' if status == 'passed' else 'FAILED: ' + status}; evidence: {artifacts}",
        flush=True,
    )
    return report


def main() -> int:
    if STANDIN_FLAG in sys.argv:
        return standin_agent()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-command",
        help="Command run in each worktree; {prompt} and {agent} are replaced. "
        "Default: deterministic stand-in agent.",
    )
    parser.add_argument("--agents", type=int, choices=(2, 3), default=3)
    args = parser.parse_args()
    report = run_swarm(
        ROOT / ".artifacts" / "agent-swarm" / uuid4().hex,
        DEFAULT_TASKS[: args.agents],
        args.agent_command,
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
