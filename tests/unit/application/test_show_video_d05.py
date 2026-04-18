"""Tests for ShowVideoUseCase D-05 extension (M009/S04).

Tests the two new fields added to ShowVideoResult:
- latest_stats: VideoStats | None
- views_velocity_24h: float | None

Uses MagicMock for the UoW to keep tests isolated from the DB.
These tests are separate from test_show_video.py which has pre-existing
import errors (references to Creator entity not yet in domain).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from vidscope.application.show_video import ShowVideoResult, ShowVideoUseCase
from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats


def _make_video(vid: int = 1) -> Video:
    return Video(
        id=VideoId(vid),
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=f"https://x.y/{vid}",
        title=f"Video {vid}",
    )


def _make_stats(vid: int = 1, captured_at: datetime | None = None, view_count: int = 1000) -> VideoStats:
    ts = captured_at or datetime(2026, 1, 5, tzinfo=UTC)
    return VideoStats(
        video_id=VideoId(vid),
        captured_at=ts,
        view_count=view_count,
        like_count=50,
        comment_count=10,
    )


def _make_fake_uow(
    *,
    video: Video | None,
    latest_stats: VideoStats | None,
    history: list[VideoStats],
) -> MagicMock:
    uow = MagicMock()
    uow.__enter__ = lambda self: self
    uow.__exit__ = lambda *a: None
    uow.videos.get = MagicMock(return_value=video)
    uow.transcripts.get_for_video = MagicMock(return_value=None)
    uow.frames.list_for_video = MagicMock(return_value=[])
    uow.analyses.get_latest_for_video = MagicMock(return_value=None)
    uow.video_stats.latest_for_video = MagicMock(return_value=latest_stats)
    uow.video_stats.list_for_video = MagicMock(return_value=history)
    return uow


# ---------------------------------------------------------------------------
# Test 1: ShowVideoResult has the two new D-05 fields
# ---------------------------------------------------------------------------


def test_show_video_result_has_d05_fields() -> None:
    """ShowVideoResult exposes latest_stats and views_velocity_24h with None defaults."""
    result = ShowVideoResult(found=False)
    assert result.latest_stats is None
    assert result.views_velocity_24h is None


# ---------------------------------------------------------------------------
# Test 2: execute populates latest_stats from video_stats.latest_for_video
# ---------------------------------------------------------------------------


def test_show_video_includes_latest_stats_when_present() -> None:
    """execute(1) returns result.latest_stats populated from repo."""
    video = _make_video(1)
    latest = _make_stats(1, view_count=1000)
    history = [
        _make_stats(1, captured_at=datetime(2026, 1, 1, tzinfo=UTC), view_count=100),
        latest,
    ]
    fake_uow = _make_fake_uow(video=video, latest_stats=latest, history=history)

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(1)

    assert result.found is True
    assert result.latest_stats is not None
    assert result.latest_stats.view_count == 1000
    fake_uow.video_stats.latest_for_video.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3: views_velocity_24h computed via metrics when >= 2 snapshots
# ---------------------------------------------------------------------------


def test_show_video_velocity_computed_for_two_snapshots() -> None:
    """views_velocity_24h is computed via metrics.py when history has >= 2 rows."""
    video = _make_video(1)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    snap1 = _make_stats(1, captured_at=base, view_count=0)
    snap2 = _make_stats(1, captured_at=base + timedelta(hours=1), view_count=24)
    latest = snap2
    history = [snap1, snap2]
    fake_uow = _make_fake_uow(video=video, latest_stats=latest, history=history)

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(1)

    assert result.views_velocity_24h is not None
    # delta=24 views / 1h = 24 views/hour
    assert result.views_velocity_24h == pytest.approx(24.0)


# ---------------------------------------------------------------------------
# Test 4: when 0 stats rows, both fields are None
# ---------------------------------------------------------------------------


def test_show_video_no_stats_rows_gives_none_fields() -> None:
    """When video_stats has no rows, latest_stats and velocity are None."""
    video = _make_video(1)
    fake_uow = _make_fake_uow(video=video, latest_stats=None, history=[])

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(1)

    assert result.found is True
    assert result.latest_stats is None
    assert result.views_velocity_24h is None


# ---------------------------------------------------------------------------
# Test 5: single snapshot — latest_stats present but velocity is None
# ---------------------------------------------------------------------------


def test_show_video_single_snapshot_velocity_is_none() -> None:
    """Only 1 snapshot -> latest_stats is set but velocity is None (< 2 rows)."""
    video = _make_video(1)
    only = _make_stats(1, captured_at=datetime(2026, 1, 1, tzinfo=UTC), view_count=100)
    fake_uow = _make_fake_uow(video=video, latest_stats=only, history=[only])

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(1)

    assert result.latest_stats == only
    assert result.views_velocity_24h is None  # < 2 snapshots


# ---------------------------------------------------------------------------
# Test 6: video not found — both new fields remain None
# ---------------------------------------------------------------------------


def test_show_video_not_found_new_fields_are_none() -> None:
    """found=False result has latest_stats=None, views_velocity_24h=None."""
    fake_uow = _make_fake_uow(video=None, latest_stats=None, history=[])

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(999)

    assert result.found is False
    assert result.latest_stats is None
    assert result.views_velocity_24h is None


# ---------------------------------------------------------------------------
# Test 7: backward compatibility — old callers without video_stats still work
# ---------------------------------------------------------------------------


def test_show_video_result_backward_compatible() -> None:
    """ShowVideoResult can be constructed without the new D-05 fields."""
    video = _make_video(1)
    # Construct result the old way (no latest_stats, no velocity)
    result = ShowVideoResult(found=True, video=video)
    assert result.found is True
    assert result.latest_stats is None
    assert result.views_velocity_24h is None
    assert result.frames == ()
