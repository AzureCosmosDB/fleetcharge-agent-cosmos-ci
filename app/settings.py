import os
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

DEMO_TIME = "2026-10-19T12:30:00-07:00"
# Public emulator-only test key; not a production credential or an authorization boundary.
EMULATOR_KEY = "ZW11bGF0b3Itb25seQ=="


@dataclass(frozen=True)
class Settings:
    endpoint: str = "http://127.0.0.1:18081"
    database: str = "fleetchargetest-demo"
    key: str = EMULATOR_KEY
    mode: str = "scripted"
    review_at: str = DEMO_TIME
    timeout_seconds: float = 60
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
        if self.mode not in {"scripted", "ollama"}:
            raise ValueError("Model mode must be scripted or ollama")
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
        limit = 300 if self.mode == "ollama" else 60
        if not 0 < self.timeout_seconds <= limit:
            raise ValueError(f"Review deadline must be within {limit} seconds")

    @property
    def clock(self) -> datetime:
        return datetime.fromisoformat(self.review_at)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            endpoint=os.environ.get("COSMOS_ENDPOINT", cls.endpoint),
            database=os.environ.get("COSMOS_DATABASE", cls.database),
            key=os.environ.get("COSMOS_KEY", EMULATOR_KEY),
            mode=os.environ.get("AGENT_MODEL_MODE", cls.mode),
            review_at=os.environ.get("FLEETCHARGE_REVIEW_AT", DEMO_TIME),
            ollama_endpoint=os.environ.get("OLLAMA_ENDPOINT", cls.ollama_endpoint),
            ollama_model=os.environ.get("OLLAMA_MODEL", cls.ollama_model),
            timeout_seconds=float(os.environ.get("FLEETCHARGE_TIMEOUT_SECONDS", "60")),
        )
