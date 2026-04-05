"""Pydantic schema validation edge cases."""

from __future__ import annotations

import pytest

from gitlurker.models.schemas import ProjectData


def test_project_data_rejects_invalid_category() -> None:
    with pytest.raises(ValueError, match="category"):
        ProjectData(
            owner="o",
            repo="r",
            category="not-a-category",
            subcategory="other",
            tracking_mode="release",
        )


def test_project_data_rejects_invalid_subcategory() -> None:
    with pytest.raises(ValueError, match="subcategory"):
        ProjectData(
            owner="o",
            repo="r",
            category="other",
            subcategory="not-a-sub",
            tracking_mode="release",
        )
