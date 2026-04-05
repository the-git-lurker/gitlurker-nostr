"""Load configuration from environment and optional `.env` files.

Canonical names:
- GitHub token: ``AUTH_TOKEN`` (preferred) or ``GITHUB_TOKEN``.
- Nostr secret (hex): ``LURKER_KEY``.

Dotenv files are **not** loaded automatically when this module is imported (so tests and
tools control the environment). Call :func:`load_gitlurker_dotenv` once at process
startup (e.g. FastAPI lifespan) before :func:`get_settings`.

Discovery order (each file overrides keys from the previous):

1. ``backend/.env``
2. ``gitlurker/.env`` (implementation root)
3. Repo root ``.env``
4. Repo root ``.env.dev``
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")

# Default public relays when ``NOSTR_USE_PUBLIC_RELAYS=true`` and ``NOSTR_RELAYS`` is empty.
PUBLIC_RELAY_DEFAULTS: tuple[str, ...] = (
    "wss://relay.damus.io",
    "wss://relay.primal.net",
    "wss://nostr.mom",
)


def _discover_env_files() -> tuple[Path, ...]:
    """Paths to existing env files: backend → gitlurker → repo root."""
    backend_dir = Path(__file__).resolve().parents[1]
    gitlurker_root = backend_dir.parent
    repo_root = gitlurker_root.parent

    candidates = (
        backend_dir / ".env",
        gitlurker_root / ".env",
        repo_root / ".env",
        repo_root / ".env.dev",
    )
    return tuple(p for p in candidates if p.is_file())


def load_gitlurker_dotenv() -> None:
    """Load dotenv files in order; later files override earlier keys."""
    for path in _discover_env_files():
        print(f"Loading env from {path}")
        load_dotenv(path, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GitHub
    github_token: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("AUTH_TOKEN", "GITHUB_TOKEN"),
            description="GitHub PAT for REST API",
        ),
    ]

    # Nostr identity
    lurker_secret_hex: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("LURKER_KEY", "GITLURKER_NSEC_HEX"),
            description="32-byte secret key as 64 hex chars",
        ),
    ]

    nostr_relays_raw: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("NOSTR_RELAYS", "RELAYS"),
            description="Comma-separated relay URLs",
        ),
    ]

    nostr_use_public_relays: bool = Field(
        default=False,
        validation_alias=AliasChoices("NOSTR_USE_PUBLIC_RELAYS"),
    )

    nostr_publish_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("NOSTR_PUBLISH_ENABLED"),
    )

    github_primary_limit_per_hour: int = Field(
        default=5000,
        ge=1,
        validation_alias=AliasChoices("GITHUB_PRIMARY_LIMIT_PER_HOUR"),
    )

    github_scheduler_budget_per_hour: int = Field(
        default=4000,
        ge=1,
        validation_alias=AliasChoices("GITHUB_SCHEDULER_BUDGET_PER_HOUR"),
    )

    refresh_interval_seconds: int = Field(
        default=3600,
        ge=60,
        validation_alias=AliasChoices("REFRESH_INTERVAL_SECONDS"),
    )

    github_max_concurrent_requests: int = Field(
        default=6,
        ge=1,
        le=50,
        validation_alias=AliasChoices("GITHUB_MAX_CONCURRENT_REQUESTS"),
    )

    gitlurker_operator_pubkeys_raw: str = Field(
        default="",
        validation_alias=AliasChoices("GITLURKER_OPERATOR_PUBKEYS"),
    )

    gitlurker_reviewer_pubkeys_raw: str = Field(
        default="",
        validation_alias=AliasChoices("GITLURKER_REVIEWER_PUBKEYS"),
    )

    nostr_eose_grace_ms: int = Field(
        default=800,
        ge=0,
        le=10_000,
        validation_alias=AliasChoices("NOSTR_EOSE_GRACE_MS"),
    )

    app_environment: Literal["development", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("GITLURKER_ENV", "APP_ENV"),
    )

    api_github_rate_limit_per_minute: int = Field(
        default=45,
        ge=1,
        le=10_000,
        validation_alias=AliasChoices("API_GITHUB_RATE_LIMIT_PER_MINUTE"),
        description="Per-IP rate limit for GitHub-backed REST endpoints",
    )

    api_github_cache_ttl_seconds: int = Field(
        default=90,
        ge=0,
        le=3600,
        validation_alias=AliasChoices("API_GITHUB_CACHE_TTL_SECONDS"),
        description="TTL for in-process cache of repo/owner API responses; 0 disables",
    )

    gitlurker_dev_dummy_api: bool = Field(
        default=False,
        validation_alias=AliasChoices("GITLURKER_DEV_DUMMY_API"),
        description="Return static JSON for /api/v1 owner/repo/release (local UI review; no token)",
    )

    @field_validator("lurker_secret_hex")
    @classmethod
    def validate_lurker_key(cls, v: str) -> str:
        s = v.strip()
        if not s:
            return ""
        if not _HEX64.match(s):
            msg = "LURKER_KEY must be 64 hexadecimal characters"
            raise ValueError(msg)
        return s.lower()

    @property
    def nostr_relays(self) -> list[str]:
        """Resolved relay URLs for clients and backend connections."""
        raw = self.nostr_relays_raw.strip()
        if raw:
            return [p.strip() for p in raw.split(",") if p.strip()]
        if self.nostr_use_public_relays:
            return list(PUBLIC_RELAY_DEFAULTS)
        return []

    @property
    def operator_pubkeys(self) -> list[str]:
        return _split_hex_pubkeys(self.gitlurker_operator_pubkeys_raw)

    @property
    def reviewer_pubkeys(self) -> list[str]:
        return _split_hex_pubkeys(self.gitlurker_reviewer_pubkeys_raw)


def _split_hex_pubkeys(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.split(","):
        p = part.strip().lower()
        if not p:
            continue
        if len(p) == 64 and _HEX64.match(p):
            out.append(p)
    return out


def get_settings() -> Settings:
    """Return a new Settings instance (reads the current process environment)."""
    return Settings()


__all__ = [
    "PUBLIC_RELAY_DEFAULTS",
    "Settings",
    "get_settings",
    "load_gitlurker_dotenv",
]
