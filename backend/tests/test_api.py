"""FastAPI API tests with mocked GitHub and Nostr services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from gitlurker.config import Settings
from gitlurker.main import create_app
from gitlurker.models.schemas import (
    CommitData,
    ContributorEntry,
    GitHubResult,
    OwnerRepoEntry,
    ReleaseData,
    RepoSummary,
    TagData,
)


class _FakePk:
    def to_hex(self) -> str:
        return "aa" * 32


def _fake_nostr() -> MagicMock:
    n = MagicMock()
    n.public_key = _FakePk()
    n.start = AsyncMock()
    n.stop = AsyncMock()
    n.fetch_project_data_snapshot = AsyncMock(return_value=None)
    n.tracked_coordinates = MagicMock(return_value=[])
    return n


def _settings(**kwargs: object) -> Settings:
    base = dict(
        github_token="test-token",
        lurker_secret_hex="",
        nostr_relays_raw="",
        nostr_use_public_relays=False,
        nostr_publish_enabled=False,
        app_environment="development",
        api_github_rate_limit_per_minute=500,
        api_github_cache_ttl_seconds=0,
        gitlurker_dev_dummy_api=False,
    )
    base.update(kwargs)
    return Settings.model_construct(**base)


@pytest.fixture
def gh_mock() -> MagicMock:
    m = MagicMock()
    m.is_configured.return_value = True
    m.aclose = AsyncMock()
    return m


@pytest.fixture
def client(gh_mock: MagicMock) -> TestClient:
    app = create_app(
        enable_background=False,
        settings=_settings(),
        github_api=gh_mock,
        nostr_service=_fake_nostr(),
    )
    with TestClient(app) as c:
        yield c


def test_nip05_ok(client: TestClient) -> None:
    r = client.get("/.well-known/nostr.json", params={"name": "_"})
    assert r.status_code == 200
    assert r.json() == {"names": {"_": "aa" * 32}}
    assert r.headers.get("access-control-allow-origin") == "*"


def test_nip05_wrong_name(client: TestClient) -> None:
    r = client.get("/.well-known/nostr.json", params={"name": "other"})
    assert r.status_code == 404


def test_nip05_no_pubkey(gh_mock: MagicMock) -> None:
    n = _fake_nostr()
    n.public_key = None
    app = create_app(
        enable_background=False,
        settings=_settings(),
        github_api=gh_mock,
        nostr_service=n,
    )
    with TestClient(app) as c:
        r = c.get("/.well-known/nostr.json", params={"name": "_"})
    assert r.status_code == 404


def test_owner_detail(client: TestClient, gh_mock: MagicMock) -> None:
    gh_mock.get_owner_repos = AsyncMock(
        return_value=GitHubResult(
            [
                OwnerRepoEntry(
                    name="r",
                    full_name="o/r",
                    description="d",
                    html_url="https://github.com/o/r",
                    private=False,
                    fork=False,
                    pushed_at_iso="",
                ),
            ],
            False,
        ),
    )
    gh_mock.get_org_members = AsyncMock(return_value=GitHubResult([], False))
    gh_mock.get_org_teams = AsyncMock(return_value=GitHubResult([], False))
    r = client.get("/api/v1/owner/o")
    assert r.status_code == 200
    j = r.json()
    assert j["github_url"] == "https://github.com/o"
    assert len(j["repos"]) == 1
    assert j["repos"][0]["name"] == "r"
    assert j["members"] == []
    assert j["teams"] == []


def test_repo_detail(client: TestClient, gh_mock: MagicMock) -> None:
    gh_mock.get_repo_summary = AsyncMock(
        return_value=GitHubResult(
            RepoSummary(
                description="Hello",
                stars=10,
                forks=2,
                open_issues=3,
                html_url="https://github.com/o/r",
                default_branch="main",
                full_name="o/r",
            ),
            False,
        ),
    )
    gh_mock.get_contributors = AsyncMock(
        return_value=GitHubResult(
            [
                ContributorEntry(
                    login="alice",
                    name=None,
                    avatar_url="",
                    contributions=5,
                    html_url="https://github.com/alice",
                ),
            ],
            False,
        ),
    )
    r = client.get("/api/v1/repo/o/r")
    assert r.status_code == 200
    j = r.json()
    assert j["description"] == "Hello"
    assert j["stars"] == 10
    assert j["forks"] == 2
    assert j["issues"] == 3
    assert j["contributors"][0]["login"] == "alice"
    assert j["github_url"] == "https://github.com/o/r"


def test_release_latest(client: TestClient, gh_mock: MagicMock) -> None:
    gh_mock.get_repo_summary = AsyncMock(
        return_value=GitHubResult(
            RepoSummary(
                description="",
                stars=0,
                forks=0,
                open_issues=0,
                html_url="https://github.com/o/r",
                default_branch="main",
                full_name="o/r",
            ),
            False,
        ),
    )
    gh_mock.get_latest_release = AsyncMock(
        return_value=GitHubResult(
            ReleaseData(
                version="v1.0.0",
                publisher="bob",
                published_at_iso="2024-01-01T00:00:00Z",
                notes_markdown="# Hi",
                notes_html="<h1>Hi</h1>",
                github_url="https://github.com/o/r/releases/tag/v1.0.0",
            ),
            False,
        ),
    )
    r = client.get("/api/v1/release/o/r")
    assert r.status_code == 200
    j = r.json()
    assert j["version"] == "v1.0.0"
    assert j["publisher"] == "bob"
    assert j["notes_html"] == "<h1>Hi</h1>"


def test_release_fallback_tag(client: TestClient, gh_mock: MagicMock) -> None:
    gh_mock.get_repo_summary = AsyncMock(
        return_value=GitHubResult(
            RepoSummary(
                description="",
                stars=0,
                forks=0,
                open_issues=0,
                html_url="https://github.com/o/r",
                default_branch="main",
                full_name="o/r",
            ),
            False,
        ),
    )
    gh_mock.get_latest_release = AsyncMock(return_value=GitHubResult(None, False))
    gh_mock.get_latest_tag = AsyncMock(
        return_value=GitHubResult(
            TagData(
                name="t1",
                date_iso="2024-02-02",
                github_url="https://github.com/o/r/releases/tag/t1",
            ),
            False,
        ),
    )
    r = client.get("/api/v1/release/o/r")
    assert r.status_code == 200
    assert r.json()["version"] == "t1"


def test_release_fallback_commit(client: TestClient, gh_mock: MagicMock) -> None:
    gh_mock.get_repo_summary = AsyncMock(
        return_value=GitHubResult(
            RepoSummary(
                description="",
                stars=0,
                forks=0,
                open_issues=0,
                html_url="https://github.com/o/r",
                default_branch="main",
                full_name="o/r",
            ),
            False,
        ),
    )
    gh_mock.get_latest_release = AsyncMock(return_value=GitHubResult(None, False))
    gh_mock.get_latest_tag = AsyncMock(return_value=GitHubResult(None, False))
    gh_mock.get_latest_commit = AsyncMock(
        return_value=GitHubResult(
            CommitData(
                sha_short="abc1234",
                date_iso="2024-03-03",
                author="dev",
                github_url="https://github.com/o/r/commit/fullsha",
            ),
            False,
        ),
    )
    gh_mock.get_readme_html = AsyncMock(
        return_value=GitHubResult("<p>readme</p>", False),
    )
    r = client.get("/api/v1/release/o/r")
    assert r.status_code == 200
    j = r.json()
    assert j["version"] == "Latest commit"
    assert j["publisher"] == "dev"
    assert j["notes_html"] == "<p>readme</p>"
    assert j["commit_sha_short"] == "abc1234"


def test_github_not_configured(gh_mock: MagicMock) -> None:
    gh_mock.is_configured.return_value = False
    app = create_app(
        enable_background=False,
        settings=_settings(),
        github_api=gh_mock,
        nostr_service=_fake_nostr(),
    )
    with TestClient(app) as c:
        r = c.get("/api/v1/owner/foo")
    assert r.status_code == 503


def test_invalid_owner_slug(client: TestClient) -> None:
    r = client.get("/api/v1/owner/not!allowed")
    assert r.status_code == 400


def test_repo_detail_uses_cache(gh_mock: MagicMock) -> None:
    gh_mock.get_repo_summary = AsyncMock(
        return_value=GitHubResult(
            RepoSummary(
                description="cached",
                stars=1,
                forks=0,
                open_issues=0,
                html_url="https://github.com/o/r",
                default_branch="main",
                full_name="o/r",
            ),
            False,
        ),
    )
    gh_mock.get_contributors = AsyncMock(return_value=GitHubResult([], False))
    app = create_app(
        enable_background=False,
        settings=Settings.model_construct(
            github_token="t",
            lurker_secret_hex="",
            nostr_relays_raw="",
            nostr_use_public_relays=False,
            nostr_publish_enabled=False,
            app_environment="development",
            api_github_rate_limit_per_minute=500,
            api_github_cache_ttl_seconds=300,
            gitlurker_dev_dummy_api=False,
        ),
        github_api=gh_mock,
        nostr_service=_fake_nostr(),
    )
    with TestClient(app) as c:
        assert c.get("/api/v1/repo/o/r").status_code == 200
        assert c.get("/api/v1/repo/o/r").status_code == 200
    assert gh_mock.get_repo_summary.await_count == 1
    assert gh_mock.get_contributors.await_count == 1


def test_dev_dummy_api_owner_repo_release(gh_mock: MagicMock) -> None:
    gh_mock.is_configured.return_value = False
    app = create_app(
        enable_background=False,
        settings=_settings(github_token="", gitlurker_dev_dummy_api=True),
        github_api=gh_mock,
        nostr_service=_fake_nostr(),
    )
    with TestClient(app) as c:
        o = c.get("/api/v1/owner/demo-org")
        assert o.status_code == 200
        assert o.json()["github_url"] == "https://github.com/demo-org"
        assert any(r["name"] == "sample-repo" for r in o.json()["repos"])
        r = c.get("/api/v1/repo/demo-org/sample-repo")
        assert r.status_code == 200
        assert r.json()["stars"] == 42
        rel = c.get("/api/v1/release/demo-org/sample-repo")
        assert rel.status_code == 200
        assert rel.json()["version"] == "v1.2.0"


def test_github_api_rate_limit(gh_mock: MagicMock) -> None:
    gh_mock.get_owner_repos = AsyncMock(return_value=GitHubResult([], False))
    gh_mock.get_org_members = AsyncMock(return_value=GitHubResult([], False))
    gh_mock.get_org_teams = AsyncMock(return_value=GitHubResult([], False))
    app = create_app(
        enable_background=False,
        settings=Settings.model_construct(
            github_token="t",
            lurker_secret_hex="",
            nostr_relays_raw="",
            nostr_use_public_relays=False,
            nostr_publish_enabled=False,
            app_environment="development",
            api_github_rate_limit_per_minute=2,
            api_github_cache_ttl_seconds=0,
            gitlurker_dev_dummy_api=False,
        ),
        github_api=gh_mock,
        nostr_service=_fake_nostr(),
    )
    with TestClient(app) as c:
        assert c.get("/api/v1/owner/x").status_code == 200
        assert c.get("/api/v1/owner/x").status_code == 200
        r = c.get("/api/v1/owner/x")
    assert r.status_code == 429
