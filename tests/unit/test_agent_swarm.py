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
    assert "agent-a" not in b["SWARM_PROMPT"]


def test_default_swarm_uses_distinct_agents_bays_and_known_presets() -> None:
    tasks = agent_swarm.DEFAULT_TASKS

    assert len({task.agent for task in tasks}) == len({task.bay for task in tasks}) == len(tasks)
    assert all(task.preset in TASKS for task in tasks)
