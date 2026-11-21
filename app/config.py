"""Runtime configuration, read from environment variables (optionally a .env file)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "CSE Plus"
    secret_key: str = field(default_factory=lambda: os.getenv("CSE_SECRET_KEY") or secrets.token_urlsafe(48))
    database_url: str = field(default_factory=lambda: os.getenv("CSE_DATABASE_URL", "sqlite:///./cseplus.db"))
    token_ttl_minutes: int = field(default_factory=lambda: int(os.getenv("CSE_TOKEN_TTL_MINUTES", "1440")))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("CSE_MODEL", "claude-opus-5-5"))
    effort: str = field(default_factory=lambda: os.getenv("CSE_EFFORT", "medium"))
    web_search: bool = field(default_factory=lambda: _bool("CSE_WEB_SEARCH", True))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("CSE_MAX_UPLOAD_MB", "10")))

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
