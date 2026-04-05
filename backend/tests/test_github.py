"""Unit tests for `GitHubService` (mocked httpx transport)."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable

import httpx
import pytest

from gitlurker.services.github import GitHubService


def _json_response(
    data: object, status: int = 200, headers: dict[str, str] | None = None
) -> httpx.Response:
    body = json.dumps(data).encode()
    return httpx.Response(status, content=body, headers=headers or {})


def make_transport(
    router: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(router)


@pytest.mark.asyncio
async def test_get_repo_summary_success() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/o/r"
        return _json_response(
            {
                "description": "Hello",
                "stargazers_count": 5,
                "forks_count": 2,
                "open_issues_count": 1,
                "html_url": "https://github.com/o/r",
                "default_branch": "main",
                "full_name": "o/r",
            },
        )

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_repo_summary("o", "r")
        assert not out.stale
        assert out.data is not None
        assert out.data.stars == 5
        assert out.data.description == "Hello"
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_repo_summary_404_stale() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_repo_summary("o", "r")
        assert out.stale
        assert out.data is None
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_repo_summary_rename_stale() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "description": None,
                "stargazers_count": 0,
                "forks_count": 0,
                "open_issues_count": 0,
                "html_url": "https://github.com/new/name",
                "default_branch": "main",
                "full_name": "new/name",
            },
        )

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_repo_summary("o", "r")
        assert out.stale
        assert out.data is None
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_check_repo_redirect_stale() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/o/r":
            return httpx.Response(
                301,
                headers={"Location": "https://api.github.com/repos/other/r"},
            )
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        assert await svc.check_repo_stale("o", "r") is True
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_latest_release_success_and_no_release() -> None:
    release_json = {
        "tag_name": "v1.0.0",
        "name": "v1.0.0",
        "body": "# Notes\n\nHi",
        "published_at": "2024-06-01T12:00:00Z",
        "html_url": "https://github.com/o/r/releases/tag/v1.0.0",
        "author": {"login": "alice"},
    }

    def route(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/repos/o/r":
            return _json_response(
                {
                    "full_name": "o/r",
                    "description": "x",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "https://github.com/o/r",
                    "default_branch": "main",
                },
            )
        if p == "/repos/o/r/releases/latest":
            return _json_response(release_json)
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_latest_release("o", "r")
        assert not out.stale
        assert out.data is not None
        assert out.data.version == "v1.0.0"
        assert out.data.publisher == "alice"
        assert "<h1>" in out.data.notes_html or "<h1" in out.data.notes_html
    finally:
        await svc.aclose()

    def route404(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/repos/o/r":
            return _json_response(
                {
                    "full_name": "o/r",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "https://github.com/o/r",
                    "default_branch": "main",
                },
            )
        if p == "/repos/o/r/releases/latest":
            return httpx.Response(404)
        return httpx.Response(404)

    svc2 = GitHubService("token", transport=make_transport(route404))
    try:
        out2 = await svc2.get_latest_release("o", "r")
        assert not out2.stale
        assert out2.data is None
    finally:
        await svc2.aclose()


@pytest.mark.asyncio
async def test_get_latest_tag() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/repos/o/r":
            return _json_response(
                {
                    "full_name": "o/r",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "https://github.com/o/r",
                    "default_branch": "main",
                },
            )
        if p == "/repos/o/r/tags":
            return _json_response(
                [{"name": "v0.1", "commit": {"sha": "abcdef1234567890abcdef1234567890abcd"}}],
            )
        if p == "/repos/o/r/commits/abcdef1234567890abcdef1234567890abcd":
            return _json_response(
                {
                    "sha": "abcdef",
                    "html_url": "https://github.com/o/r/commit/abcdef",
                    "commit": {
                        "committer": {"date": "2024-01-02T00:00:00Z"},
                        "author": {"name": "Bob"},
                    },
                },
            )
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_latest_tag("o", "r")
        assert not out.stale
        assert out.data is not None
        assert out.data.name == "v0.1"
        assert "2024-01-02" in out.data.date_iso
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_latest_commit() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/repos/o/r":
            return _json_response(
                {
                    "full_name": "o/r",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "https://github.com/o/r",
                    "default_branch": "develop",
                },
            )
        if p == "/repos/o/r/commits":
            return _json_response(
                [
                    {
                        "sha": "fedcba9876543210fedcba9876543210fedcba98",
                        "html_url": "https://github.com/o/r/commit/fedcba",
                        "commit": {
                            "committer": {"date": "2024-03-03T00:00:00Z"},
                            "author": {"name": "Carol"},
                        },
                    },
                ],
            )
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_latest_commit("o", "r")
        assert not out.stale
        assert out.data is not None
        assert out.data.sha_short == "fedcba9"
        assert out.data.author == "Carol"
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_contributors_top50() -> None:
    contribs = [
        {
            "login": f"u{i}",
            "contributions": 100 - i,
            "avatar_url": "",
            "html_url": f"https://github.com/u{i}",
        }
        for i in range(3)
    ]

    def route(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/repos/o/r":
            return _json_response(
                {
                    "full_name": "o/r",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "https://github.com/o/r",
                    "default_branch": "main",
                },
            )
        if p == "/repos/o/r/contributors":
            return _json_response(contribs)
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_contributors("o", "r", limit=50)
        assert not out.stale
        assert out.data is not None
        assert len(out.data) == 3
        assert out.data[0].login == "u0"
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_owner_repos_org_then_user() -> None:
    repos = [{"name": "a", "full_name": "o/a", "html_url": "https://github.com/o/a"}]

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/orgs/o/repos":
            return httpx.Response(404)
        if request.url.path == "/users/o/repos":
            return _json_response(repos)
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_owner_repos("o")
        assert not out.stale
        assert out.data is not None
        assert len(out.data) == 1
        assert out.data[0].name == "a"
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_org_members_404_empty() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/orgs/notorg/public_members":
            return httpx.Response(404)
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_org_members("notorg")
        assert not out.stale
        assert out.data == []
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_repo_summary_non_json_body() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/o/r":
            return httpx.Response(200, content=b"not-json{")
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_repo_summary("o", "r")
        assert out.data is None
        assert not out.stale
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_429_retries_then_success() -> None:
    calls = {"n": 0}
    release_json = {
        "tag_name": "v1",
        "body": "",
        "published_at": "2024-01-01T00:00:00Z",
        "html_url": "https://github.com/o/r/releases/tag/v1",
        "author": {"login": "x"},
    }

    def route(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/repos/o/r":
            return _json_response(
                {
                    "full_name": "o/r",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "https://github.com/o/r",
                    "default_branch": "main",
                },
            )
        if p == "/repos/o/r/releases/latest":
            calls["n"] += 1
            if calls["n"] < 2:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return _json_response(release_json)
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_latest_release("o", "r")
        assert calls["n"] == 2
        assert out.data is not None
        assert out.data.version == "v1"
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_readme_html_decodes_markdown() -> None:
    raw_md = "# Hi\n"
    b64 = base64.b64encode(raw_md.encode()).decode()

    def route(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/repos/o/r":
            return _json_response(
                {
                    "full_name": "o/r",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "https://github.com/o/r",
                    "default_branch": "main",
                },
            )
        if p == "/repos/o/r/readme":
            return _json_response({"encoding": "base64", "content": b64})
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_readme_html("o", "r")
        assert not out.stale
        assert out.data is not None
        assert "<h1>Hi</h1>" in out.data
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_get_org_teams_ok() -> None:
    teams = [
        {
            "name": "Core",
            "slug": "core",
            "description": "Maintainers",
            "html_url": "https://github.com/orgs/o/teams/core",
        },
    ]

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/orgs/o/teams":
            return _json_response(teams)
        return httpx.Response(404)

    svc = GitHubService("token", transport=make_transport(route))
    try:
        out = await svc.get_org_teams("o")
        assert not out.stale
        assert out.data is not None
        assert len(out.data) == 1
        assert out.data[0].slug == "core"
        assert out.data[0].name == "Core"
    finally:
        await svc.aclose()
