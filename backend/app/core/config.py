"""
Application configuration.

Loads environment variables and provides typed settings
for all services (OpenAI, Gemini, worker pool, etc.).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the backend root
_backend_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(_backend_dir / ".env")


class Settings:
    """Centralized application settings."""

    # ─── API Keys ───
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ─── OpenAI ───
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "4096"))

    # ─── Gemini ───
    GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash")
    GEMINI_TEXT_MODEL: str = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")

    # ─── Parallel Image Generation ───
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "5"))
    IMAGE_RETRY_COUNT: int = int(os.getenv("IMAGE_RETRY_COUNT", "3"))
    IMAGE_RETRY_DELAY: float = float(os.getenv("IMAGE_RETRY_DELAY", "2.0"))

    # ─── Paths ───
    BASE_OUTPUT_DIR: Path = Path(os.getenv("BASE_OUTPUT_DIR", str(_backend_dir / "app" / "output")))
    UPLOADS_DIR: Path = Path(os.getenv("UPLOADS_DIR", str(_backend_dir / "app" / "uploads")))

    # ─── CORS ───
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",")

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
