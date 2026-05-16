"""Background refresh: GitHub → Kind 30078 / Kind 1 with scheduler rate budget (NFR-10)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from nostr_sdk import Coordinate

from gitlurker.models.schemas import CommitData, ProjectData, ReleaseAnnouncementInput
from gitlurker.services.github import GitHubService

if TYPE_CHECKING:
    from gitlurker.config import Settings
    from gitlurker.services.nostr import NostrService

logger = logging.getLogger(__name__)

# Conservative GitHub REST calls per tracked repo per sweep (stale checks + summary + mode).
_ESTIMATED_REQUESTS_PER_PROJECT = 8
# Skip a sweep only when GitHub's remaining quota is critically low (not per full fleet size).
_CRITICAL_GITHUB_RATE_REMAINING = 20


def _fields_from_latest_commit(c: CommitData) -> dict[str, Any]:
    """Clear release/tag fields; set commit tags (default-branch head)."""
    full_sha = ""
    if c.github_url and "/commit/" in c.github_url:
        full_sha = c.github_url.rsplit("/commit/", 1)[-1].split("?")[0]
    sha_store = full_sha if len(full_sha) >= 7 else c.sha_short
    return {
        "release_version": None,
        "release_date_iso": None,
        "tag_name": None,
        "tag_date_iso": None,
        "commit_sha": sha_store,
        "commit_date_iso": c.date_iso,
        "commit_author": c.author or None,
    }


async def enrich_project_from_github(
    github: GitHubService,
    base: ProjectData,
) -> tuple[ProjectData, bool]:
    """Merge ``base`` with live GitHub data for ``base.tracking_mode``.

    Returns ``(updated, summary_ok)``. When ``summary_ok`` is False (missing or stale
    repo summary), callers should publish ``updated`` and skip release announcements.
    """
    owner, repo = base.owner, base.repo
    summary_r = await github.get_repo_summary(owner, repo)
    if summary_r.stale or summary_r.data is None:
        updated = base.model_copy(
            update={
                "stale": True,
                "description": base.description or "Repository unavailable or moved.",
            },
        )
        return updated, False

    s = summary_r.data
    updated = base.model_copy(
        update={
            "name": base.name or repo,
            "description": s.description or "",
            "stars": s.stars,
            "forks": s.forks,
            "open_issues": s.open_issues,
            "web": s.html_url or base.web,
            "clone": base.clone or f"https://github.com/{owner}/{repo}.git",
            "stale": False,
        },
    )

    mode = updated.tracking_mode

    if mode == "release":
        rel_r = await github.get_latest_release(owner, repo)
        if rel_r.stale:
            updated = updated.model_copy(
                update={"stale": True},
            )
        elif rel_r.data is not None:
            d = rel_r.data
            updated = updated.model_copy(
                update={
                    "release_version": d.version,
                    "release_date_iso": d.published_at_iso,
                    "tag_name": None,
                    "tag_date_iso": None,
                    "commit_sha": None,
                    "commit_date_iso": None,
                    "commit_author": None,
                },
            )
        else:
            com_r = await github.get_latest_commit(owner, repo)
            if com_r.stale:
                updated = updated.model_copy(update={"stale": True})
            elif com_r.data is not None:
                updated = updated.model_copy(update=_fields_from_latest_commit(com_r.data))
    elif mode == "tag":
        tag_r = await github.get_latest_tag(owner, repo)
        if tag_r.stale:
            updated = updated.model_copy(update={"stale": True})
        elif tag_r.data is not None:
            t = tag_r.data
            updated = updated.model_copy(
                update={
                    "release_version": None,
                    "release_date_iso": None,
                    "tag_name": t.name,
                    "tag_date_iso": t.date_iso,
                    "commit_sha": None,
                    "commit_date_iso": None,
                    "commit_author": None,
                },
            )
        else:
            com_r = await github.get_latest_commit(owner, repo)
            if com_r.stale:
                updated = updated.model_copy(update={"stale": True})
            elif com_r.data is not None:
                updated = updated.model_copy(update=_fields_from_latest_commit(com_r.data))
    else:
        com_r = await github.get_latest_commit(owner, repo)
        if com_r.stale:
            updated = updated.model_copy(update={"stale": True})
        elif com_r.data is not None:
            updated = updated.model_copy(update=_fields_from_latest_commit(com_r.data))

    return updated, True


def owner_repo_from_coordinate(coord: Coordinate) -> tuple[str, str] | None:
    ident = coord.identifier().strip()
    if "/" not in ident:
        return None
    owner, _, repo = ident.partition("/")
    owner, repo = owner.strip(), repo.strip()
    if not owner or not repo:
        return None
    return owner, repo


class SchedulerBudget:
    """Rolling hourly cap on scheduler GitHub requests (separate from token global limit)."""

    def __init__(self, limit_per_hour: int) -> None:
        self._limit = limit_per_hour
        self._window_start = time.monotonic()
        self._used = 0

    def _rollover(self) -> None:
        if time.monotonic() - self._window_start >= 3600.0:
            self._window_start = time.monotonic()
            self._used = 0

    def record_request(self) -> None:
        self._rollover()
        self._used += 1

    def remaining(self) -> int:
        self._rollover()
        return max(0, self._limit - self._used)


class RefreshScheduler:
    def __init__(
        self,
        settings: Settings,
        github: GitHubService,
        nostr: NostrService,
        budget: SchedulerBudget,
    ) -> None:
        self._settings = settings
        self._github = github
        self._nostr = nostr
        self._budget = budget
        self._sem = asyncio.Semaphore(settings.github_max_concurrent_requests)

    def _should_skip_sweep(self) -> bool:
        """Avoid hammering GitHub when the hourly token budget is exhausted.

        Per-repo refreshes also defer when :attr:`SchedulerBudget` is empty. We no longer
        skip the whole sweep just because ``N * estimated_calls`` exceeds the hourly cap:
        that prevented *any* updates for large Kind 10003 lists.
        """
        rem = self._github.last_rate_limit_remaining
        if rem is not None and rem < _CRITICAL_GITHUB_RATE_REMAINING:
            logger.warning(
                "Scheduler skipping sweep: X-RateLimit-Remaining critically low (%s)",
                rem,
            )
            return True
        return False

    async def run_forever(self) -> None:
        try:
            await self.run_sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Initial refresh sweep failed")
        while True:
            await asyncio.sleep(self._settings.refresh_interval_seconds)
            try:
                await self.run_sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Refresh sweep failed")

    async def run_sweep_once(self) -> None:
        coords = self._nostr.tracked_coordinates()
        if not coords:
            logger.debug("No tracked projects; sweep idle")
            return
        if self._should_skip_sweep():
            return
        tasks = [self._refresh_wrapped(c) for c in coords]
        await asyncio.gather(*tasks)

    async def _refresh_wrapped(self, coord: Coordinate) -> None:
        async with self._sem:
            try:
                await self._refresh_one(coord)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Refresh failed for coordinate %s", coord.identifier())

    async def _refresh_one(self, coord: Coordinate) -> None:
        parsed = owner_repo_from_coordinate(coord)
        if parsed is None:
            return
        owner, repo = parsed
        if self._budget.remaining() < _ESTIMATED_REQUESTS_PER_PROJECT:
            logger.debug(
                "Scheduler hourly budget too low for a full refresh; deferring %s/%s",
                owner,
                repo,
            )
            return

        base = await self._nostr.fetch_project_data_snapshot(owner, repo)
        if base is None:
            base = ProjectData(
                owner=owner,
                repo=repo,
                name=repo,
                description="",
                category="other",
                subcategory="other",
                tracking_mode="release",
            )

        updated, summary_ok = await enrich_project_from_github(self._github, base)
        if not summary_ok:
            await self._nostr.publish_project(updated)
            return

        mode = updated.tracking_mode
        old_version_key = _version_key(base, mode)

        if updated != base:
            await self._nostr.publish_project(updated)

        new_key = _version_key(updated, mode)
        if new_key and new_key != old_version_key and not updated.stale:
            ann = _announcement_from_project(updated, mode)
            if ann is not None:
                await self._nostr.publish_release_announcement(ann)


def _version_key(p: ProjectData, mode: str) -> str:
    if mode == "release":
        v = (p.release_version or "").strip()
        return v if v else (p.commit_sha or "").strip()
    if mode == "tag":
        v = (p.tag_name or "").strip()
        return v if v else (p.commit_sha or "").strip()
    return (p.commit_sha or "").strip()


def _announcement_from_project(p: ProjectData, mode: str) -> ReleaseAnnouncementInput | None:
    if mode == "release" and p.release_version:
        ver = p.release_version
        return ReleaseAnnouncementInput(
            owner=p.owner,
            repo=p.repo,
            version_label=ver,
            published_at_iso=p.release_date_iso or "",
            publisher="",
            github_url=f"https://github.com/{p.owner}/{p.repo}/releases/tag/{ver}",
        )
    if mode == "tag" and p.tag_name:
        tag = p.tag_name
        return ReleaseAnnouncementInput(
            owner=p.owner,
            repo=p.repo,
            version_label=tag,
            published_at_iso=p.tag_date_iso or "",
            publisher="",
            github_url=f"https://github.com/{p.owner}/{p.repo}/releases/tag/{tag}",
        )
    if mode == "commit" and p.commit_sha:
        sha = p.commit_sha
        short = sha[:7] if len(sha) >= 7 else sha
        return ReleaseAnnouncementInput(
            owner=p.owner,
            repo=p.repo,
            version_label=short,
            published_at_iso=p.commit_date_iso or "",
            publisher=p.commit_author or "",
            github_url=f"https://github.com/{p.owner}/{p.repo}/commit/{sha}",
        )
    return None


__all__ = [
    "RefreshScheduler",
    "SchedulerBudget",
    "enrich_project_from_github",
    "owner_repo_from_coordinate",
]
