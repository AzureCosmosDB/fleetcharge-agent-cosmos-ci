from unittest.mock import MagicMock

import pytest

from scripts import test_ollama


@pytest.mark.parametrize("deadline", [300, 900])
def test_live_runner_propagates_review_deadline_and_bounds_subprocess(
    tmp_path, monkeypatch, deadline
):
    monkeypatch.setattr(
        "sys.argv", ["test_ollama", "--model", "local:latest", "--review-timeout", str(deadline)]
    )
    monkeypatch.setattr(test_ollama, "ROOT", tmp_path)
    artifacts = tmp_path / ".artifacts"
    artifacts.mkdir()
    stale = [
        artifacts / name
        for name in (
            "ollama-results.xml",
            "ollama-review-output.json",
            "ollama-report.md",
            "ollama-inference.json",
        )
    ]
    for path in stale:
        path.write_text("old successful result")
    http = MagicMock()
    http.__enter__.return_value = http
    http.post.return_value.json.return_value = {"capabilities": ["completion"]}
    http.get.return_value.json.return_value = {"models": [{"name": "local:latest"}]}
    monkeypatch.setattr(test_ollama.httpx, "Client", MagicMock(return_value=http))
    emulator = MagicMock()
    emulator.__enter__.return_value.endpoint = "http://127.0.0.1:49151"
    emulator.__enter__.return_value.ready_url = "http://127.0.0.1:49152/ready"
    monkeypatch.setattr(test_ollama, "Emulator", MagicMock(return_value=emulator))
    phase = MagicMock()
    monkeypatch.setattr(test_ollama, "run_phase", phase)

    assert test_ollama.main() == 0
    assert all(not path.exists() for path in stale)
    command = phase.call_args.args[1]
    assert command[command.index("--ollama-review-timeout") + 1] == str(deadline)
    assert phase.call_args.kwargs["timeout"] == 2 * deadline + 820
    assert "--capture=tee-sys" in command
    assert phase.call_args.kwargs["env"]["AGENT_MODEL_MODE"] == "ollama"
    assert phase.call_args.kwargs["env"]["FLEETCHARGE_TIMEOUT_SECONDS"] == "60"
    assert emulator.__exit__.called


@pytest.mark.parametrize("deadline", [0, 901])
def test_invalid_live_deadline_fails_before_contacting_services(tmp_path, monkeypatch, deadline):
    monkeypatch.setattr(test_ollama, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["test_ollama", "--review-timeout", str(deadline)])
    http = MagicMock()
    emulator = MagicMock()
    monkeypatch.setattr(test_ollama.httpx, "Client", http)
    monkeypatch.setattr(test_ollama, "Emulator", emulator)

    assert test_ollama.main() == 1
    http.assert_not_called()
    emulator.assert_not_called()
