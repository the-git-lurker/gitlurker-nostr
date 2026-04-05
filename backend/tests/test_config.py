"""Tests for settings loading (env aliases and relay resolution)."""

import pytest

from gitlurker.config import PUBLIC_RELAY_DEFAULTS, Settings, get_settings


@pytest.fixture
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear env vars that affect Settings so .env files do not leak into tests."""
    keys = (
        "AUTH_TOKEN",
        "GITHUB_TOKEN",
        "LURKER_KEY",
        "GITLURKER_NSEC_HEX",
        "NOSTR_RELAYS",
        "RELAYS",
        "NOSTR_USE_PUBLIC_RELAYS",
        "NOSTR_PUBLISH_ENABLED",
    )
    for k in keys:
        monkeypatch.delenv(k, raising=False)


def test_auth_token_alias_github_token(monkeypatch: pytest.MonkeyPatch, isolate_env: None) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_alias")
    s = Settings()
    assert s.github_token == "ghp_from_alias"


def test_auth_token_prefers_auth_token(monkeypatch: pytest.MonkeyPatch, isolate_env: None) -> None:
    monkeypatch.setenv("AUTH_TOKEN", "ghp_primary")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_other")
    s = Settings()
    assert s.github_token == "ghp_primary"


def test_nostr_relays_from_csv(monkeypatch: pytest.MonkeyPatch, isolate_env: None) -> None:
    monkeypatch.setenv(
        "NOSTR_RELAYS",
        "ws://127.0.0.1:7777,wss://relay.damus.io",
    )
    s = Settings()
    assert s.nostr_relays == ["ws://127.0.0.1:7777", "wss://relay.damus.io"]


def test_nostr_use_public_relays_when_empty(
    monkeypatch: pytest.MonkeyPatch, isolate_env: None
) -> None:
    monkeypatch.setenv("NOSTR_USE_PUBLIC_RELAYS", "true")
    monkeypatch.delenv("NOSTR_RELAYS", raising=False)
    monkeypatch.delenv("RELAYS", raising=False)
    s = Settings()
    assert s.nostr_relays == list(PUBLIC_RELAY_DEFAULTS)


def test_lurker_key_valid_hex(monkeypatch: pytest.MonkeyPatch, isolate_env: None) -> None:
    key = "a" * 64
    monkeypatch.setenv("LURKER_KEY", key)
    s = Settings()
    assert s.lurker_secret_hex == key.lower()


def test_lurker_key_invalid_rejected(monkeypatch: pytest.MonkeyPatch, isolate_env: None) -> None:
    monkeypatch.setenv("LURKER_KEY", "not_hex")
    with pytest.raises(ValueError, match="64 hexadecimal"):
        Settings()


def test_get_settings_returns_instance(
    monkeypatch: pytest.MonkeyPatch,
    isolate_env: None,
) -> None:
    monkeypatch.setenv("AUTH_TOKEN", "test_token_for_factory")
    s = get_settings()
    assert isinstance(s, Settings)
    assert s.github_token == "test_token_for_factory"


def test_operator_pubkeys_parsed(monkeypatch: pytest.MonkeyPatch, isolate_env: None) -> None:
    a = "a" * 64
    b = "b" * 64
    monkeypatch.setenv("GITLURKER_OPERATOR_PUBKEYS", f"{a},{b}")
    s = Settings()
    assert s.operator_pubkeys == [a, b]
