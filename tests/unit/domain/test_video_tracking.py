"""Unit tests for TrackingStatus enum + VideoTracking domain entity (M011/S01/R056)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from vidscope.domain import (
    TrackingStatus,
    VideoId,
    VideoTracking,
)


class TestTrackingStatusEnum:
    def test_has_exactly_six_members(self) -> None:
        assert {s.value for s in TrackingStatus} == {
            "new", "reviewed", "saved", "actioned", "ignored", "archived",
        }

    def test_construction_from_string(self) -> None:
        assert TrackingStatus("new") is TrackingStatus.NEW
        assert TrackingStatus("reviewed") is TrackingStatus.REVIEWED
        assert TrackingStatus("saved") is TrackingStatus.SAVED
        assert TrackingStatus("actioned") is TrackingStatus.ACTIONED
        assert TrackingStatus("ignored") is TrackingStatus.IGNORED
        assert TrackingStatus("archived") is TrackingStatus.ARCHIVED

    def test_strenum_semantics(self) -> None:
        assert str(TrackingStatus.NEW) == "new"
        assert TrackingStatus.NEW == "new"

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            TrackingStatus("bogus")


class TestVideoTrackingEntity:
    def test_minimal_construction(self) -> None:
        vt = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        assert vt.video_id == VideoId(1)
        assert vt.status is TrackingStatus.NEW
        assert vt.starred is False
        assert vt.notes is None
        assert vt.id is None
        assert vt.created_at is None
        assert vt.updated_at is None

    def test_full_construction(self) -> None:
        now = datetime.now(UTC)
        vt = VideoTracking(
            video_id=VideoId(42),
            status=TrackingStatus.SAVED,
            starred=True,
            notes="look at the hook",
            id=7,
            created_at=now,
            updated_at=now,
        )
        assert vt.starred is True
        assert vt.notes == "look at the hook"
        assert vt.id == 7
        assert vt.created_at == now

    def test_frozen_prevents_mutation(self) -> None:
        vt = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        with pytest.raises(dataclasses.FrozenInstanceError):
            vt.status = TrackingStatus.SAVED  # type: ignore[misc]

    def test_slots_prevents_new_attributes(self) -> None:
        vt = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        assert not hasattr(vt, "__dict__")
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError, TypeError)):
            vt.bogus = "x"  # type: ignore[attr-defined]

    def test_notes_none_vs_empty_string_distinct(self) -> None:
        unset = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        cleared = VideoTracking(
            video_id=VideoId(1), status=TrackingStatus.NEW, notes="",
        )
        assert unset.notes is None
        assert cleared.notes == ""
        assert unset.notes != cleared.notes


class TestPortReExports:
    """Ensure VideoTrackingRepository + UoW attr are wired."""

    def test_port_repository_importable(self) -> None:
        from vidscope.ports import VideoTrackingRepository

        assert VideoTrackingRepository is not None

    def test_uow_protocol_declares_video_tracking(self) -> None:
        from vidscope.ports import UnitOfWork

        # Protocol annotations are readable via __annotations__
        anns = UnitOfWork.__annotations__
        assert "video_tracking" in anns

    def test_video_tracking_repository_is_runtime_checkable(self) -> None:
        from vidscope.ports import VideoTrackingRepository

        # @runtime_checkable Protocols have _is_runtime_protocol True
        assert getattr(VideoTrackingRepository, "_is_runtime_protocol", False) is True
