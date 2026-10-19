import pytest

from app.settings import Settings


@pytest.mark.parametrize("endpoint", ["https://example.com", "http://127.0.0.1.evil", "file:///x"])
def test_rejects_non_loopback_endpoints(endpoint):
    with pytest.raises(ValueError):
        Settings(endpoint=endpoint)


def test_rejects_unknown_model_mode():
    with pytest.raises(ValueError):
        Settings(mode="live")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com/v1",
        "http://127.0.0.1.evil/v1",
        "http://user:password@127.0.0.1/v1",
        "http://127.0.0.1:11434",
        "http://127.0.0.1:11434/v1?cloud=true",
    ],
)
def test_rejects_non_local_ollama_configuration(endpoint):
    with pytest.raises(ValueError, match="Ollama"):
        Settings(mode="ollama", ollama_endpoint=endpoint)


@pytest.mark.parametrize("model", ["", " ", "qwen-cloud", "model:cloud"])
def test_rejects_empty_or_cloud_model(model):
    with pytest.raises(ValueError, match="local Ollama model"):
        Settings(mode="ollama", ollama_model=model)


def test_ollama_configuration_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL_MODE", "ollama")
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:0.5b")
    monkeypatch.setenv("FLEETCHARGE_TIMEOUT_SECONDS", "300")
    settings = Settings.from_env()
    assert settings.mode == "ollama"
    assert settings.ollama_endpoint == "http://localhost:11434/v1"
    assert settings.ollama_model == "qwen2.5:0.5b"
    assert settings.timeout_seconds == 300


@pytest.mark.parametrize("mode,deadline", [("scripted", 61), ("ollama", 301), ("ollama", 0)])
def test_review_deadlines_remain_bounded(mode, deadline):
    with pytest.raises(ValueError, match="deadline"):
        Settings(mode=mode, timeout_seconds=deadline)


def test_rejects_naive_clock():
    with pytest.raises(ValueError):
        Settings(review_at="2026-10-19T12:30:00")


def test_cleanup_requires_owned_database_name():
    with pytest.raises(ValueError):
        Settings(database="production")
