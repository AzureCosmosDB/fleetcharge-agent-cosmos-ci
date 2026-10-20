import pytest

from app import settings as settings_module
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


@pytest.mark.parametrize("mode,deadline", [("ollama", 901), ("ollama", 0)])
def test_review_deadlines_remain_bounded(mode, deadline):
    with pytest.raises(ValueError, match="deadline"):
        Settings(mode=mode, timeout_seconds=deadline)


def test_cpu_only_live_review_deadline_is_explicitly_bounded():
    assert Settings(mode="ollama", timeout_seconds=900).timeout_seconds == 900


def test_default_mode_is_real_and_legacy_scripted_configuration_is_rejected():
    assert Settings().mode == "ollama"
    assert Settings().timeout_seconds == 300
    with pytest.raises(ValueError, match="scripted mode was removed"):
        Settings(mode="scripted")


def test_rejects_naive_clock():
    with pytest.raises(ValueError):
        Settings(review_at="2026-10-19T12:30:00")


def test_cleanup_requires_owned_database_name():
    with pytest.raises(ValueError):
        Settings(database="production")


def test_local_dotenv_loads_without_overriding_process_environment(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("OLLAMA_MODEL=from-file:latest\nFLEETCHARGE_TIMEOUT_SECONDS=123\n")
    monkeypatch.setattr(settings_module, "ENV_FILE", path)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("FLEETCHARGE_TIMEOUT_SECONDS", raising=False)
    assert Settings.from_env().ollama_model == "from-file:latest"
    assert Settings.from_env().timeout_seconds == 123
    monkeypatch.setenv("OLLAMA_MODEL", "from-process:latest")
    assert Settings.from_env().ollama_model == "from-process:latest"


def test_invalid_dotenv_value_fails_explicitly(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("OLLAMA_MODEL\n")
    monkeypatch.setattr(settings_module, "ENV_FILE", path)
    with pytest.raises(ValueError, match="must have a value"):
        Settings.from_env()


def test_documented_emulator_profile_matches_defaults(monkeypatch):
    from base64 import b64decode

    for name in ("COSMOS_ENDPOINT", "COSMOS_DATABASE", "COSMOS_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        settings_module, "ENV_FILE", settings_module.ENV_FILE.with_name(".env.example")
    )
    config = Settings.from_env()
    assert config.endpoint == Settings().endpoint == "http://127.0.0.1:18081"
    assert config.database == Settings().database == "fleetchargetest-demo"
    assert config.key == Settings().key == settings_module.EMULATOR_KEY
    assert len(b64decode(config.key, validate=True)) == 64


def test_cosmos_dotenv_settings_allow_explicit_process_overrides(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        f"COSMOS_ENDPOINT=http://127.0.0.1:18081\n"
        f"COSMOS_DATABASE=fleetchargetest-local\nCOSMOS_KEY={settings_module.EMULATOR_KEY}\n"
    )
    monkeypatch.setattr(settings_module, "ENV_FILE", path)
    for name in ("COSMOS_ENDPOINT", "COSMOS_DATABASE", "COSMOS_KEY"):
        monkeypatch.delenv(name, raising=False)
    config = Settings.from_env()
    assert config.key == settings_module.EMULATOR_KEY
    assert config.database == "fleetchargetest-local"
    assert config.endpoint == "http://127.0.0.1:18081"
    monkeypatch.setenv("COSMOS_ENDPOINT", "http://127.0.0.1:49151")
    monkeypatch.setenv("COSMOS_DATABASE", "fleetchargetest-process")
    monkeypatch.setenv("COSMOS_KEY", "Y3VzdG9tLWVtdWxhdG9yLWtleQ==")
    config = Settings.from_env()
    assert config.endpoint == "http://127.0.0.1:49151"
    assert config.database == "fleetchargetest-process"
    assert config.key == "Y3VzdG9tLWVtdWxhdG9yLWtleQ=="
