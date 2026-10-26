"""Lifecycle tests mock Docker/HTTP, never Cosmos repository behavior."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from scripts import ci
from scripts.emulator import IMAGE, OWNER_LABEL, ROOT, Emulator, EmulatorError

CONTAINER_ID = "a" * 64


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    path = ROOT / ".cache" / f"lifecycle-{uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


class Docker:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.label = ""
        self.name = ""
        self.fail = ""
        self.wrong_owner = False
        self.created = False

    def run(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["timeout"] > 0
        assert kwargs["shell"] is False
        self.calls.append(command)
        action = command[1]
        if action == self.fail:
            return subprocess.CompletedProcess(command, 1, "", f"{action} failed")
        if action == "create":
            self.created = True
            self.name = command[command.index("--name") + 1]
            self.label = command[command.index("--label") + 1].split("=", 1)[1]
            return subprocess.CompletedProcess(command, 0, CONTAINER_ID, "")
        if action == "container":
            if not self.created:
                return subprocess.CompletedProcess(command, 1, "", "No such container")
            info = {
                "Id": CONTAINER_ID,
                "Name": f"/{self.name}",
                "Config": {"Labels": {OWNER_LABEL: "foreign" if self.wrong_owner else self.label}},
                "State": {"Running": True},
                "NetworkSettings": {
                    "Ports": {
                        "8081/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49151"}],
                        "8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}],
                    }
                },
            }
            return subprocess.CompletedProcess(command, 0, json.dumps([info]), "")
        if action == "logs":
            return subprocess.CompletedProcess(command, 0, "emulator diagnostic\n", "")
        if action == "rm":
            self.created = False
        return subprocess.CompletedProcess(command, 0, "", "")


class Ready:
    status = 200

    def __enter__(self) -> Ready:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


@pytest.fixture
def docker(monkeypatch: pytest.MonkeyPatch) -> Docker:
    fake = Docker()
    monkeypatch.setattr(subprocess, "run", fake.run)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **kw: Ready())
    return fake


def emulator(tmp_path: Path, **kwargs: Any) -> Emulator:
    return Emulator(log_path=tmp_path / "emulator.log", **kwargs)


def test_dynamic_loopback_ports_and_exact_cleanup(docker: Docker, tmp_path: Path) -> None:
    with emulator(tmp_path) as instance:
        assert instance.endpoint == "http://127.0.0.1:49151"
        assert instance.ready_url == "http://127.0.0.1:49152/ready"
    create = next(call for call in docker.calls if call[1] == "create")
    assert "127.0.0.1::8081" in create
    assert "127.0.0.1::8080" in create
    assert IMAGE in create
    assert ["docker", "rm", "--force", CONTAINER_ID] in docker.calls
    assert "emulator diagnostic" in (tmp_path / "emulator.log").read_text()
    before = len(docker.calls)
    instance.close()
    assert len(docker.calls) == before


def test_removal_verification_requires_completed_cleanup(docker: Docker, tmp_path: Path) -> None:
    instance = emulator(tmp_path)
    with pytest.raises(EmulatorError, match="cleanup has not completed"):
        instance.verify_removed()
    with instance:
        with pytest.raises(EmulatorError, match="cleanup has not completed"):
            instance.verify_removed()
    instance.verify_removed()
    docker.created = True
    with pytest.raises(EmulatorError, match="still exists"):
        instance.verify_removed()


def test_readiness_timeout_captures_logs_and_cleans(
    docker: Docker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args: Any, **kwargs: Any) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", unavailable)
    with pytest.raises(EmulatorError, match="readiness timed out"):
        with emulator(tmp_path, readiness_timeout=0.01, poll_interval=0.001):
            pytest.fail("Unready emulator must not enter the workload")
    assert ["docker", "rm", "--force", CONTAINER_ID] in docker.calls
    assert "emulator diagnostic" in (tmp_path / "emulator.log").read_text()


@pytest.mark.parametrize("action", ["create", "start", "pull"])
def test_docker_failure_exits_and_cleans(
    docker: Docker, tmp_path: Path, action: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    docker.fail = action
    if action == "pull":
        original = docker.run

        def absent_image(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if command[1] == "image":
                return subprocess.CompletedProcess(command, 1, "", "image missing")
            return original(command, **kwargs)

        monkeypatch.setattr(subprocess, "run", absent_image)
    with pytest.raises(EmulatorError, match=f"{action}.*failed"):
        with emulator(tmp_path):
            pytest.fail("Docker failure must prevent workload execution")
    removed = any(call[1] == "rm" for call in docker.calls)
    assert removed == (action == "start")


def test_ownership_guard_never_logs_or_removes_foreign_container(
    docker: Docker, tmp_path: Path
) -> None:
    with pytest.raises(ExceptionGroup, match="Workload and emulator cleanup"):
        with emulator(tmp_path):
            docker.wrong_owner = True
            raise RuntimeError("primary workload failure")
    assert not any(call[1] in ("rm", "logs") for call in docker.calls)
    assert "Ownership guard" in (tmp_path / "emulator.log").read_text()


def test_workload_failure_still_cleans(docker: Docker, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="workload failure"):
        with emulator(tmp_path):
            raise RuntimeError("workload failure")
    assert ["docker", "rm", "--force", CONTAINER_ID] in docker.calls


def test_cleanup_error_preserves_primary(docker: Docker, tmp_path: Path) -> None:
    with pytest.raises(ExceptionGroup) as caught:
        with emulator(tmp_path):
            docker.fail = "rm"
            raise ValueError("original test failure")
    assert isinstance(caught.value.exceptions[0], ValueError)
    assert "original test failure" in str(caught.value.exceptions[0])
    assert "rm failed" in str(caught.value.exceptions[1].exceptions[0])  # type: ignore[attr-defined]


def test_logs_failure_does_not_skip_removal(docker: Docker, tmp_path: Path) -> None:
    with pytest.raises(ExceptionGroup, match="diagnostics/cleanup"):
        with emulator(tmp_path):
            docker.fail = "logs"
    assert ["docker", "rm", "--force", CONTAINER_ID] in docker.calls


def test_timed_out_create_recovers_only_uuid_owned_container(
    docker: Docker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = docker.run

    def timeout_after_create(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        result = original(command, **kwargs)
        if command[1] == "create":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return result

    monkeypatch.setattr(subprocess, "run", timeout_after_create)
    with pytest.raises(EmulatorError, match="timed out"):
        with emulator(tmp_path):
            pytest.fail("Timed out create must not run workload")
    assert ["docker", "rm", "--force", CONTAINER_ID] in docker.calls


def test_ci_phase_failure_returns_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["ci", "--components-only"])
    calls: list[list[str]] = []

    def failure(command: list[str], **kwargs: Any) -> None:
        assert kwargs["timeout"] == 300
        assert kwargs["shell"] is False
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "run", failure)
    assert ci.main() == 1
    assert calls == [["uv", "sync", "--locked", "--extra", "test"]]


@pytest.mark.parametrize("pytest_fails", [False, True])
@pytest.mark.parametrize("components_only", [False, True])
def test_ci_runs_all_gates_and_cleans_after_pytest(
    docker: Docker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pytest_fails: bool,
    components_only: bool,
) -> None:
    monkeypatch.setattr("sys.argv", ["ci", "--components-only"] if components_only else ["ci"])
    phases: list[list[str]] = []
    original = docker.run

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if command[0] == "docker":
            return original(command, **kwargs)
        assert kwargs["timeout"] > 0
        assert kwargs["shell"] is False
        phases.append(command)
        if "mypy" in command:
            assert kwargs["timeout"] == 600
        elif "ruff" in command:
            assert kwargs["timeout"] == 180
        if "pytest" in command:
            assert kwargs["env"]["COSMOS_ENDPOINT"] == "http://127.0.0.1:49151"
            assert kwargs["env"]["COSMOS_READY_URL"] == "http://127.0.0.1:49152/ready"
            assert kwargs["env"]["AGENT_MODEL_MODE"] == "ollama"
            assert command[-1] == "--junitxml=.artifacts/results.xml"
            if pytest_fails:
                raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "run", run)
    assert ci.main() == int(pytest_fails)
    expected = [
        ["uv", "sync", "--locked", "--extra", "test"],
        ["uv", "run", "--no-sync", "ruff", "check", "app", "scripts", "tests"],
        ["uv", "run", "--no-sync", "ruff", "format", "--check", "app", "scripts", "tests"],
        ["uv", "run", "--no-sync", "mypy", "app", "scripts"],
        ["uv", "run", "--no-sync", "pytest", "--junitxml=.artifacts/results.xml"],
    ]
    if not components_only and not pytest_fails:
        expected.append(
            [
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                "scripts.test_ollama",
                "--review-timeout",
                "300",
            ]
        )
    assert phases == expected
    assert ["docker", "rm", "--force", CONTAINER_ID] in docker.calls
    assert "emulator diagnostic" in (tmp_path / ".artifacts" / "emulator.log").read_text()
