"""Pydantic schemas for API, GitHub, and Nostr structures."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, cast

from pydantic import BaseModel, Field, field_validator

_OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

TrackingMode = Literal["release", "tag", "commit"]

CATEGORIES = frozenset({"bitcoin", "layer2", "ecash", "nostr", "ai", "other"})
SUBCATEGORIES = frozenset(
    {
        "client",
        "development",
        "exchange",
        "interface",
        "node",
        "wallet",
        "server",
        "payments",
        "protocol",
        "relay",
        "signer",
        "agent",
        "model",
        "mcp",
        "skills",
        "other",
    }
)


class ProjectData(BaseModel):
    """Structured project metadata published as Kind 30078 tags + JSON content."""

    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    name: str = ""
    description: str = ""
    category: str
    subcategory: str
    tracking_mode: TrackingMode
    web: str = ""
    clone: str = ""
    release_version: str | None = None
    release_date_iso: str | None = None
    tag_name: str | None = None
    tag_date_iso: str | None = None
    commit_sha: str | None = None
    commit_date_iso: str | None = None
    commit_author: str | None = None
    stars: int = Field(default=0, ge=0)
    forks: int = Field(default=0, ge=0)
    open_issues: int = Field(default=0, ge=0)
    stale: bool = False

    @field_validator("owner", "repo")
    @classmethod
    def validate_owner_repo(cls, v: str) -> str:
        s = v.strip()
        if not _OWNER_REPO_RE.match(s):
            msg = "owner/repo must match [A-Za-z0-9_.-]+"
            raise ValueError(msg)
        return s

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in CATEGORIES:
            msg = f"category must be one of {sorted(CATEGORIES)}"
            raise ValueError(msg)
        return s

    @field_validator("subcategory")
    @classmethod
    def validate_subcategory(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in SUBCATEGORIES:
            msg = f"subcategory must be one of {sorted(SUBCATEGORIES)}"
            raise ValueError(msg)
        return s


class DmAddCommand(BaseModel):
    """Validated `cmd: add` payload (schema v1)."""

    owner: str
    repo: str
    category: str
    subcategory: str
    mode: TrackingMode

    @field_validator("owner", "repo")
    @classmethod
    def validate_owner_repo_cmd(cls, v: str) -> str:
        s = v.strip()
        if not _OWNER_REPO_RE.match(s):
            msg = "owner/repo must match [A-Za-z0-9_.-]+"
            raise ValueError(msg)
        return s


class DmRemoveCommand(BaseModel):
    owner: str
    repo: str

    @field_validator("owner", "repo")
    @classmethod
    def validate_owner_repo_cmd(cls, v: str) -> str:
        s = v.strip()
        if not _OWNER_REPO_RE.match(s):
            msg = "owner/repo must match [A-Za-z0-9_.-]+"
            raise ValueError(msg)
        return s


class ReleaseAnnouncementInput(BaseModel):
    """Inputs for a Kind 1 release announcement note."""

    owner: str
    repo: str
    version_label: str
    published_at_iso: str
    publisher: str = ""
    github_url: str = ""


@dataclass(frozen=True)
class GitHubResult[T]:
    """GitHub REST fetch outcome with optional stale repo flag."""

    data: T | None
    stale: bool = False


class RepoSummary(BaseModel):
    description: str | None = None
    stars: int = Field(ge=0, default=0)
    forks: int = Field(ge=0, default=0)
    open_issues: int = Field(ge=0, default=0)
    html_url: str = ""
    default_branch: str = "main"
    full_name: str = ""


class ReleaseData(BaseModel):
    version: str
    publisher: str
    published_at_iso: str
    notes_markdown: str
    notes_html: str
    github_url: str


class TagData(BaseModel):
    name: str
    date_iso: str
    github_url: str


class CommitData(BaseModel):
    sha_short: str
    date_iso: str
    author: str
    github_url: str


class ContributorEntry(BaseModel):
    login: str
    name: str | None = None
    avatar_url: str = ""
    contributions: int = Field(ge=0, default=0)
    html_url: str = ""


class OwnerRepoEntry(BaseModel):
    name: str
    full_name: str
    description: str | None = None
    html_url: str = ""
    private: bool = False
    fork: bool = False
    pushed_at_iso: str = ""


class OrgTeamEntry(BaseModel):
    name: str
    slug: str
    description: str = ""
    html_url: str = ""


class OrgMemberEntry(BaseModel):
    login: str
    avatar_url: str = ""
    html_url: str = ""


def parse_dm_command_v1(line: str) -> DmAddCommand | DmRemoveCommand | None:
    """Parse minified JSON DM body. Returns None if invalid."""
    raw = line.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("v") != 1:
        return None
    cmd = obj.get("cmd")
    if cmd not in ("add", "remove"):
        return None
    owner = obj.get("owner")
    repo = obj.get("repo")
    if not isinstance(owner, str) or not isinstance(repo, str):
        return None
    if cmd == "remove":
        try:
            return DmRemoveCommand(owner=owner, repo=repo)
        except ValueError:
            return None
    category = obj.get("category")
    subcategory = obj.get("subcategory")
    mode = obj.get("mode")
    if (
        not isinstance(category, str)
        or not isinstance(subcategory, str)
        or not isinstance(mode, str)
    ):
        return None
    if category.strip().lower() not in CATEGORIES:
        return None
    if subcategory.strip().lower() not in SUBCATEGORIES:
        return None
    if mode not in ("release", "tag", "commit"):
        return None
    try:
        return DmAddCommand(
            owner=owner,
            repo=repo,
            category=category,
            subcategory=subcategory,
            mode=cast(TrackingMode, mode),
        )
    except ValueError:
        return None
