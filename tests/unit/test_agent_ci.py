import json
import os
import subprocess
from pathlib import Path

import pytest

from app.settings import EMULATOR_KEY
from scripts import agent_ci
from scripts.emulator import EmulatorError


class FakeEmulator:
    endpoint = "http://127.0.0.1:49001"
    ready_url = "http://127.0.0.1:49002/ready"

    def __init__(self, *, log_path):
        self.log_path = log_path
        self.closed = False
        self.verified = False
        self.removal_error = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def verify_removed(self):
        assert self.closed
        if self.removal_error:
            raise EmulatorError("Owned container still exists")
        self.verified = True


@pytest.fixture
def isolated_runner(monkeypatch, tmp_path):
    emulator = FakeEmulator(log_path=tmp_path / "run" / "emulator.log")
    monkeypatch.setattr(agent_ci, "Emulator", lambda **_: emulator)
    calls = []
    monkeypatch.setattr(
        agent_ci,
        "run_phase",
        lambda label, command, **kwargs: calls.append((label, command, kwargs)),
    )
    return emulator, calls, tmp_path / "run"


@pytest.mark.parametrize("task", agent_ci.TASKS)
def test_task_gets_owned_settings_and_separate_artifacts(isolated_runner, monkeypatch, task):
    emulator, calls, artifacts = isolated_runner
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://shared-account.example")
    monkeypatch.setenv("COSMOS_DATABASE", "shared-production")
    monkeypatch.setenv("COSMOS_KEY", "not-the-public-emulator-key")
    before = dict(os.environ)
    report = agent_ci.run_task(task, artifacts)
    assert dict(os.environ) == before
    assert emulator.closed and emulator.verified
    assert report["kind"] == "component-task-check"
    assert report["task"] == task
    assert report["owned_container_removed"] is True
    assert json.loads((artifacts / "result.json").read_text()) == report
    assert len(calls) == 1
    _, command, options = calls[0]
    assert command == [
        "uv",
        "run",
        "--no-sync",
        "pytest",
        *agent_ci.TASKS[task],
        f"--junitxml={artifacts / 'results.xml'}",
    ]
    assert "--ollama" not in command
    assert options["timeout"] == 600
    environment = options["env"]
    assert environment["COSMOS_ENDPOINT"] == emulator.endpoint
    assert environment["COSMOS_READY_URL"] == emulator.ready_url
    assert environment["COSMOS_DATABASE"] == f"fleetchargetest-agent-{task}"
    assert environment["COSMOS_KEY"] == EMULATOR_KEY
    assert "not-the-public-emulator-key" not in json.dumps(report)


def test_failed_tests_clean_up_without_success_report(isolated_runner, monkeypatch):
    emulator, _, artifacts = isolated_runner

    def fail(*_, **__):
        raise subprocess.CalledProcessError(1, ["pytest"])

    monkeypatch.setattr(agent_ci, "run_phase", fail)
    with pytest.raises(subprocess.CalledProcessError):
        agent_ci.run_task("dispatch", artifacts)
    assert emulator.closed
    assert not (artifacts / "result.json").exists()


def test_failed_removal_does_not_write_success_report(isolated_runner):
    emulator, _, artifacts = isolated_runner
    emulator.removal_error = True
    with pytest.raises(EmulatorError, match="still exists"):
        agent_ci.run_task("dispatch", artifacts)
    assert emulator.closed
    assert not (artifacts / "result.json").exists()


def test_existing_artifacts_are_never_overwritten(isolated_runner):
    _, calls, artifacts = isolated_runner
    artifacts.mkdir()
    with pytest.raises(FileExistsError):
        agent_ci.run_task("dispatch", artifacts)
    assert not calls


def test_invalid_cli_task_fails_explicitly(monkeypatch):
    monkeypatch.setattr("sys.argv", ["agent_ci", "--task", "unknown"])
    with pytest.raises(SystemExit) as error:
        agent_ci.main()
    assert error.value.code == 2


def test_main_allocates_unique_task_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(agent_ci, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["agent_ci", "--task", "dispatch"])
    paths = []
    monkeypatch.setattr(agent_ci, "run_task", lambda task, artifacts: paths.append(artifacts))
    assert agent_ci.main() == agent_ci.main() == 0
    assert len(set(paths)) == 2
    assert all(path.parent == tmp_path / ".artifacts" / "agent-ci" / "dispatch" for path in paths)
