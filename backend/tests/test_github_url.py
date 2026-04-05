"""Tests for ``gitlurker.github_url``."""

from __future__ import annotations

import pytest

from gitlurker.github_url import parse_github_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://github.com/foo/bar", ("foo", "bar")),
        ("github.com/foo/bar", ("foo", "bar")),
        ("https://github.com/foo/bar.git", ("foo", "bar")),
        (
            "https://github.com/OCEAN-xyz/datum_gateway/releases/tag/v0.3.0beta",
            ("OCEAN-xyz", "datum_gateway"),
        ),
        (
            "https://github.com/CodyTseng/nostr-relay-tray?tab=readme-ov-file",
            ("CodyTseng", "nostr-relay-tray"),
        ),
        ("https://github.com/UTXOnly/nostpy-relay/tree/main", ("UTXOnly", "nostpy-relay")),
        ("git@github.com:fiatjaf/narr.git", ("fiatjaf", "narr")),
    ],
)
def test_parse_github_url_ok(raw: str, expected: tuple[str, str]) -> None:
    assert parse_github_url(raw) == expected


def test_parse_github_url_rejects_non_github() -> None:
    assert parse_github_url("https://gitlab.com/a/b") is None


def test_parse_github_url_owner_only() -> None:
    assert parse_github_url("https://github.com/solo") is None
