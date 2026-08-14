from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class Settings:
    ANTHROPIC_API_KEY: str | None = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None
    )
    ANTHROPIC_MODEL: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    )
    LLM_MAX_TOKENS: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "1500")))
    LLM_TIMEOUT_SECONDS: float = field(
        default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    )
    LLM_RATE_LIMIT_PER_MINUTE: int = field(
        default_factory=lambda: int(os.getenv("LLM_RATE_LIMIT_PER_MINUTE", "5"))
    )
    RISK_THRESHOLD: float = field(
        default_factory=lambda: float(os.getenv("RISK_THRESHOLD", "0.5"))
    )
    MAX_TRANSACTIONS_PER_REQUEST: int = field(
        default_factory=lambda: int(os.getenv("MAX_TRANSACTIONS_PER_REQUEST", "5000"))
    )
    ALLOWED_ORIGINS: list[str] = field(default_factory=_origins)
    HOST: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    DEBUG: bool = field(default_factory=lambda: _bool("DEBUG"))


settings = Settings()
