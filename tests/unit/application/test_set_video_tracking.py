"""Unit tests for SetVideoTrackingUseCase (M011/S01/R056)."""

from __future__ import annotations

from vidscope.application.set_video_tracking import (
    SetVideoTrackingResult,
    SetVideoTrackingUseCase,
)
from vidscope.domain import TrackingStatus, VideoId, VideoTracking


class _FakeTrackingRepo:
    def __init__(self) -> None:
        self._store: dict[int, VideoTracking] = {}
        self.upsert_calls: list[VideoTracking] = []

    def get_for_video(self, video_id: VideoId) -> VideoTracking | None:
        return self._store.get(int(video_id))

    def upsert(self, tracking: VideoTracking) -> VideoTracking:
        self.upsert_calls.append(tracking)
        persisted = VideoTracking(
            video_id=tracking.video_id,
            status=tracking.status,
            starred=tracking.starred,
            notes=tracking.notes,
            id=42,
        )
        self._store[int(tracking.video_id)] = persisted
        return persisted

    def list_by_status(self, status: TrackingStatus, *, limit: int = 1000) -> list[VideoTracking]:
        return []

    def list_starred(self, *, limit: int = 1000) -> list[VideoTracking]:
        return []


class _FakeUoW:
    def __init__(self, tracking_repo: _FakeTrackingRepo) -> None:
        self.video_tracking = tracking_repo

    def __enter__(self) -> _FakeUoW:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _make_factory(repo: _FakeTrackingRepo):
    def _factory() -> _FakeUoW:
        return _FakeUoW(repo)
    return _factory


class TestSetVideoTrackingUseCase:
    def test_creates_new_tracking_row(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        result = uc.execute(1, status=TrackingStatus.SAVED)

        assert isinstance(result, SetVideoTrackingResult)
        assert result.created is True
        assert result.tracking.status is TrackingStatus.SAVED
        assert result.tracking.starred is False
        assert len(repo.upsert_calls) == 1
        call = repo.upsert_calls[0]
        assert call.video_id == VideoId(1)
        assert call.notes is None

    def test_updates_existing_tracking_row(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW)
        result = uc.execute(1, status=TrackingStatus.ACTIONED, starred=True)
        assert result.created is False
        assert result.tracking.status is TrackingStatus.ACTIONED
        assert result.tracking.starred is True

    def test_notes_none_preserves_existing(self) -> None:
        """Open Q 3: --note absent => preserve existing notes."""
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW, notes="first")
        result = uc.execute(1, status=TrackingStatus.SAVED, notes=None)
        assert result.tracking.notes == "first"

    def test_notes_empty_string_clears(self) -> None:
        """Open Q 3: --clear-note (notes='') clears existing."""
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW, notes="first")
        result = uc.execute(1, status=TrackingStatus.SAVED, notes="")
        assert result.tracking.notes == ""

    def test_notes_string_replaces(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW, notes="first")
        result = uc.execute(1, status=TrackingStatus.SAVED, notes="second")
        assert result.tracking.notes == "second"

    def test_starred_default_false(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        result = uc.execute(1, status=TrackingStatus.NEW)
        assert result.tracking.starred is False
