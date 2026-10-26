"""Proof-invariant tests, not a substitute for the real two-emulator command."""

import os
from pathlib import Path

import pytest

from scripts.agent_isolation import (
    DATABASE,
    IsolationError,
    Sandbox,
    check_dispatch,
    check_environments,
)
from scripts.emulator import Emulator


def sandboxes(tmp_path: Path) -> tuple[Sandbox, Sandbox]:
    first = Emulator(log_path=tmp_path / "agent-a.log")
    first.container_id = "a" * 64
    first.endpoint = "http://127.0.0.1:49001"
    first.ready_url = "http://127.0.0.1:49002/ready"
    second = Emulator(log_path=tmp_path / "agent-b.log")
    second.container_id = "b" * 64
    second.endpoint = "http://127.0.0.1:49003"
    second.ready_url = "http://127.0.0.1:49004/ready"
    return Sandbox("agent-a", first, "BAY-7"), Sandbox("agent-b", second, "BAY-8")


def test_shared_ids_ignore_ambient_cloud_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://not-a-local-emulator.example")
    monkeypatch.setenv("COSMOS_DATABASE", "shared-production")
    before = dict(os.environ)
    pair = sandboxes(tmp_path)
    check_environments(pair)
    assert pair[0].settings.database == pair[1].settings.database == DATABASE
    assert pair[0].settings.endpoint != pair[1].settings.endpoint
    assert pair[0].update_id != pair[1].update_id
    assert dict(os.environ) == before


@pytest.mark.parametrize("collision", ["container", "sdk", "readiness", "cross-port", "missing"])
def test_environment_collision_is_rejected(tmp_path: Path, collision: str) -> None:
    first, second = sandboxes(tmp_path)
    if collision == "container":
        second.emulator.container_id = first.emulator.container_id
    elif collision == "sdk":
        second.emulator.endpoint = first.emulator.endpoint
    elif collision == "readiness":
        second.emulator.ready_url = first.emulator.ready_url
    elif collision == "cross-port":
        second.emulator.endpoint = first.emulator.ready_url.removesuffix("/ready")
    else:
        second.emulator.container_id = None
    with pytest.raises(IsolationError, match="two owned containers"):
        check_environments((first, second))


@pytest.mark.parametrize("field", ["id", "depotId", "pickupBay", "updateId"])
def test_wrong_or_missing_readback_fails(field: str) -> None:
    document = {
        "id": "current-dispatch",
        "depotId": "SEA-01",
        "pickupBay": "BAY-7",
        "updateId": "agent-a-dispatch",
    }
    check_dispatch(document, bay="BAY-7", update_id="agent-a-dispatch")
    document[field] = "another-agent"
    with pytest.raises(IsolationError, match=field):
        check_dispatch(document, bay="BAY-7", update_id="agent-a-dispatch")
    del document[field]
    with pytest.raises(IsolationError, match=field):
        check_dispatch(document, bay="BAY-7", update_id="agent-a-dispatch")
