from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from scripts import agent_swarm
from scripts.agent_ci import TASKS
from scripts.emulator import ROOT, Emulator

TASK = agent_swarm.Task("agent-a", "dispatch", "BAY-7")


def test_default_agent_runs_the_standin_by_absolute_path() -> None:
    command = agent_swarm.build_agent_command(None, TASK)

    assert command[0] == sys.executable
    assert Path(command[1]).is_absolute()
    assert Path(command[1]).name == "agent_swarm.py"
    assert command[2:] == [agent_swarm.STANDIN_FLAG]


def test_custom_agent_command_receives_prompt_and_agent_as_single_arguments() -> None:
    command = agent_swarm.build_agent_command('tool --name {agent} -p "{prompt}"', TASK)

    assert command[:3] == ["tool", "--name", "agent-a"]
    assert command[4] == TASK.prompt
    assert "BAY-7" in TASK.prompt and "agent-a-dispatch" in TASK.prompt


def test_each_agent_environment_points_only_at_its_own_emulator() -> None:
    first = SimpleNamespace(
        endpoint="http://127.0.0.1:1111", ready_url="http://127.0.0.1:1112/ready"
    )
    second = SimpleNamespace(
        endpoint="http://127.0.0.1:2221", ready_url="http://127.0.0.1:2222/ready"
    )
    other = agent_swarm.Task("agent-b", "dispatch", "BAY-8")

    a = agent_swarm.agent_environment(TASK, cast(Emulator, first))
    b = agent_swarm.agent_environment(other, cast(Emulator, second), standin=True)

    assert a["COSMOS_ENDPOINT"] == first.endpoint and b["COSMOS_ENDPOINT"] == second.endpoint
    assert a["COSMOS_DATABASE"] == b["COSMOS_DATABASE"] == agent_swarm.DATABASE
    assert (a["SWARM_AGENT"], b["SWARM_AGENT"]) == ("agent-a", "agent-b")
    assert b["PYTHONPATH"] == str(ROOT)
    assert a["SWARM_PYTHON"] == sys.executable
    assert "SWARM_PYTHON" in TASK.prompt
    assert "agent-a" not in b["SWARM_PROMPT"]


def test_default_swarm_uses_distinct_agents_bays_and_known_presets() -> None:
    tasks = agent_swarm.DEFAULT_TASKS

    assert len({task.agent for task in tasks}) == len({task.bay for task in tasks}) == len(tasks)
    assert all(task.preset in TASKS for task in tasks)


def _repo(path: Path) -> Path:
    path.mkdir()
    for arguments in (("init", "-q", "-b", "main"), ("config", "core.autocrlf", "false")):
        agent_swarm.git(*arguments, cwd=path)
    (path / "notes.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    agent_swarm.git("add", "-A", cwd=path)
    agent_swarm.git("commit", "-q", "-m", "base", cwd=path)
    return path


def _branch(path: Path, name: str, content: str) -> str:
    agent_swarm.git("checkout", "-q", "-b", name, "main", cwd=path)
    (path / "notes.txt").write_text(content, encoding="utf-8")
    agent_swarm.git("commit", "-q", "-am", name, cwd=path)
    commit = agent_swarm.git("rev-parse", "HEAD", cwd=path)
    agent_swarm.git("checkout", "-q", "main", cwd=path)
    return commit


def test_overlapping_agent_changes_are_reported_as_conflicts_and_can_be_aborted(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "repo")
    first = _branch(repo, "agent-a", "one\nA\nthree\n")
    second = _branch(repo, "agent-b", "one\nB\nthree\n")

    assert agent_swarm.merge_branch(repo, "agent-a", first) == []
    assert not agent_swarm.merge_in_progress(repo)
    assert agent_swarm.merge_branch(repo, "agent-b", second) == ["notes.txt"]
    assert agent_swarm.merge_in_progress(repo)
    assert agent_swarm.has_conflict_markers(repo, ["notes.txt"])

    agent_swarm.git("merge", "--abort", cwd=repo)

    assert not agent_swarm.merge_in_progress(repo)
    assert not agent_swarm.has_conflict_markers(repo, ["notes.txt"])
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "one\nA\nthree\n"


def test_separate_agent_changes_merge_without_conflict(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    first = _branch(repo, "agent-a", "ONE\ntwo\nthree\n")
    second = _branch(repo, "agent-b", "one\ntwo\nTHREE\n")

    assert agent_swarm.merge_branch(repo, "agent-a", first) == []
    assert agent_swarm.merge_branch(repo, "agent-b", second) == []
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "ONE\ntwo\nTHREE\n"


def test_swarm_status_distinguishes_conflicts_from_failed_integration_tests() -> None:
    clean = {"conflicts": [], "integrated_tests_passed": True}
    unresolved = {
        "conflicts": [{"agent": "agent-b", "files": ["a"], "resolved": False}],
        "integrated_tests_passed": None,
    }
    resolved = {
        "conflicts": [{"agent": "agent-b", "files": ["a"], "resolved": True}],
        "integrated_tests_passed": True,
    }

    assert agent_swarm.swarm_status(clean) == "passed"
    assert agent_swarm.swarm_status(resolved) == "passed"
    assert agent_swarm.swarm_status(unresolved) == "unresolved-conflict"
    assert (
        agent_swarm.swarm_status({"conflicts": [], "integrated_tests_passed": False})
        == "integration-tests-failed"
    )


def test_resolver_prompt_names_the_agent_and_conflicting_files() -> None:
    text = agent_swarm.RESOLVE_PROMPT.format(agent="agent-b", files="tests/a.py, tests/b.py")
    command = agent_swarm.build_agent_command('tool -p "{prompt}"', TASK, text)

    assert "agent-b" in command[2] and "tests/a.py, tests/b.py" in command[2]
    assert "git commit --no-edit" in command[2]
