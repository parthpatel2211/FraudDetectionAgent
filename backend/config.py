import os
from dataclasses import dataclass

@dataclass
class Settings:
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    OPENAI_API_KEY: str | None = ""
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")
    # For CORS
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

settings = Settings()
