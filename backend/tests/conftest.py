"""Shared pytest fixtures for the GitLurker backend."""

from __future__ import annotations

import pytest


@pytest.fixture
def isolate_backend_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear env vars so tests control Settings without leaking host .env files."""
    keys = (
        "AUTH_TOKEN",
        "GITHUB_TOKEN",
        "LURKER_KEY",
        "GITLURKER_NSEC_HEX",
        "NOSTR_RELAYS",
        "RELAYS",
        "NOSTR_USE_PUBLIC_RELAYS",
        "NOSTR_PUBLISH_ENABLED",
        "GITLURKER_OPERATOR_PUBKEYS",
        "GITLURKER_REVIEWER_PUBKEYS",
        "API_GITHUB_RATE_LIMIT_PER_MINUTE",
        "API_GITHUB_CACHE_TTL_SECONDS",
    )
    for k in keys:
        monkeypatch.delenv(k, raising=False)
