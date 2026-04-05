"""Normalize GitHub URLs to (owner, repo) for seeding and tooling."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_GH_HOST = re.compile(r"^github\.com$", re.I)


def parse_github_url(url: str) -> tuple[str, str] | None:
    """Return ``(owner, repo)`` or ``None`` if the string is not a github.com repo URL.

    Uses the first two path segments as owner and repo (so ``…/owner/repo/tree/…`` still works).
    Query strings and fragments are ignored.
    """
    raw = url.strip()
    if not raw:
        return None
    if raw.startswith("git@github.com:"):
        path = raw.removeprefix("git@github.com:").split("?", 1)[0].split("#", 1)[0]
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1].removesuffix(".git")
        return None

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    if not host or not _GH_HOST.match(host):
        return None
    path = parsed.path.strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo.removesuffix(".git")
        return owner, repo
    return None
