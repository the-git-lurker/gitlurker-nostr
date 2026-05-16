"""Async GitHub REST API client (Phase 3)."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
import markdown

from gitlurker.models.schemas import (
    CommitData,
    ContributorEntry,
    GitHubResult,
    OrgMemberEntry,
    OrgTeamEntry,
    OwnerRepoEntry,
    ReleaseData,
    RepoSummary,
    TagData,
)

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_ACCEPT = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"


def _truncate_sha(sha: str, n: int = 7) -> str:
    s = sha.strip()
    return s[:n] if len(s) >= n else s


def _md_to_html(text: str) -> str:
    if not text:
        return ""
    return markdown.markdown(
        text,
        extensions=["fenced_code", "tables"],
        output_format="html",
    )


class GitHubService:
    """httpx-based async GitHub REST v3 client with basic rate-limit handling."""

    def __init__(
        self,
        github_token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
        on_request: Callable[[], None] | None = None,
    ) -> None:
        headers: dict[str, str] = {
            "Accept": GITHUB_ACCEPT,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        token = github_token.strip()
        self._token = token
        self._on_request = on_request
        self.last_rate_limit_remaining: int | None = None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def is_configured(self) -> bool:
        return bool(self._token)

    async def _sleep_for_rate_limit(self, response: httpx.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 3600.0)
            except ValueError:
                pass
        reset_s = response.headers.get("X-RateLimit-Reset")
        if reset_s:
            try:
                target = float(reset_s)
                return min(max(target - time.time(), 0.5), 3600.0)
            except ValueError:
                pass
        return 60.0

    async def _request(
        self,
        method: str,
        path: str,
        *,
        follow_redirects: bool = True,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> httpx.Response:
        last: httpx.Response | None = None
        for attempt in range(max_retries):
            response = await self._client.request(
                method,
                path,
                follow_redirects=follow_redirects,
                **kwargs,
            )
            last = response
            rem = response.headers.get("X-RateLimit-Remaining")
            if rem is not None:
                try:
                    self.last_rate_limit_remaining = int(rem)
                except ValueError:
                    pass
            if self._on_request is not None:
                self._on_request()
            if response.status_code == 429:
                delay = await self._sleep_for_rate_limit(response)
                logger.warning(
                    "GitHub 429; backing off %.1fs (attempt %s/%s)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
                continue
            if response.status_code in (502, 503, 504) and attempt < max_retries - 1:
                delay = min(0.5 * (2**attempt), 8.0)
                logger.warning(
                    "GitHub %s; retry in %.1fs (attempt %s/%s)",
                    response.status_code,
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
                continue
            return response
        assert last is not None
        return last

    async def _repo_root_response(
        self,
        owner: str,
        repo: str,
        *,
        follow_redirects: bool,
    ) -> httpx.Response:
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}",
            follow_redirects=follow_redirects,
        )

    def _full_name_mismatch(self, owner: str, repo: str, data: dict[str, Any]) -> bool:
        full = (data.get("full_name") or "").lower()
        expected = f"{owner}/{repo}".lower()
        return bool(full and full != expected)

    async def check_repo_stale(self, owner: str, repo: str) -> bool:
        """True if the repo appears deleted, moved, or renamed (FR-29)."""
        r0 = await self._repo_root_response(owner, repo, follow_redirects=False)
        if r0.status_code in (301, 302, 307, 308):
            return True
        if r0.status_code == 200:
            try:
                data = r0.json()
            except Exception:
                return False
            return self._full_name_mismatch(owner, repo, data)
        if r0.status_code == 404:
            r1 = await self._repo_root_response(owner, repo, follow_redirects=True)
            if r1.status_code != 200:
                return True
            try:
                data = r1.json()
            except Exception:
                return True
            return self._full_name_mismatch(owner, repo, data)
        return False

    async def get_repo_summary(self, owner: str, repo: str) -> GitHubResult[RepoSummary]:
        r = await self._repo_root_response(owner, repo, follow_redirects=True)
        if r.status_code == 404:
            return GitHubResult(None, stale=True)
        if r.status_code != 200:
            return GitHubResult(None, stale=False)
        try:
            data = r.json()
        except Exception:
            return GitHubResult(None, stale=False)
        if self._full_name_mismatch(owner, repo, data):
            return GitHubResult(None, stale=True)
        raw_desc = data.get("description")
        if isinstance(raw_desc, str) or raw_desc is None:
            description: str | None = raw_desc
        else:
            description = None
        summary = RepoSummary(
            description=description,
            stars=int(data.get("stargazers_count") or 0),
            forks=int(data.get("forks_count") or 0),
            open_issues=int(data.get("open_issues_count") or 0),
            html_url=str(data.get("html_url") or ""),
            default_branch=str(data.get("default_branch") or "main"),
            full_name=str(data.get("full_name") or f"{owner}/{repo}"),
        )
        return GitHubResult(summary, stale=False)

    async def get_latest_release(self, owner: str, repo: str) -> GitHubResult[ReleaseData]:
        if await self.check_repo_stale(owner, repo):
            return GitHubResult(None, stale=True)
        r = await self._request("GET", f"/repos/{owner}/{repo}/releases/latest")
        if r.status_code == 404:
            return GitHubResult(None, stale=False)
        if r.status_code != 200:
            return GitHubResult(None, stale=False)
        data = r.json()
        tag = str(data.get("tag_name") or data.get("name") or "")
        body = str(data.get("body") or "")
        author = (data.get("author") or {}) if isinstance(data.get("author"), dict) else {}
        publisher = str(author.get("login") or "")
        published = str(data.get("published_at") or "")
        html_url = str(data.get("html_url") or f"https://github.com/{owner}/{repo}/releases")
        rel = ReleaseData(
            version=tag,
            publisher=publisher,
            published_at_iso=published,
            notes_markdown=body,
            notes_html=_md_to_html(body),
            github_url=html_url,
        )
        return GitHubResult(rel, stale=False)

    async def get_latest_tag(self, owner: str, repo: str) -> GitHubResult[TagData]:
        if await self.check_repo_stale(owner, repo):
            return GitHubResult(None, stale=True)
        r = await self._request("GET", f"/repos/{owner}/{repo}/tags", params={"per_page": 1})
        if r.status_code != 200:
            return GitHubResult(None, stale=False)
        arr = r.json()
        if not arr or not isinstance(arr, list):
            return GitHubResult(None, stale=False)
        first = arr[0]
        name = str(first.get("name") or "")
        commit_obj = first.get("commit") if isinstance(first.get("commit"), dict) else {}
        sha = str(commit_obj.get("sha") or "")
        date_iso = ""
        if sha:
            cr = await self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}")
            if cr.status_code == 200:
                cj = cr.json()
                commit = cj.get("commit") if isinstance(cj.get("commit"), dict) else {}
                com = commit.get("committer")
                committer = com if isinstance(com, dict) else {}
                date_iso = str(committer.get("date") or "")
        url = f"https://github.com/{owner}/{repo}/releases/tag/{name}" if name else ""
        if not name:
            return GitHubResult(None, stale=False)
        return GitHubResult(TagData(name=name, date_iso=date_iso, github_url=url), stale=False)

    async def get_latest_commit(self, owner: str, repo: str) -> GitHubResult[CommitData]:
        summary = await self.get_repo_summary(owner, repo)
        if summary.stale or summary.data is None:
            return GitHubResult(None, stale=summary.stale)
        branch = summary.data.default_branch
        r = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits",
            params={"sha": branch, "per_page": 1},
        )
        if r.status_code != 200:
            return GitHubResult(None, stale=False)
        arr = r.json()
        if not arr or not isinstance(arr, list):
            return GitHubResult(None, stale=False)
        c = arr[0]
        sha = str(c.get("sha") or "")
        html_url = str(c.get("html_url") or "")
        commit = c.get("commit") if isinstance(c.get("commit"), dict) else {}
        committer = commit.get("committer") if isinstance(commit.get("committer"), dict) else {}
        author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
        date_iso = str(committer.get("date") or author.get("date") or "")
        an = author.get("name") if isinstance(author.get("name"), str) else ""
        return GitHubResult(
            CommitData(
                sha_short=_truncate_sha(sha),
                date_iso=date_iso,
                author=str(an or ""),
                github_url=html_url,
            ),
            stale=False,
        )

    async def get_contributors(
        self,
        owner: str,
        repo: str,
        *,
        limit: int = 50,
    ) -> GitHubResult[list[ContributorEntry]]:
        if await self.check_repo_stale(owner, repo):
            return GitHubResult(None, stale=True)
        r = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contributors",
            params={"per_page": limit},
        )
        if r.status_code != 200:
            return GitHubResult([], stale=False)
        arr = r.json()
        if not isinstance(arr, list):
            return GitHubResult([], stale=False)
        out: list[ContributorEntry] = []
        for row in arr[:limit]:
            if not isinstance(row, dict):
                continue
            login = str(row.get("login") or "")
            out.append(
                ContributorEntry(
                    login=login,
                    name=None,
                    avatar_url=str(row.get("avatar_url") or ""),
                    contributions=int(row.get("contributions") or 0),
                    html_url=str(row.get("html_url") or f"https://github.com/{login}"),
                ),
            )
        return GitHubResult(out, stale=False)

    async def get_owner_repos(self, owner: str) -> GitHubResult[list[OwnerRepoEntry]]:
        r_org = await self._request("GET", f"/orgs/{owner}/repos", params={"per_page": 100})
        if r_org.status_code == 200:
            return self._parse_repo_list(r_org.json())
        if r_org.status_code != 404:
            return GitHubResult([], stale=False)
        r_user = await self._request("GET", f"/users/{owner}/repos", params={"per_page": 100})
        if r_user.status_code != 200:
            return GitHubResult([], stale=False)
        return self._parse_repo_list(r_user.json())

    def _parse_repo_list(self, raw: Any) -> GitHubResult[list[OwnerRepoEntry]]:
        if not isinstance(raw, list):
            return GitHubResult([], stale=False)
        out: list[OwnerRepoEntry] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "")
            fn = str(row.get("full_name") or "")
            rd = row.get("description")
            desc = rd if isinstance(rd, str) else None
            pushed = row.get("pushed_at")
            pushed_iso = str(pushed) if isinstance(pushed, str) else ""
            out.append(
                OwnerRepoEntry(
                    name=name,
                    full_name=fn or name,
                    description=desc,
                    html_url=str(row.get("html_url") or ""),
                    private=bool(row.get("private")),
                    fork=bool(row.get("fork")),
                    pushed_at_iso=pushed_iso,
                ),
            )
        return GitHubResult(out, stale=False)

    async def get_readme_html(self, owner: str, repo: str) -> GitHubResult[str]:
        if await self.check_repo_stale(owner, repo):
            return GitHubResult("", stale=True)
        r = await self._request("GET", f"/repos/{owner}/{repo}/readme")
        if r.status_code == 404:
            return GitHubResult("", stale=False)
        if r.status_code != 200:
            return GitHubResult("", stale=False)
        try:
            data = r.json()
        except Exception:
            return GitHubResult("", stale=False)
        if not isinstance(data, dict):
            return GitHubResult("", stale=False)
        enc = data.get("encoding")
        raw_b64 = data.get("content")
        if enc != "base64" or not isinstance(raw_b64, str):
            return GitHubResult("", stale=False)
        try:
            raw = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
        except Exception:
            return GitHubResult("", stale=False)
        return GitHubResult(_md_to_html(raw), stale=False)

    async def get_org_members(self, owner: str) -> GitHubResult[list[OrgMemberEntry]]:
        r = await self._request("GET", f"/orgs/{owner}/public_members", params={"per_page": 100})
        if r.status_code == 404:
            return GitHubResult([], stale=False)
        if r.status_code != 200:
            return GitHubResult([], stale=False)
        arr = r.json()
        if not isinstance(arr, list):
            return GitHubResult([], stale=False)
        out: list[OrgMemberEntry] = []
        for row in arr:
            if not isinstance(row, dict):
                continue
            login = str(row.get("login") or "")
            out.append(
                OrgMemberEntry(
                    login=login,
                    avatar_url=str(row.get("avatar_url") or ""),
                    html_url=str(row.get("html_url") or f"https://github.com/{login}"),
                ),
            )
        return GitHubResult(out, stale=False)

    async def get_org_teams(self, owner: str) -> GitHubResult[list[OrgTeamEntry]]:
        r = await self._request("GET", f"/orgs/{owner}/teams", params={"per_page": 30})
        if r.status_code in (403, 404):
            return GitHubResult([], stale=False)
        if r.status_code != 200:
            return GitHubResult([], stale=False)
        arr = r.json()
        if not isinstance(arr, list):
            return GitHubResult([], stale=False)
        out: list[OrgTeamEntry] = []
        for row in arr:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "")
            slug = str(row.get("slug") or "")
            desc = row.get("description")
            description = str(desc) if isinstance(desc, str) else ""
            out.append(
                OrgTeamEntry(
                    name=name,
                    slug=slug,
                    description=description,
                    html_url=str(
                        row.get("html_url") or f"https://github.com/orgs/{owner}/teams/{slug}"
                    ),
                ),
            )
        return GitHubResult(out, stale=False)


__all__ = [
    "CommitData",
    "ContributorEntry",
    "GitHubResult",
    "GitHubService",
    "OrgMemberEntry",
    "OrgTeamEntry",
    "OwnerRepoEntry",
    "ReleaseData",
    "RepoSummary",
    "TagData",
]
