"""Unit tests for refresh scheduler helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from nostr_sdk import Coordinate, Keys, Kind, PublicKey

from gitlurker.config import Settings
from gitlurker.models.schemas import CommitData, GitHubResult, ProjectData, RepoSummary
from gitlurker.services.nostr import KIND_PROJECT, project_d_tag
from gitlurker.services.scheduler import (
    RefreshScheduler,
    SchedulerBudget,
    enrich_project_from_github,
    owner_repo_from_coordinate,
)


def test_owner_repo_from_coordinate_ok() -> None:
    pk = PublicKey.parse("aa" * 32)
    c = Coordinate(Kind(30078), pk, "Foo/Bar")
    assert owner_repo_from_coordinate(c) == ("Foo", "Bar")


def test_owner_repo_from_coordinate_invalid() -> None:
    pk = PublicKey.parse("aa" * 32)
    c = Coordinate(Kind(30078), pk, "nope")
    assert owner_repo_from_coordinate(c) is None


def test_scheduler_budget_remaining() -> None:
    b = SchedulerBudget(100)
    assert b.remaining() == 100
    b.record_request()
    assert b.remaining() == 99


@pytest.mark.asyncio
async def test_run_sweep_defers_project_when_hourly_budget_too_low(
    monkeypatch: pytest.MonkeyPatch,
    isolate_backend_env: None,
) -> None:
    keys = Keys.generate()
    monkeypatch.setenv("AUTH_TOKEN", "t")
    monkeypatch.setenv("LURKER_KEY", keys.secret_key().to_hex())
    monkeypatch.setenv("NOSTR_RELAYS", "")
    monkeypatch.setenv("NOSTR_PUBLISH_ENABLED", "false")
    monkeypatch.setenv("GITLURKER_OPERATOR_PUBKEYS", "")
    settings = Settings()

    coord = Coordinate(KIND_PROJECT, keys.public_key(), project_d_tag("a", "b"))
    budget = SchedulerBudget(30)
    for _ in range(30):
        budget.record_request()

    gh = MagicMock()
    gh.last_rate_limit_remaining = 9999
    nostr = MagicMock()
    nostr.tracked_coordinates = MagicMock(return_value=[coord])
    nostr.fetch_project_data_snapshot = AsyncMock()

    sched = RefreshScheduler(settings, gh, nostr, budget)
    await sched.run_sweep_once()

    nostr.fetch_project_data_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_run_sweep_skips_when_github_rate_limit_critical(
    monkeypatch: pytest.MonkeyPatch,
    isolate_backend_env: None,
) -> None:
    keys = Keys.generate()
    monkeypatch.setenv("AUTH_TOKEN", "t")
    monkeypatch.setenv("LURKER_KEY", keys.secret_key().to_hex())
    monkeypatch.setenv("NOSTR_RELAYS", "")
    monkeypatch.setenv("NOSTR_PUBLISH_ENABLED", "false")
    monkeypatch.setenv("GITLURKER_OPERATOR_PUBKEYS", "")
    settings = Settings()

    coord = Coordinate(KIND_PROJECT, keys.public_key(), project_d_tag("a", "b"))
    budget = SchedulerBudget(4000)
    gh = MagicMock()
    gh.last_rate_limit_remaining = 15
    nostr = MagicMock()
    nostr.tracked_coordinates = MagicMock(return_value=[coord])
    nostr.fetch_project_data_snapshot = AsyncMock()

    sched = RefreshScheduler(settings, gh, nostr, budget)
    await sched.run_sweep_once()

    nostr.fetch_project_data_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_release_without_github_release_uses_default_branch_commit() -> None:
    summary = RepoSummary(
        description="x",
        stars=1,
        forks=0,
        open_issues=0,
        html_url="https://github.com/o/r",
        default_branch="main",
        full_name="o/r",
    )
    commit = CommitData(
        sha_short="abc1234",
        date_iso="2025-06-15T12:00:00Z",
        author="dev",
        github_url="https://github.com/o/r/commit/abcdef1234567890",
    )
    gh = MagicMock()
    gh.get_repo_summary = AsyncMock(return_value=GitHubResult(summary, False))
    gh.get_latest_release = AsyncMock(return_value=GitHubResult(None, False))
    gh.get_latest_commit = AsyncMock(return_value=GitHubResult(commit, False))

    base = ProjectData(
        owner="o",
        repo="r",
        name="r",
        description="",
        category="bitcoin",
        subcategory="wallet",
        tracking_mode="release",
    )
    updated, ok = await enrich_project_from_github(gh, base)
    assert ok is True
    assert updated.stale is False
    assert updated.release_version is None
    assert updated.commit_date_iso == "2025-06-15T12:00:00Z"
    assert updated.commit_sha == "abcdef1234567890"


@pytest.mark.asyncio
async def test_enrich_tag_without_github_tag_uses_default_branch_commit() -> None:
    summary = RepoSummary(
        description="",
        stars=0,
        forks=0,
        open_issues=0,
        html_url="https://github.com/o/r",
        default_branch="main",
        full_name="o/r",
    )
    commit = CommitData(
        sha_short="def0123",
        date_iso="2025-01-01T00:00:00Z",
        author="",
        github_url="https://github.com/o/r/commit/abcd1234567890abcdef1234567890abcd1234",
    )
    gh = MagicMock()
    gh.get_repo_summary = AsyncMock(return_value=GitHubResult(summary, False))
    gh.get_latest_tag = AsyncMock(return_value=GitHubResult(None, False))
    gh.get_latest_commit = AsyncMock(return_value=GitHubResult(commit, False))

    base = ProjectData(
        owner="o",
        repo="r",
        name="r",
        description="",
        category="bitcoin",
        subcategory="wallet",
        tracking_mode="tag",
    )
    updated, ok = await enrich_project_from_github(gh, base)
    assert ok is True
    assert updated.tag_name is None
    assert updated.commit_sha == "abcd1234567890abcdef1234567890abcd1234"
    assert updated.commit_date_iso == "2025-01-01T00:00:00Z"
