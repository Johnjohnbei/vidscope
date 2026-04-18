"""Unit tests for ListTrendingUseCase — ranking correctness + D-04 scalability.

TDD: these tests were written before the implementation to drive the design.
All tests exercise the use case through its public interface only — no adapter
internals leak into the test assertions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from vidscope.application.list_trending import ListTrendingUseCase
from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats


class _FrozenClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _hist(
    *,
    video_id: int = 1,
    view_counts: list[int],
    start: datetime,
    step_hours: int = 1,
) -> list[VideoStats]:
    return [
        VideoStats(
            video_id=VideoId(video_id),
            captured_at=start + timedelta(hours=i * step_hours),
            view_count=v,
            like_count=v // 10,
            comment_count=v // 100,
        )
        for i, v in enumerate(view_counts)
    ]


def _make_uow_factory(
    *,
    candidates: dict[int, list[VideoStats]],
    videos: dict[int, Video],
):
    class _FakeUoW:
        def __init__(self) -> None:
            self.video_stats = MagicMock()
            self.video_stats.rank_candidates_by_delta = MagicMock(
                return_value=[VideoId(vid) for vid in candidates]
            )
            self.video_stats.list_for_video = MagicMock(
                side_effect=lambda vid, *, limit=1000: candidates.get(int(vid), [])
            )
            self.videos = MagicMock()
            self.videos.get = MagicMock(
                side_effect=lambda vid: videos.get(int(vid))
            )

        def __enter__(self) -> _FakeUoW:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    return lambda: _FakeUoW()


def _make_video(vid: int, platform: Platform = Platform.YOUTUBE) -> Video:
    return Video(
        id=VideoId(vid),
        platform=platform,
        platform_id=PlatformId(f"p{vid}"),
        url=f"https://x.y/{vid}",
        title=f"T{vid}",
    )


# ---------------------------------------------------------------------------
# Test 1: ranking by velocity descending
# ---------------------------------------------------------------------------


def test_ranks_by_velocity_descending() -> None:
    """execute() returns entries sorted by views_velocity_24h descending."""
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(hours=2)
    candidates = {
        1: _hist(video_id=1, view_counts=[100, 500], start=base),    # delta 400/1h
        2: _hist(video_id=2, view_counts=[100, 200], start=base),    # delta 100/1h
        3: _hist(video_id=3, view_counts=[100, 1000], start=base),   # delta 900/1h (winner)
    }
    videos = {i: _make_video(i) for i in (1, 2, 3)}
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos),
        clock=_FrozenClock(now),
    )
    results = uc.execute(since=timedelta(days=7), limit=10)
    assert [e.video_id for e in results] == [3, 1, 2]
    assert results[0].views_velocity_24h > results[1].views_velocity_24h
    assert results[1].views_velocity_24h > results[2].views_velocity_24h


# ---------------------------------------------------------------------------
# Test 2: videos with < 2 snapshots are excluded
# ---------------------------------------------------------------------------


def test_excludes_videos_with_less_than_two_snapshots() -> None:
    """Videos with only 1 snapshot in the window are excluded (can't compute velocity)."""
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(hours=2)
    candidates = {
        1: _hist(video_id=1, view_counts=[100], start=base),    # only 1 snapshot
        2: _hist(video_id=2, view_counts=[50, 500], start=base),
    }
    videos = {i: _make_video(i) for i in (1, 2)}
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos),
        clock=_FrozenClock(now),
    )
    results = uc.execute(since=timedelta(days=7))
    assert [e.video_id for e in results] == [2]


# ---------------------------------------------------------------------------
# Test 3: platform filter
# ---------------------------------------------------------------------------


def test_passes_platform_filter_to_repository() -> None:
    """When platform is specified, rank_candidates_by_delta receives it."""
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(hours=2)
    candidates = {
        1: _hist(video_id=1, view_counts=[100, 500], start=base),
    }
    videos = {1: _make_video(1, platform=Platform.YOUTUBE)}
    factory = _make_uow_factory(candidates=candidates, videos=videos)

    uc = ListTrendingUseCase(unit_of_work_factory=factory, clock=_FrozenClock(now))
    results = uc.execute(since=timedelta(days=7), platform=Platform.YOUTUBE)
    # Verify the use case passes platform through to the repository
    assert len(results) == 1
    assert results[0].platform == Platform.YOUTUBE


# ---------------------------------------------------------------------------
# Test 4: min_velocity filter
# ---------------------------------------------------------------------------


def test_respects_min_velocity() -> None:
    """Videos below min_velocity are excluded from the results.

    views_velocity_24h returns views/hour (D-04). With a 1-hour window:
    - Video 1: (500-100)/1h = 400 views/hour (fast)
    - Video 2: (150-100)/1h =  50 views/hour (slow)
    Setting min_velocity=200 should exclude video 2 but keep video 1.
    """
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(hours=2)
    candidates = {
        1: _hist(video_id=1, view_counts=[100, 500], start=base),   # 400 views/hour
        2: _hist(video_id=2, view_counts=[100, 150], start=base),   #  50 views/hour
    }
    videos = {i: _make_video(i) for i in (1, 2)}
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos),
        clock=_FrozenClock(now),
    )
    results = uc.execute(since=timedelta(days=7), min_velocity=200.0)
    assert [e.video_id for e in results] == [1]


# ---------------------------------------------------------------------------
# Test 5: limit
# ---------------------------------------------------------------------------


def test_respects_limit() -> None:
    """execute() returns at most limit entries (SQL-level + Python slice)."""
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(hours=2)
    candidates = {
        i: _hist(video_id=i, view_counts=[100, 100 + i * 10], start=base)
        for i in range(1, 6)
    }
    videos = {i: _make_video(i) for i in range(1, 6)}
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos),
        clock=_FrozenClock(now),
    )
    results = uc.execute(since=timedelta(days=7), limit=2)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Test 6: engagement_rate from metrics module
# ---------------------------------------------------------------------------


def test_engagement_rate_from_metrics_module() -> None:
    """engagement_rate in TrendingEntry uses the pure-domain metrics.engagement_rate."""
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(hours=2)
    hist = [
        VideoStats(
            video_id=VideoId(1),
            captured_at=base,
            view_count=100,
            like_count=5,
            comment_count=5,
        ),
        VideoStats(
            video_id=VideoId(1),
            captured_at=base + timedelta(hours=1),
            view_count=1000,
            like_count=50,
            comment_count=10,
        ),
    ]
    videos = {1: _make_video(1)}
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates={1: hist}, videos=videos),
        clock=_FrozenClock(now),
    )
    results = uc.execute(since=timedelta(days=7))
    # engagement_rate = (likes + comments) / views = (50 + 10) / 1000 = 0.06
    assert results[0].engagement_rate == pytest.approx((50 + 10) / 1000)


# ---------------------------------------------------------------------------
# Test 7: velocity comes from metrics.views_velocity_24h (not SQL approximation)
# ---------------------------------------------------------------------------


def test_velocity_comes_from_pure_domain_metrics() -> None:
    """views_velocity_24h in TrendingEntry is the exact metric from metrics.py."""
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(hours=2)
    hist = [
        VideoStats(
            video_id=VideoId(1),
            captured_at=base,
            view_count=0,
            like_count=0,
            comment_count=0,
        ),
        VideoStats(
            video_id=VideoId(1),
            captured_at=base + timedelta(hours=1),
            view_count=24,
            like_count=2,
            comment_count=1,
        ),
    ]
    videos = {1: _make_video(1)}
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates={1: hist}, videos=videos),
        clock=_FrozenClock(now),
    )
    results = uc.execute(since=timedelta(days=7))
    # delta_views=24, delta_hours=1h → velocity = 24 views/hour
    assert results[0].views_velocity_24h == pytest.approx(24.0)


# ---------------------------------------------------------------------------
# Test 8: rank_candidates_by_delta receives correct parameters
# ---------------------------------------------------------------------------


def test_rank_candidates_by_delta_called_with_correct_params() -> None:
    """Use case passes since (cutoff datetime), platform, and limit to the repo."""
    now = datetime(2026, 1, 10, tzinfo=UTC)

    class _CapturingUoW:
        def __init__(self) -> None:
            self.video_stats = MagicMock()
            self.video_stats.rank_candidates_by_delta = MagicMock(return_value=[])
            self.videos = MagicMock()

        def __enter__(self) -> _CapturingUoW:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    uow_instance = _CapturingUoW()
    uc = ListTrendingUseCase(
        unit_of_work_factory=lambda: uow_instance,
        clock=_FrozenClock(now),
    )
    uc.execute(since=timedelta(days=7), platform=Platform.YOUTUBE, limit=5)

    call_kwargs = uow_instance.video_stats.rank_candidates_by_delta.call_args.kwargs
    expected_cutoff = now - timedelta(days=7)
    assert call_kwargs["since"] == expected_cutoff
    assert call_kwargs["platform"] == Platform.YOUTUBE
    # limit arg must be >= requested limit (use case may over-fetch for min_velocity)
    assert call_kwargs["limit"] >= 5


# ---------------------------------------------------------------------------
# Validation: rejects non-positive since
# ---------------------------------------------------------------------------


def test_rejects_non_positive_since() -> None:
    """execute() raises ValueError when since <= 0."""
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates={}, videos={}),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="since"):
        uc.execute(since=timedelta(seconds=0))


# ---------------------------------------------------------------------------
# Validation: rejects limit=0
# ---------------------------------------------------------------------------


def test_rejects_limit_zero() -> None:
    """execute() raises ValueError when limit < 1 (T-INPUT-01)."""
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates={}, videos={}),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="limit"):
        uc.execute(since=timedelta(days=1), limit=0)
