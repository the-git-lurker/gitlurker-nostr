"""Integration-style tests: scheduler refresh with mocked GitHub + Nostr.

Operator DM add/remove flows are covered in ``tests/test_nostr.py`` (e.g.
``test_apply_dm_add_and_remove_tracked``).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from nostr_sdk import Coordinate, Keys

from gitlurker.config import Settings
from gitlurker.models.schemas import GitHubResult, ReleaseData, RepoSummary
from gitlurker.services.nostr import KIND_PROJECT, project_d_tag
from gitlurker.services.scheduler import RefreshScheduler, SchedulerBudget


@pytest.mark.asyncio
async def test_refresh_cycle_publishes_project_and_release_announcement(
    monkeypatch: pytest.MonkeyPatch,
    isolate_backend_env: None,
) -> None:
    keys = Keys.generate()
    monkeypatch.setenv("AUTH_TOKEN", "ghp_test_integration")
    monkeypatch.setenv("LURKER_KEY", keys.secret_key().to_hex())
    monkeypatch.setenv("NOSTR_RELAYS", "")
    monkeypatch.setenv("NOSTR_PUBLISH_ENABLED", "false")
    monkeypatch.setenv("GITLURKER_OPERATOR_PUBKEYS", "")
    settings = Settings()

    coord = Coordinate(KIND_PROJECT, keys.public_key(), project_d_tag("o", "r"))

    gh = MagicMock()
    gh.last_rate_limit_remaining = 5000
    gh.get_repo_summary = AsyncMock(
        return_value=GitHubResult(
            RepoSummary(
                description="hello",
                stars=4,
                forks=2,
                open_issues=1,
                html_url="https://github.com/o/r",
                default_branch="main",
                full_name="o/r",
            ),
            False,
        ),
    )
    gh.get_latest_release = AsyncMock(
        return_value=GitHubResult(
            ReleaseData(
                version="v9.0.0",
                publisher="bot",
                published_at_iso="2025-01-01T00:00:00Z",
                notes_markdown="notes",
                notes_html="<p>notes</p>",
                github_url="https://github.com/o/r/releases/tag/v9.0.0",
            ),
            False,
        ),
    )

    nostr = MagicMock()
    nostr.tracked_coordinates = MagicMock(return_value=[coord])
    nostr.fetch_project_data_snapshot = AsyncMock(return_value=None)
    nostr.publish_project = AsyncMock()
    nostr.publish_release_announcement = AsyncMock()

    budget = SchedulerBudget(50_000)
    sched = RefreshScheduler(settings, gh, nostr, budget)
    await sched.run_sweep_once()

    nostr.publish_project.assert_awaited()
    nostr.publish_release_announcement.assert_awaited()
    gh.get_repo_summary.assert_awaited()
    gh.get_latest_release.assert_awaited()
