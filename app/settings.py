import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEMO_TIME = "2026-10-19T12:30:00-07:00"
# Public emulator-only test key; not a production credential or an authorization boundary.
EMULATOR_KEY = (
    "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
)


@dataclass(frozen=True)
class Settings:
    endpoint: str = "http://127.0.0.1:18081"
    database: str = "fleetchargetest-demo"
    key: str = EMULATOR_KEY
    mode: str = "ollama"
    review_at: str = DEMO_TIME
    timeout_seconds: float = 300
    ollama_endpoint: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "fleetcharge-phi3.5:latest"

    def __post_init__(self) -> None:
        url = urlparse(self.endpoint)
        if (
            url.scheme not in {"http", "https"}
            or url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or url.username
            or url.password
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
        ):
            raise ValueError("The teaching sample accepts loopback emulator endpoints only")
        if not re.fullmatch(r"fleetchargetest-[A-Za-z0-9_-]{1,80}", self.database):
            raise ValueError("Database name must use the isolated fleetchargetest- prefix")
        if self.mode != "ollama":
            raise ValueError("Only real Ollama inference is supported; scripted mode was removed")
        model_url = urlparse(self.ollama_endpoint)
        if (
            model_url.scheme != "http"
            or model_url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or model_url.username
            or model_url.password
            or model_url.path.rstrip("/") != "/v1"
            or model_url.query
            or model_url.fragment
        ):
            raise ValueError("Ollama must use a local HTTP endpoint ending in /v1")
        if not self.ollama_model.strip() or "cloud" in self.ollama_model.lower():
            raise ValueError("Supply an installed local Ollama model, not a cloud model")
        if self.clock.tzinfo is None or self.clock.utcoffset() is None:
            raise ValueError("Review time must include a timezone offset")
        limit = 900
        if not 0 < self.timeout_seconds <= limit:
            raise ValueError(f"Review deadline must be within {limit} seconds")

    @property
    def clock(self) -> datetime:
        return datetime.fromisoformat(self.review_at)

    @classmethod
    def from_env(cls) -> "Settings":
        values: dict[str, str] = {}
        for key, value in dotenv_values(ENV_FILE).items():
            if value is None:
                raise ValueError(f"Local .env setting must have a value: {key}")
            values[key] = value
        values.update(os.environ)
        return cls(
            endpoint=values.get("COSMOS_ENDPOINT", cls.endpoint),
            database=values.get("COSMOS_DATABASE", cls.database),
            key=values.get("COSMOS_KEY", EMULATOR_KEY),
            mode=values.get("AGENT_MODEL_MODE", cls.mode),
            review_at=values.get("FLEETCHARGE_REVIEW_AT", DEMO_TIME),
            ollama_endpoint=values.get("OLLAMA_ENDPOINT", cls.ollama_endpoint),
            ollama_model=values.get("OLLAMA_MODEL", cls.ollama_model),
            timeout_seconds=float(values.get("FLEETCHARGE_TIMEOUT_SECONDS", "300")),
        )
