"""Tests for ``gitlurker.scripts.seed`` fixture parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitlurker.models.schemas import ProjectData
from gitlurker.scripts.seed import (
    load_legacy_fixture,
    merge_project_lists,
    project_data_to_django_fixture_row,
    write_stale_seed_json,
)


def test_load_legacy_fixture_maps_categories(tmp_path: Path) -> None:
    fixture = tmp_path / "seed.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "model": "git_lurker.project",
                    "pk": 1,
                    "fields": {
                        "repository": "bitcoin",
                        "owner": "bitcoin",
                        "category": "lightning",
                        "subcategory": "protocol",
                    },
                },
                {
                    "model": "git_lurker.project",
                    "pk": 2,
                    "fields": {
                        "repository": "cashu",
                        "owner": "cashubtc",
                        "category": "e-cash",
                        "subcategory": "wallet",
                    },
                },
            ],
        ),
        encoding="utf-8",
    )
    rows = load_legacy_fixture(fixture)
    assert len(rows) == 2
    assert rows[0].owner == "bitcoin"
    assert rows[0].repo == "bitcoin"
    assert rows[0].category == "layer2"
    assert rows[0].subcategory == "protocol"
    assert rows[0].tracking_mode == "release"
    assert rows[1].category == "ecash"


def test_load_legacy_fixture_skips_bad_rows(tmp_path: Path) -> None:
    fixture = tmp_path / "bad.json"
    fixture.write_text(
        json.dumps(
            [
                {"model": "x", "pk": 1, "fields": {}},
                {
                    "model": "git_lurker.project",
                    "pk": 2,
                    "fields": {
                        "repository": "r",
                        "owner": "o",
                        "category": "bitcoin",
                        "subcategory": "unknown_sub",
                    },
                },
            ],
        ),
        encoding="utf-8",
    )
    rows = load_legacy_fixture(fixture)
    assert len(rows) == 1
    assert rows[0].subcategory == "other"


def test_load_legacy_fixture_maps_ai_category(tmp_path: Path) -> None:
    fixture = tmp_path / "ai.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "model": "git_lurker.project",
                    "pk": 1,
                    "fields": {
                        "repository": "x",
                        "owner": "y",
                        "category": "ai",
                        "subcategory": "agent",
                    },
                },
            ],
        ),
        encoding="utf-8",
    )
    rows = load_legacy_fixture(fixture)
    assert rows[0].category == "ai"
    assert rows[0].subcategory == "agent"


def test_merge_project_lists_dedupes(tmp_path: Path) -> None:
    a = ProjectData(
        owner="O",
        repo="R",
        name="R",
        description="",
        category="bitcoin",
        subcategory="wallet",
        tracking_mode="release",
    )
    b = ProjectData(
        owner="o",
        repo="r",
        name="r",
        description="",
        category="nostr",
        subcategory="client",
        tracking_mode="release",
    )
    c = ProjectData(
        owner="other",
        repo="repo",
        name="repo",
        description="",
        category="nostr",
        subcategory="relay",
        tracking_mode="release",
    )
    merged = merge_project_lists([a], [b, c])
    assert len(merged) == 2
    assert merged[0].owner == "O"
    assert merged[1].owner == "other"


def test_load_legacy_fixture_rejects_non_array(tmp_path: Path) -> None:
    fixture = tmp_path / "nope.json"
    fixture.write_text('{"x": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        load_legacy_fixture(fixture)


def test_project_data_roundtrips_through_django_fixture_row(tmp_path: Path) -> None:
    p = ProjectData(
        owner="CashuBTC",
        repo="cashu",
        name="cashu",
        description="",
        category="ecash",
        subcategory="wallet",
        tracking_mode="release",
        stale=True,
    )
    row = project_data_to_django_fixture_row(p, 42)
    (tmp_path / "roundtrip.json").write_text(json.dumps([row]), encoding="utf-8")
    loaded = load_legacy_fixture(tmp_path / "roundtrip.json")
    assert len(loaded) == 1
    assert loaded[0].owner == "CashuBTC"
    assert loaded[0].repo == "cashu"
    assert loaded[0].category == "ecash"
    assert loaded[0].subcategory == "wallet"


def test_project_data_fixture_row_maps_layer2_to_lightning(tmp_path: Path) -> None:
    p = ProjectData(
        owner="o",
        repo="r",
        name="r",
        description="",
        category="layer2",
        subcategory="protocol",
        tracking_mode="release",
    )
    row = project_data_to_django_fixture_row(p, 1)
    assert row["fields"]["category"] == "lightning"
    (tmp_path / "l2.json").write_text(json.dumps([row]), encoding="utf-8")
    loaded = load_legacy_fixture(tmp_path / "l2.json")
    assert loaded[0].category == "layer2"


def test_write_stale_seed_json_sorts_by_owner_repo(tmp_path: Path) -> None:
    a = ProjectData(
        owner="zebra",
        repo="z",
        name="z",
        description="",
        category="bitcoin",
        subcategory="other",
        tracking_mode="release",
        stale=True,
    )
    b = ProjectData(
        owner="alice",
        repo="b",
        name="b",
        description="",
        category="nostr",
        subcategory="client",
        tracking_mode="release",
        stale=True,
    )
    out = tmp_path / "stale_seed.json"
    write_stale_seed_json(out, [a, b])
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert [r["fields"]["owner"] for r in raw] == ["alice", "zebra"]
    assert raw[0]["pk"] == 1 and raw[1]["pk"] == 2
