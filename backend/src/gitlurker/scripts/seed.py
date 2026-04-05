"""Seed Kind 30078 (project) and Kind 10003 (bookmark list) from a Django-style fixture.

Canonical project list: ``backend/fixtures/seed_projects.json`` — a JSON array of
``{"model": "git_lurker.project", "pk": ..., "fields": {...}}`` objects (same shape as
``dumpdata``). Edit that file to add or change entries; there is no separate “extra” list.

**Default mode is dry-run:** the script does **not** open relay connections or call
``send_event``, even if ``NOSTR_PUBLISH_ENABLED`` is true. Use ``--publish`` to send.

**Typical commands** (from ``gitlurker/backend``)::

    uv run python -m gitlurker.scripts.seed
    uv run python -m gitlurker.scripts.seed --no-github
    uv run python -m gitlurker.scripts.seed --publish

**Flags**

* ``--json-path`` — fixture file (default: ``backend/fixtures/seed_projects.json``).
* ``--stale-output-path`` — where to write excluded stale rows (default:
  ``backend/fixtures/stale_seed.json``).
* ``--no-github`` — skip GitHub enrichment (no API token needed; stars stay at defaults).
* ``--include-stale`` — include repositories marked stale/missing in the publish set and
  in dry-run “would publish” counts. Without it, stale rows are omitted from publish.
* ``--publish`` — requires ``LURKER_KEY``, ``NOSTR_RELAYS`` (or public relay fallback per
  settings), and ``NOSTR_PUBLISH_ENABLED=true``.

**Stale output:** if any project is stale and would be **excluded** (you did **not** pass
``--include-stale``), the script writes ``stale_seed.json`` in the same dumpdata shape,
sorted by owner/repository, containing **only** those rows. Use it to review removals or
merge fixes back into ``seed_projects.json`` by hand. If nothing is excluded as stale,
that file is not written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import Counter
from pathlib import Path

from nostr_sdk import Coordinate

from gitlurker.config import get_settings, load_gitlurker_dotenv
from gitlurker.models.schemas import CATEGORIES, SUBCATEGORIES, ProjectData
from gitlurker.services.github import GitHubService
from gitlurker.services.nostr import KIND_PROJECT, NostrService, project_d_tag
from gitlurker.services.scheduler import enrich_project_from_github

logger = logging.getLogger(__name__)

_LEGACY_CATEGORY_MAP: dict[str, str] = {
    "bitcoin": "bitcoin",
    "lightning": "layer2",
    "e-cash": "ecash",
    "ecash": "ecash",
    "nostr": "nostr",
    "ai": "ai",
    "other": "other",
}

_CATEGORY_TO_DJANGO_FIXTURE: dict[str, str] = {
    "bitcoin": "bitcoin",
    "layer2": "lightning",
    "ecash": "e-cash",
    "nostr": "nostr",
    "ai": "ai",
    "other": "other",
}


def _impl_root() -> Path:
    """``gitlurker`` directory that contains ``backend/`` (implementation root)."""
    return Path(__file__).resolve().parents[4]


def _default_seed_fixture_path() -> Path:
    return _impl_root() / "backend" / "fixtures" / "seed_projects.json"


def _default_stale_output_path() -> Path:
    return _impl_root() / "backend" / "fixtures" / "stale_seed.json"


def _normalize_category(raw: str) -> str:
    key = raw.strip().lower()
    mapped = _LEGACY_CATEGORY_MAP.get(key, "other")
    return mapped if mapped in CATEGORIES else "other"


def _normalize_subcategory(raw: str) -> str:
    s = raw.strip().lower()
    return s if s in SUBCATEGORIES else "other"


def load_legacy_fixture(path: Path) -> list[ProjectData]:
    """Parse Django dumpdata JSON into ``ProjectData`` rows (release tracking)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        msg = "fixture must be a JSON array"
        raise ValueError(msg)
    out: list[ProjectData] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        fields = row.get("fields")
        if not isinstance(fields, dict):
            continue
        owner = str(fields.get("owner") or "").strip()
        repo = str(fields.get("repository") or "").strip()
        if not owner or not repo:
            continue
        out.append(
            ProjectData(
                owner=owner,
                repo=repo,
                name=repo,
                description="",
                category=_normalize_category(str(fields.get("category") or "")),
                subcategory=_normalize_subcategory(str(fields.get("subcategory") or "")),
                tracking_mode="release",
            ),
        )
    return out


def project_data_to_django_fixture_row(project: ProjectData, pk: int) -> dict[str, object]:
    """One ``git_lurker.project`` dumpdata row (for exporting stale subsets)."""
    django_cat = _CATEGORY_TO_DJANGO_FIXTURE.get(project.category, "other")
    return {
        "model": "git_lurker.project",
        "pk": pk,
        "fields": {
            "owner": project.owner,
            "repository": project.repo,
            "category": django_cat,
            "subcategory": project.subcategory,
        },
    }


def write_stale_seed_json(path: Path, projects: list[ProjectData]) -> None:
    """Write ``projects`` as a Django-style JSON array (sorted by owner/repo)."""
    sorted_p = sorted(projects, key=lambda p: (p.owner.lower(), p.repo.lower()))
    rows = [project_data_to_django_fixture_row(p, i + 1) for i, p in enumerate(sorted_p)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Wrote %d stale-only fixture row(s) to %s", len(rows), path)


def merge_project_lists(primary: list[ProjectData], extra: list[ProjectData]) -> list[ProjectData]:
    """Append ``extra`` rows, skipping duplicates (case-insensitive owner/repo)."""
    seen: set[tuple[str, str]] = {(p.owner.lower(), p.repo.lower()) for p in primary}
    out = list(primary)
    for p in extra:
        key = (p.owner.lower(), p.repo.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def category_counts(projects: list[ProjectData]) -> dict[str, int]:
    return dict(Counter(p.category for p in projects))


def _excluded_stale_projects(
    projects: list[ProjectData],
    *,
    include_stale: bool,
) -> list[ProjectData]:
    if include_stale:
        return []
    return sorted(
        (p for p in projects if p.stale),
        key=lambda p: (p.owner.lower(), p.repo.lower()),
    )


async def _enrich_all(github: GitHubService, projects: list[ProjectData]) -> list[ProjectData]:
    enriched: list[ProjectData] = []
    for p in projects:
        updated, _ok = await enrich_project_from_github(github, p)
        enriched.append(updated)
    return enriched


def _coordinates_for_projects(nostr: NostrService, projects: list[ProjectData]) -> list[Coordinate]:
    pk = nostr.public_key
    if pk is None:
        return []
    return [Coordinate(KIND_PROJECT, pk, project_d_tag(p.owner, p.repo)) for p in projects]


async def _run(args: argparse.Namespace) -> int:
    load_gitlurker_dotenv()
    settings = get_settings()
    fixture = Path(args.json_path).expanduser().resolve()
    if not fixture.is_file():
        logger.error("Fixture not found: %s", fixture)
        return 2

    projects = load_legacy_fixture(fixture)
    if not projects:
        logger.error("No projects loaded from %s", fixture)
        return 2

    use_github = not args.no_github
    if use_github and not settings.github_token.strip():
        logger.error("GitHub token missing (set AUTH_TOKEN or GITHUB_TOKEN), or pass --no-github")
        return 2

    if use_github:
        gh = GitHubService(settings.github_token)
        try:
            projects = await _enrich_all(gh, projects)
        finally:
            await gh.aclose()

    dry_run = not args.publish
    counts = category_counts(projects)
    logger.info("Category counts: %s", counts)

    if dry_run:
        logger.warning(
            "Dry-run: not connecting to relays or sending events "
            "(use --publish when you intend to send to relays)",
        )

    stale_excluded = _excluded_stale_projects(projects, include_stale=args.include_stale)
    stale_out = Path(args.stale_output_path).expanduser().resolve()
    if stale_excluded:
        write_stale_seed_json(stale_out, stale_excluded)

    if dry_run:
        stale_n = sum(1 for p in projects if p.stale)
        publish_n = len(projects) if args.include_stale else sum(1 for p in projects if not p.stale)
        logger.info(
            "Would publish %d Kind 30078 replaceable events + Kind 10003 (%d stale total; "
            "%d would publish without --include-stale)",
            len(projects),
            stale_n,
            publish_n,
        )
        for p in projects[:5]:
            logger.info(
                "  %s/%s  category=%s sub=%s stars=%s stale=%s",
                p.owner,
                p.repo,
                p.category,
                p.subcategory,
                p.stars,
                p.stale,
            )
        if len(projects) > 5:
            logger.info("  ... and %d more", len(projects) - 5)
        if stale_excluded:
            logger.info("Stale projects excluded without --include-stale (see %s):", stale_out)
            for p in stale_excluded:
                logger.info(
                    "  stale: %s/%s  category=%s",
                    p.owner,
                    p.repo,
                    p.category,
                )
        return 0

    # --publish
    if not settings.lurker_secret_hex.strip():
        logger.error("LURKER_KEY is required for --publish")
        return 2
    if not settings.nostr_relays:
        logger.error("No NOSTR_RELAYS configured (or enable NOSTR_USE_PUBLIC_RELAYS)")
        return 2
    if not settings.nostr_publish_enabled:
        logger.error("NOSTR_PUBLISH_ENABLED must be true to send events with --publish")
        return 2

    to_publish = list(projects)
    if not args.include_stale:
        fresh = [p for p in to_publish if not p.stale]
        skipped = len(to_publish) - len(fresh)
        if skipped:
            logger.info(
                "Excluding %d stale projects from publish (pass --include-stale to publish them)",
                skipped,
            )
        to_publish = fresh

    if not to_publish:
        logger.error("Nothing to publish after filtering stale projects")
        return 2

    nostr = NostrService(settings)
    await nostr.start()
    try:
        coords = _coordinates_for_projects(nostr, to_publish)
        nostr.replace_tracked_coordinates(coords)
        for p in to_publish:
            await nostr.publish_project(p)
        await nostr.publish_project_list()
        logger.info(
            "Published %d Kind 30078 events and Kind 10003 (%d coordinates)",
            len(to_publish),
            len(coords),
        )
    finally:
        await nostr.stop()
    return 0


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description=(
            "Load seed_projects.json, optionally enrich from GitHub, "
            "dry-run or publish Kind 30078 + Kind 10003 (see module docstring)."
        ),
    )
    parser.add_argument(
        "--json-path",
        default=str(_default_seed_fixture_path()),
        help="Django dumpdata JSON array (default: backend/fixtures/seed_projects.json)",
    )
    parser.add_argument(
        "--stale-output-path",
        default=str(_default_stale_output_path()),
        help="Where to write excluded stale rows (default: backend/fixtures/stale_seed.json)",
    )
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Skip GitHub enrichment (fixture metadata only)",
    )
    parser.add_argument(
        "--include-stale",
        action="store_true",
        help="Include stale / missing repos when publishing (default: skip when publishing)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Connect to relays and publish (requires LURKER_KEY, relays, NOSTR_PUBLISH_ENABLED)",
    )
    ns = parser.parse_args(argv)
    raise SystemExit(asyncio.run(_run(ns)))


if __name__ == "__main__":
    main()
