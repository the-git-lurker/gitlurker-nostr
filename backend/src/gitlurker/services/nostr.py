"""Nostr relay client, event builders, and DM command handling (Phase 2)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from nostr_sdk import (
    Bookmarks,
    Client,
    ClientBuilder,
    Coordinate,
    Event,
    EventBuilder,
    Filter,
    HandleNotification,
    Keys,
    Kind,
    KindStandard,
    NostrSigner,
    PublicKey,
    RelayUrl,
    Tag,
    TagKind,
    UnwrappedGift,
)

from gitlurker.models.schemas import (
    CATEGORIES,
    SUBCATEGORIES,
    DmAddCommand,
    DmRemoveCommand,
    ProjectData,
    ReleaseAnnouncementInput,
    TrackingMode,
    parse_dm_command_v1,
)

if TYPE_CHECKING:
    from gitlurker.config import Settings

logger = logging.getLogger(__name__)

KIND_PROJECT = Kind(30078)
KIND_GIFT_WRAP = Kind.from_std(KindStandard.GIFT_WRAP)


def project_d_tag(owner: str, repo: str) -> str:
    """`d` tag for Kind 30078 (stable per owner/repo)."""
    return f"{owner.strip()}/{repo.strip()}".lower()


def build_kind30078_builder(project: ProjectData) -> EventBuilder:
    """Unsigned Kind 30078 [`EventBuilder`] with required metadata tags."""
    d = project_d_tag(project.owner, project.repo)
    tags: list[Tag] = [
        Tag.identifier(d),
        Tag.custom(TagKind.NAME(), [project.name or project.repo]),
        Tag.description(project.description or ""),
        _tag_unknown("owner", project.owner),
        _tag_unknown("category", project.category),
        Tag.hashtag(project.subcategory),
        _tag_unknown("stars", str(project.stars)),
        _tag_unknown("forks", str(project.forks)),
        _tag_unknown("open_issues", str(project.open_issues)),
    ]
    web = project.web or f"https://github.com/{project.owner}/{project.repo}"
    clone = project.clone or f"https://github.com/{project.owner}/{project.repo}.git"
    tags.append(_tag_unknown("web", web))
    tags.append(_tag_unknown("clone", clone))
    if project.release_version:
        tags.append(_tag_unknown("release", project.release_version))
        if project.release_date_iso:
            tags.append(_tag_unknown("release_date", project.release_date_iso))
    if project.tag_name:
        tags.append(_tag_unknown("tag", project.tag_name))
        if project.tag_date_iso:
            tags.append(_tag_unknown("tag_date", project.tag_date_iso))
    if project.commit_sha:
        tags.append(_tag_unknown("commit", project.commit_sha))
        if project.commit_date_iso:
            tags.append(_tag_unknown("commit_date", project.commit_date_iso))
        if project.commit_author:
            tags.append(_tag_unknown("commit_author", project.commit_author))
    tags.append(_tag_unknown("mode", project.tracking_mode))
    if project.stale:
        tags.append(_tag_unknown("stale", "1"))
    content = json.dumps(
        {
            "owner": project.owner,
            "repo": project.repo,
            "name": project.name,
            "category": project.category,
            "subcategory": project.subcategory,
            "tracking_mode": project.tracking_mode,
        },
        separators=(",", ":"),
    )
    return EventBuilder(KIND_PROJECT, content).tags(tags)


def _tag_unknown(name: str, *values: str) -> Tag:
    return Tag.custom(TagKind.UNKNOWN(name), list(values))


def build_kind10003_builder(coordinates: list[Coordinate]) -> EventBuilder:
    """Unsigned Kind 10003 bookmark list with `a` tag coordinates."""
    return EventBuilder.bookmarks(Bookmarks(coordinate=list(coordinates)))


def kind10003_coordinate_count(coordinates: list[Coordinate]) -> int:
    """Number of Kind 30078 coordinates in a bookmark list (for diagnostics/tests)."""
    return len(coordinates)


def build_release_announcement_builder(data: ReleaseAnnouncementInput) -> EventBuilder:
    """Kind 1 text note announcing a release/tag/commit."""
    parts = [
        f"{data.owner}/{data.repo}",
        data.version_label,
        data.published_at_iso,
    ]
    if data.publisher:
        parts.append(data.publisher)
    body = " — ".join(parts)
    if data.github_url:
        body = f"{body}\n{data.github_url}"
    return EventBuilder.text_note(body)


def minimal_project_from_add(cmd: DmAddCommand) -> ProjectData:
    """Placeholder project row until GitHub enrichment (Phase 3)."""
    return ProjectData(
        owner=cmd.owner,
        repo=cmd.repo,
        name=cmd.repo,
        description="Pending GitHub sync.",
        category=cmd.category,
        subcategory=cmd.subcategory,
        tracking_mode=cmd.mode,
    )


def release_announcement_key(owner: str, repo: str, version_label: str) -> tuple[str, str, str]:
    return (owner.strip().lower(), repo.strip().lower(), version_label.strip())


def project_data_from_kind30078_event(event: Event) -> ProjectData | None:
    """Parse a Kind 30078 event (GitLurker tags) into `ProjectData`, if valid."""
    if event.kind().as_u16() != 30078:
        return None
    tags: dict[str, list[str]] = {}
    for raw in event.tags().to_vec():
        parts = raw.as_vec()
        if not parts:
            continue
        key = parts[0]
        tags.setdefault(key, []).extend(parts[1:])

    def one(key: str) -> str:
        xs = tags.get(key)
        return xs[0] if xs else ""

    owner = one("owner")
    repo = ""
    dvals = tags.get("d")
    if dvals:
        d0 = dvals[0]
        if "/" in d0:
            o, _, r = d0.partition("/")
            owner = owner or o.strip()
            repo = r.strip()
    try:
        meta = json.loads(event.content())
    except json.JSONDecodeError:
        meta = {}
    if isinstance(meta, dict):
        owner = owner or str(meta.get("owner") or "").strip()
        repo = repo or str(meta.get("repo") or "").strip()
    if not owner or not repo:
        return None
    subtags = tags.get("t")
    subcategory = subtags[0].lower() if subtags else "other"
    if subcategory not in SUBCATEGORIES:
        subcategory = "other"
    category = one("category").lower() or "other"
    if category not in CATEGORIES:
        category = "other"
    mode_s = one("mode").lower() or "release"
    if mode_s not in ("release", "tag", "commit"):
        mode_s = "release"
    mode: TrackingMode = mode_s  # type: ignore[assignment]
    name = one("name") or repo
    description = ""
    desc_vals = tags.get("description")
    if desc_vals:
        description = desc_vals[0]
    web = one("web") or f"https://github.com/{owner}/{repo}"
    clone = one("clone") or f"https://github.com/{owner}/{repo}.git"
    stars = int(one("stars") or "0")
    forks = int(one("forks") or "0")
    open_issues = int(one("open_issues") or "0")
    release_version = one("release") or None
    release_date_iso = None
    rd = tags.get("release_date")
    if rd:
        release_date_iso = rd[0]
    tag_name = one("tag") or None
    tag_date_iso = None
    tgd = tags.get("tag_date")
    if tgd:
        tag_date_iso = tgd[0]
    commit_sha = one("commit") or None
    commit_date_iso = None
    cdd = tags.get("commit_date")
    if cdd:
        commit_date_iso = cdd[0]
    commit_author = one("commit_author") or None
    stale = bool(tags.get("stale") and tags["stale"][0] in ("1", "true", "yes"))
    try:
        return ProjectData(
            owner=owner,
            repo=repo,
            name=name,
            description=description,
            category=category,
            subcategory=subcategory,
            tracking_mode=mode,
            web=web,
            clone=clone,
            release_version=release_version,
            release_date_iso=release_date_iso,
            tag_name=tag_name,
            tag_date_iso=tag_date_iso,
            commit_sha=commit_sha,
            commit_date_iso=commit_date_iso,
            commit_author=commit_author,
            stars=stars,
            forks=forks,
            open_issues=open_issues,
            stale=stale,
        )
    except ValueError:
        return None


class NostrService:
    """Connects to relays, publishes GitLurker events, and listens for operator DMs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._keys: Keys | None = None
        self._signer: NostrSigner | None = None
        self._public_key: PublicKey | None = None
        self._client: Client | None = None
        self._tracked: list[Coordinate] = []
        self._announcements_sent: set[tuple[str, str, str]] = set()
        self._listener_task: asyncio.Task[None] | None = None

    @property
    def public_key(self) -> PublicKey | None:
        return self._public_key

    def replace_tracked_coordinates(self, coordinates: list[Coordinate]) -> None:
        """Replace in-memory Kind 10003 coordinates (bootstrap / tests)."""
        self._tracked = list(coordinates)

    def tracked_coordinates(self) -> list[Coordinate]:
        return list(self._tracked)

    async def fetch_project_data_snapshot(self, owner: str, repo: str) -> ProjectData | None:
        """Fetch the latest Kind 30078 for this repo from relays (best-effort)."""
        if self._client is None or self._public_key is None:
            return None
        d = project_d_tag(owner, repo)
        flt = Filter().kind(KIND_PROJECT).author(self._public_key).identifier(d)
        try:
            events = await self._client.fetch_events(flt, timedelta(seconds=8))
        except Exception:
            logger.debug("fetch_events failed for %s/%s", owner, repo, exc_info=True)
            return None
        ev = events.first()
        if ev is None:
            return None
        return project_data_from_kind30078_event(ev)

    def _coord_for(self, owner: str, repo: str) -> Coordinate:
        assert self._public_key is not None
        return Coordinate(KIND_PROJECT, self._public_key, project_d_tag(owner, repo))

    def _operator_hexes(self) -> set[str]:
        return {p.lower() for p in self._settings.operator_pubkeys}

    def _sender_allowed(self, sender: PublicKey) -> bool:
        allow = self._operator_hexes()
        if not allow:
            return False
        return sender.to_hex().lower() in allow

    async def start(self) -> None:
        """Build signer/client, connect relays, optionally start DM listener."""
        hex_key = self._settings.lurker_secret_hex.strip()
        if not hex_key:
            logger.warning("LURKER_KEY not set; Nostr client disabled")
            return
        self._keys = Keys.parse(hex_key)
        self._signer = NostrSigner.keys(self._keys)
        self._public_key = await self._signer.get_public_key()
        builder = ClientBuilder().signer(self._signer)
        self._client = builder.build()
        for url in self._settings.nostr_relays:
            try:
                await self._client.add_relay(RelayUrl.parse(url))
            except Exception:
                logger.exception("Failed to add relay %s", url)
        await self._client.connect()
        if self._settings.operator_pubkeys and self._public_key is not None:
            self._listener_task = asyncio.create_task(self._run_dm_listener())
        logger.info("Nostr client started (%d relays)", len(self._settings.nostr_relays))

    async def stop(self) -> None:
        """Stop DM listener and disconnect."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._client is not None:
            await self._client.shutdown()
            self._client = None
        self._signer = None
        self._keys = None
        self._public_key = None
        logger.info("Nostr client stopped")

    async def publish_project(self, project: ProjectData) -> Event | None:
        """Publish Kind 30078 for ``project`` (replaceable by coordinate)."""
        if self._signer is None:
            return None
        builder = build_kind30078_builder(project)
        event = await builder.sign(self._signer)
        if self._settings.nostr_publish_enabled and self._client is not None:
            await self._client.send_event(event)
        return event

    async def publish_project_list(self) -> Event | None:
        """Publish Kind 10003 listing tracked Kind 30078 coordinates."""
        if self._signer is None:
            return None
        n = len(self._tracked)
        approx_a = n * 96 if n else 0
        logger.info(
            "Kind 10003 bookmark list: %d coordinates (~%d bytes raw `a` tag payload, upper bound)",
            n,
            approx_a,
        )
        builder = build_kind10003_builder(self._tracked)
        event = await builder.sign(self._signer)
        if self._settings.nostr_publish_enabled and self._client is not None:
            await self._client.send_event(event)
        return event

    async def publish_release_announcement(self, data: ReleaseAnnouncementInput) -> Event | None:
        """Publish Kind 1 release note unless this version was already announced."""
        if self._signer is None:
            return None
        builder = build_release_announcement_builder(data)
        if not self._settings.nostr_publish_enabled:
            return await builder.sign(self._signer)
        key = release_announcement_key(data.owner, data.repo, data.version_label)
        if key in self._announcements_sent:
            return None
        event = await builder.sign(self._signer)
        if self._client is None:
            return event
        await self._client.send_event(event)
        self._announcements_sent.add(key)
        return event

    async def apply_dm_command(
        self,
        cmd: DmAddCommand | DmRemoveCommand,
        *,
        sender: PublicKey,
    ) -> None:
        """Execute add/remove against in-memory list and publish Kind 10003."""
        if not self._sender_allowed(sender):
            return
        if isinstance(cmd, DmRemoveCommand):
            target = self._coord_for(cmd.owner, cmd.repo)
            self._tracked = [c for c in self._tracked if c != target]
            await self.publish_project_list()
            return
        project = minimal_project_from_add(cmd)
        await self.publish_project(project)
        coord = self._coord_for(cmd.owner, cmd.repo)
        if coord not in self._tracked:
            self._tracked.append(coord)
        await self.publish_project_list()

    async def _handle_incoming_event(self, event: Event) -> None:
        if self._signer is None or self._public_key is None:
            return
        try:
            if event.kind().as_u16() == 1059:
                unwrapped = await UnwrappedGift.from_gift_wrap(self._signer, event)
                rumor = unwrapped.rumor()
                sender = unwrapped.sender()
                if not self._sender_allowed(sender):
                    return
                cmd = parse_dm_command_v1(rumor.content())
                if cmd is None:
                    return
                await self.apply_dm_command(cmd, sender=sender)
                return
            if event.kind().as_u16() == 4:
                peer = event.author()
                if not self._sender_allowed(peer):
                    return
                plain = await self._signer.nip04_decrypt(peer, event.content())
                cmd = parse_dm_command_v1(plain)
                if cmd is None:
                    return
                await self.apply_dm_command(cmd, sender=peer)
        except Exception:
            logger.debug("Ignoring DM/gift-wrap decode error", exc_info=True)

    async def _run_dm_listener(self) -> None:
        assert self._client is not None and self._public_key is not None
        try:
            flt = Filter().kind(KIND_GIFT_WRAP).pubkey(self._public_key)
            await self._client.subscribe(flt)
            await self._client.handle_notifications(_DmNotificationHandler(self))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("DM listener exited with error")


class _DmNotificationHandler(HandleNotification):
    def __init__(self, service: NostrService) -> None:
        self._svc = service

    async def handle_msg(self, _relay_url, _msg) -> None:  # noqa: ANN001
        return None

    async def handle(self, _relay_url, _subscription_id: str, event: Event) -> None:  # noqa: ANN001
        await self._svc._handle_incoming_event(event)  # noqa: SLF001


__all__ = [
    "KIND_GIFT_WRAP",
    "KIND_PROJECT",
    "NostrService",
    "build_kind10003_builder",
    "kind10003_coordinate_count",
    "build_kind30078_builder",
    "build_release_announcement_builder",
    "minimal_project_from_add",
    "project_d_tag",
    "project_data_from_kind30078_event",
    "release_announcement_key",
    "parse_dm_command_v1",
]
