"""REST API v1 and NIP-05 well-known routes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cachetools import TTLCache
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from gitlurker.models.schemas import CommitData, ProjectData
from gitlurker.services.github import GitHubService
from gitlurker.services.nostr import NostrService

if TYPE_CHECKING:
    from gitlurker.config import Settings

_SLUG = re.compile(r"^[A-Za-z0-9_.-]+$")


def _dev_api_fixtures_path() -> Path:
    return Path(__file__).resolve().parents[3] / "fixtures" / "dev_api_samples.json"


def _load_dev_api_fixtures() -> dict[str, Any]:
    p = _dev_api_fixtures_path()
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _dev_owner_response(fixtures: dict[str, Any], owner: str) -> dict[str, Any]:
    owners = fixtures.get("owners") or {}
    base = owners.get(owner.lower())
    if base is not None:
        out = dict(base)
        out.setdefault("repos", [])
        out.setdefault("members", [])
        out.setdefault("teams", [])
        out.setdefault("github_url", f"https://github.com/{owner}")
        return out
    return {
        "repos": [],
        "members": [],
        "teams": [],
        "github_url": f"https://github.com/{owner}",
    }


def _dev_repo_response(fixtures: dict[str, Any], owner: str, repo: str) -> dict[str, Any] | None:
    repos = fixtures.get("repos") or {}
    return repos.get(f"{owner}/{repo}".lower())


def _dev_release_response(fixtures: dict[str, Any], owner: str, repo: str) -> dict[str, Any] | None:
    rel = fixtures.get("releases") or {}
    return rel.get(f"{owner}/{repo}".lower())


def _require_slug(label: str, value: str) -> None:
    if not _SLUG.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label} (allowed: letters, digits, _, ., -)",
        )


def _cors_nip05(response: JSONResponse) -> JSONResponse:
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


well_known = APIRouter(tags=["well-known"])


@well_known.get("/.well-known/nostr.json")
async def nip05_verify(name: str, request: Request) -> JSONResponse:
    if name != "_":
        raise HTTPException(status_code=404, detail="Unknown name")
    pk = getattr(request.app.state, "lurker_pubkey_hex", None)
    if not pk:
        raise HTTPException(status_code=404, detail="Nostr identity not configured")
    return _cors_nip05(
        JSONResponse(content={"names": {"_": pk}}),
    )


def build_api_v1_router(settings: Settings, limiter: Limiter) -> APIRouter:
    """GitHub-backed JSON API with per-IP rate limits and optional TTL cache."""
    api_v1 = APIRouter(prefix="/api/v1", tags=["api"])
    dev_fixtures: dict[str, Any] = (
        _load_dev_api_fixtures() if settings.gitlurker_dev_dummy_api else {}
    )
    lim = f"{settings.api_github_rate_limit_per_minute}/minute"
    ttl = settings.api_github_cache_ttl_seconds
    owner_cache: TTLCache[str, dict[str, Any]] | None = (
        TTLCache(maxsize=128, ttl=ttl) if ttl > 0 else None
    )
    repo_cache: TTLCache[tuple[str, str], dict[str, Any]] | None = (
        TTLCache(maxsize=256, ttl=ttl) if ttl > 0 else None
    )
    release_cache: TTLCache[tuple[str, str], dict[str, Any]] | None = (
        TTLCache(maxsize=256, ttl=ttl) if ttl > 0 else None
    )

    @api_v1.get("/owner/{owner}")
    @limiter.limit(lim)
    async def owner_detail(owner: str, request: Request) -> dict[str, Any]:
        _require_slug("owner", owner)
        if settings.gitlurker_dev_dummy_api:
            return _dev_owner_response(dev_fixtures, owner)
        gh: GitHubService = request.app.state.github
        if not gh.is_configured():
            raise HTTPException(status_code=503, detail="GitHub token not configured")
        cache_key = owner.lower()
        if owner_cache is not None and cache_key in owner_cache:
            return owner_cache[cache_key]
        repos_r = await gh.get_owner_repos(owner)
        members_r = await gh.get_org_members(owner)
        teams_r = await gh.get_org_teams(owner)
        if repos_r.data is None:
            repos: list[dict[str, Any]] = []
        else:
            repos = [r.model_dump(mode="json") for r in repos_r.data]
        if members_r.data is None:
            members = []
        else:
            members = [m.model_dump(mode="json") for m in members_r.data]
        if teams_r.data is None:
            teams: list[dict[str, Any]] = []
        else:
            teams = [t.model_dump(mode="json") for t in teams_r.data]
        payload = {
            "repos": repos,
            "members": members,
            "teams": teams,
            "github_url": f"https://github.com/{owner}",
        }
        if owner_cache is not None:
            owner_cache[cache_key] = payload
        return payload

    @api_v1.get("/repo/{owner}/{repo}")
    @limiter.limit(lim)
    async def repo_detail(owner: str, repo: str, request: Request) -> dict[str, Any]:
        _require_slug("owner", owner)
        _require_slug("repo", repo)
        if settings.gitlurker_dev_dummy_api:
            payload = _dev_repo_response(dev_fixtures, owner, repo)
            if payload is None:
                raise HTTPException(status_code=404, detail="Repository not in dev fixtures")
            return dict(payload)
        gh: GitHubService = request.app.state.github
        if not gh.is_configured():
            raise HTTPException(status_code=503, detail="GitHub token not configured")
        ck = (owner.lower(), repo.lower())
        if repo_cache is not None and ck in repo_cache:
            return repo_cache[ck]
        summary_r = await gh.get_repo_summary(owner, repo)
        if summary_r.stale:
            raise HTTPException(status_code=404, detail="Repository not found or moved")
        if summary_r.data is None:
            raise HTTPException(status_code=502, detail="GitHub API error")
        s = summary_r.data
        contrib_r = await gh.get_contributors(owner, repo)
        contributors: list[dict[str, Any]]
        if contrib_r.data is None:
            contributors = []
        else:
            contributors = [c.model_dump(mode="json") for c in contrib_r.data]
        payload = {
            "description": s.description,
            "stars": s.stars,
            "forks": s.forks,
            "issues": s.open_issues,
            "contributors": contributors,
            "github_url": s.html_url or f"https://github.com/{owner}/{repo}",
        }
        if repo_cache is not None:
            repo_cache[ck] = payload
        return payload

    @api_v1.get("/release/{owner}/{repo}")
    @limiter.limit(lim)
    async def release_detail(owner: str, repo: str, request: Request) -> dict[str, Any]:
        _require_slug("owner", owner)
        _require_slug("repo", repo)
        if settings.gitlurker_dev_dummy_api:
            rel = _dev_release_response(dev_fixtures, owner, repo)
            if rel is None:
                raise HTTPException(status_code=404, detail="Release not in dev fixtures")
            return dict(rel)
        gh: GitHubService = request.app.state.github
        nostr: NostrService = request.app.state.nostr
        if not gh.is_configured():
            raise HTTPException(status_code=503, detail="GitHub token not configured")
        ck = (owner.lower(), repo.lower())
        if release_cache is not None and ck in release_cache:
            return release_cache[ck]
        summary = await gh.get_repo_summary(owner, repo)
        if summary.stale or summary.data is None:
            if summary.stale:
                raise HTTPException(status_code=404, detail="Repository not found or moved")
            raise HTTPException(status_code=502, detail="GitHub API error")
        payload = await _release_payload(owner, repo, gh, nostr)
        if release_cache is not None:
            release_cache[ck] = payload
        return payload

    return api_v1


async def _commit_release_view(
    owner: str,
    repo: str,
    gh: GitHubService,
    cd: CommitData,
) -> dict[str, Any]:
    notes_html = ""
    readme_r = await gh.get_readme_html(owner, repo)
    if readme_r.stale:
        raise HTTPException(status_code=404, detail="Repository not found or moved")
    if readme_r.data:
        notes_html = readme_r.data
    return {
        "version": "Latest commit",
        "date": cd.date_iso,
        "publisher": cd.author,
        "notes_html": notes_html,
        "github_url": cd.github_url or f"https://github.com/{owner}/{repo}",
        "commit_sha_short": cd.sha_short,
    }


async def _release_payload(
    owner: str,
    repo: str,
    gh: GitHubService,
    nostr: NostrService,
) -> dict[str, Any]:
    snap: ProjectData | None = None
    if nostr.public_key is not None:
        snap = await nostr.fetch_project_data_snapshot(owner, repo)
    mode = snap.tracking_mode if snap else None

    if mode == "tag":
        t = await gh.get_latest_tag(owner, repo)
        if t.stale:
            raise HTTPException(status_code=404, detail="Repository not found or moved")
        if t.data is None:
            raise HTTPException(status_code=404, detail="No tags found")
        d = t.data
        return {
            "version": d.name,
            "date": d.date_iso,
            "publisher": "",
            "notes_html": "",
            "github_url": d.github_url or f"https://github.com/{owner}/{repo}",
        }

    if mode == "commit":
        c = await gh.get_latest_commit(owner, repo)
        if c.stale:
            raise HTTPException(status_code=404, detail="Repository not found or moved")
        if c.data is None:
            raise HTTPException(status_code=404, detail="No commits found")
        return await _commit_release_view(owner, repo, gh, c.data)

    rel = await gh.get_latest_release(owner, repo)
    if rel.stale:
        raise HTTPException(status_code=404, detail="Repository not found or moved")
    if rel.data is not None:
        d = rel.data
        return {
            "version": d.version,
            "date": d.published_at_iso,
            "publisher": d.publisher,
            "notes_html": d.notes_html,
            "github_url": d.github_url,
        }

    if mode is None:
        tag = await gh.get_latest_tag(owner, repo)
        if not tag.stale and tag.data is not None:
            d = tag.data
            return {
                "version": d.name,
                "date": d.date_iso,
                "publisher": "",
                "notes_html": "",
                "github_url": d.github_url or f"https://github.com/{owner}/{repo}",
            }
        com = await gh.get_latest_commit(owner, repo)
        if not com.stale and com.data is not None:
            return await _commit_release_view(owner, repo, gh, com.data)

    raise HTTPException(status_code=404, detail="No release found")


def build_limiter() -> Limiter:
    return Limiter(key_func=get_remote_address)


__all__ = ["build_api_v1_router", "build_limiter", "well_known"]
