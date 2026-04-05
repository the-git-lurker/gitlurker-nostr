"""Unit tests for Nostr event builders and `NostrService` behaviour."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from nostr_sdk import Coordinate, Keys, Kind, NostrSigner

from gitlurker.config import Settings
from gitlurker.models.schemas import (
    DmAddCommand,
    DmRemoveCommand,
    ProjectData,
    ReleaseAnnouncementInput,
    parse_dm_command_v1,
)
from gitlurker.services.nostr import (
    KIND_PROJECT,
    NostrService,
    build_kind10003_builder,
    build_kind30078_builder,
    build_release_announcement_builder,
    kind10003_coordinate_count,
    project_d_tag,
    project_data_from_kind30078_event,
    release_announcement_key,
)


@pytest.fixture
def isolate_nostr_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "LURKER_KEY",
        "GITLURKER_NSEC_HEX",
        "NOSTR_RELAYS",
        "RELAYS",
        "NOSTR_PUBLISH_ENABLED",
        "GITLURKER_OPERATOR_PUBKEYS",
    ):
        monkeypatch.delenv(k, raising=False)


def _tag_matrix(event) -> list[list[str]]:
    return [t.as_vec() for t in event.tags().to_vec()]


def test_parse_dm_add_remove() -> None:
    add_line = json.dumps(
        {
            "v": 1,
            "cmd": "add",
            "owner": "rust-nostr",
            "repo": "nostr",
            "category": "nostr",
            "subcategory": "protocol",
            "mode": "release",
        },
        separators=(",", ":"),
    )
    cmd = parse_dm_command_v1(add_line)
    assert isinstance(cmd, DmAddCommand)
    assert cmd.owner == "rust-nostr"
    assert cmd.mode == "release"

    rem = parse_dm_command_v1(
        json.dumps({"v": 1, "cmd": "remove", "owner": "rust-nostr", "repo": "nostr"}),
    )
    assert isinstance(rem, DmRemoveCommand)

    assert parse_dm_command_v1('{"v":2,"cmd":"add"}') is None
    assert parse_dm_command_v1("not-json") is None
    assert (
        parse_dm_command_v1(
            json.dumps(
                {
                    "v": 1,
                    "cmd": "add",
                    "owner": "bad owner",
                    "repo": "x",
                    "category": "nostr",
                    "subcategory": "protocol",
                    "mode": "release",
                },
            ),
        )
        is None
    )


@pytest.mark.asyncio
async def test_kind30078_builder_tags() -> None:
    p = ProjectData(
        owner="rust-nostr",
        repo="nostr",
        name="nostr",
        description="desc",
        category="nostr",
        subcategory="protocol",
        tracking_mode="release",
        release_version="v1.0.0",
        release_date_iso="2024-01-02",
        stars=10,
        forks=3,
        open_issues=1,
        stale=True,
    )
    keys = Keys.generate()
    signer = NostrSigner.keys(keys)
    b = build_kind30078_builder(p)
    event = await b.sign(signer)
    assert event.kind().as_u16() == 30078
    matrix = _tag_matrix(event)
    kinds = {t[0]: t[1:] for t in matrix}
    assert kinds["d"] == [project_d_tag("rust-nostr", "nostr")]
    assert kinds["name"] == ["nostr"]
    assert kinds["owner"] == ["rust-nostr"]
    assert kinds["category"] == ["nostr"]
    assert kinds["t"] == ["protocol"]
    assert kinds["release"] == ["v1.0.0"]
    assert kinds["stars"] == ["10"]
    assert kinds["stale"] == ["1"]


@pytest.mark.asyncio
async def test_kind10003_builder() -> None:
    keys = Keys.generate()
    pk = keys.public_key()
    c = Coordinate(KIND_PROJECT, pk, "a/b")
    signer = NostrSigner.keys(keys)
    ev = await build_kind10003_builder([c]).sign(signer)
    assert ev.kind().as_u16() == 10003


@pytest.mark.asyncio
async def test_kind10003_builder_many_coordinates() -> None:
    keys = Keys.generate()
    pk = keys.public_key()
    coords = [Coordinate(KIND_PROJECT, pk, f"owner{n}/repo{n}") for n in range(130)]
    assert kind10003_coordinate_count(coords) == 130
    signer = NostrSigner.keys(keys)
    ev = await build_kind10003_builder(coords).sign(signer)
    assert ev.kind().as_u16() == 10003


@pytest.mark.asyncio
async def test_release_announcement_builder_kind() -> None:
    keys = Keys.generate()
    signer = NostrSigner.keys(keys)
    data = ReleaseAnnouncementInput(
        owner="o",
        repo="r",
        version_label="v1",
        published_at_iso="2024-01-01",
        publisher="alice",
        github_url="https://github.com/o/r/releases/v1",
    )
    ev = await build_release_announcement_builder(data).sign(signer)
    assert ev.kind().as_u16() == 1
    assert "o/r" in ev.content()


@pytest.mark.asyncio
async def test_release_duplicate_suppressed_when_publish_enabled(
    monkeypatch: pytest.MonkeyPatch,
    isolate_nostr_env: None,
) -> None:
    lurker = Keys.generate()
    s = Settings(
        LURKER_KEY=lurker.secret_key().to_hex(),
        NOSTR_PUBLISH_ENABLED="false",
        NOSTR_RELAYS="",
        GITLURKER_OPERATOR_PUBKEYS="",
    )
    svc = NostrService(s)
    await svc.start()
    assert svc._client is not None
    svc._client.send_event = AsyncMock()
    data = ReleaseAnnouncementInput(
        owner="o",
        repo="r",
        version_label="v1",
        published_at_iso="2024-01-01",
    )
    monkeypatch.setattr(s, "nostr_publish_enabled", True)
    first = await svc.publish_release_announcement(data)
    second = await svc.publish_release_announcement(data)
    assert first is not None
    assert second is None
    await svc.stop()


@pytest.mark.asyncio
async def test_apply_dm_add_and_remove_tracked(isolate_nostr_env: None) -> None:
    lurker = Keys.generate()
    op = Keys.generate()
    s = Settings(
        LURKER_KEY=lurker.secret_key().to_hex(),
        NOSTR_PUBLISH_ENABLED="false",
        NOSTR_RELAYS="",
        GITLURKER_OPERATOR_PUBKEYS=op.public_key().to_hex(),
    )
    svc = NostrService(s)
    await svc.start()
    pk = svc.public_key
    assert pk is not None
    coord = Coordinate(Kind(30078), pk, project_d_tag("rust-nostr", "nostr"))
    svc.replace_tracked_coordinates([coord])
    assert len(svc.tracked_coordinates()) == 1

    await svc.apply_dm_command(
        DmRemoveCommand(owner="rust-nostr", repo="nostr"),
        sender=op.public_key(),
    )
    assert svc.tracked_coordinates() == []

    await svc.apply_dm_command(
        DmAddCommand(
            owner="rust-nostr",
            repo="nostr",
            category="nostr",
            subcategory="protocol",
            mode="release",
        ),
        sender=op.public_key(),
    )
    assert len(svc.tracked_coordinates()) == 1
    await svc.stop()


@pytest.mark.asyncio
async def test_apply_dm_ignored_for_non_operator(isolate_nostr_env: None) -> None:
    lurker = Keys.generate()
    op = Keys.generate()
    stranger = Keys.generate()
    s = Settings(
        LURKER_KEY=lurker.secret_key().to_hex(),
        NOSTR_PUBLISH_ENABLED="false",
        NOSTR_RELAYS="",
        GITLURKER_OPERATOR_PUBKEYS=op.public_key().to_hex(),
    )
    svc = NostrService(s)
    await svc.start()
    await svc.apply_dm_command(
        DmAddCommand(
            owner="x",
            repo="y",
            category="nostr",
            subcategory="protocol",
            mode="tag",
        ),
        sender=stranger.public_key(),
    )
    assert svc.tracked_coordinates() == []
    await svc.stop()


def test_release_announcement_key_normalizes() -> None:
    assert release_announcement_key("O", "R", " V ") == ("o", "r", "V")


@pytest.mark.asyncio
async def test_project_data_from_kind30078_roundtrip() -> None:
    p = ProjectData(
        owner="rust-nostr",
        repo="nostr",
        name="nostr",
        description="d",
        category="nostr",
        subcategory="protocol",
        tracking_mode="release",
        release_version="v1.2.0",
        release_date_iso="2024-06-01",
        stars=7,
        forks=2,
        open_issues=0,
        stale=True,
    )
    keys = Keys.generate()
    signer = NostrSigner.keys(keys)
    event = await build_kind30078_builder(p).sign(signer)
    out = project_data_from_kind30078_event(event)
    assert out is not None
    assert out.owner == "rust-nostr"
    assert out.repo == "nostr"
    assert out.category == "nostr"
    assert out.subcategory == "protocol"
    assert out.tracking_mode == "release"
    assert out.release_version == "v1.2.0"
    assert out.stars == 7
    assert out.stale is True


@pytest.mark.asyncio
async def test_project_data_from_kind30078_wrong_kind_returns_none() -> None:
    keys = Keys.generate()
    signer = NostrSigner.keys(keys)
    data = ReleaseAnnouncementInput(
        owner="o",
        repo="r",
        version_label="v1",
        published_at_iso="2024-01-01",
    )
    event = await build_release_announcement_builder(data).sign(signer)
    assert project_data_from_kind30078_event(event) is None
