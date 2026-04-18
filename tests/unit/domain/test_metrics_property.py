"""Hypothesis property-based tests for vidscope.domain.metrics.

Gate non-négociable M009-S01 : ces 4 propriétés DOIVENT être vertes avant
tout merge. Elles couvrent :

1. views_velocity_24h — résultat >= 0 ou None (jamais négatif si vues croissent)
2. engagement_rate — retourne None quand view_count est 0 ou None (jamais ZeroDivisionError)
3. views_velocity_24h — None si < 2 snapshots
4. engagement_rate — valeur >= 0 quand computable
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vidscope.domain import VideoId, VideoStats
from vidscope.domain.metrics import engagement_rate, views_velocity_24h

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_DT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
_VIDEO_ID = VideoId(1)


def _make_stats(
    *,
    offset_hours: float = 0.0,
    view_count: int | None = None,
    like_count: int | None = None,
    comment_count: int | None = None,
    repost_count: int | None = None,
    save_count: int | None = None,
) -> VideoStats:
    """Build a VideoStats snapshot at a given hour offset from BASE_DT."""
    return VideoStats(
        video_id=_VIDEO_ID,
        captured_at=_BASE_DT + timedelta(hours=offset_hours),
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
        repost_count=repost_count,
        save_count=save_count,
    )


# ---------------------------------------------------------------------------
# Property 1: views_velocity_24h — zero-bug guard
# ---------------------------------------------------------------------------

@given(
    views=st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        min_size=2,
        max_size=20,
    )
)
@settings(max_examples=200)
def test_velocity_never_raises(views: list[int]) -> None:
    """Property 1: views_velocity_24h never raises, regardless of input shape."""
    history = [
        _make_stats(offset_hours=float(i), view_count=v)
        for i, v in enumerate(views)
    ]
    result = views_velocity_24h(history)
    # Result must be a float or None — never an exception
    assert result is None or isinstance(result, float)


# ---------------------------------------------------------------------------
# Property 2: engagement_rate — ZeroDivisionError / None guard (D-05)
# ---------------------------------------------------------------------------

@given(
    view_count=st.one_of(st.none(), st.just(0), st.integers(min_value=-100, max_value=0)),
    like_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
    comment_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
)
@settings(max_examples=200)
def test_engagement_rate_none_when_view_count_zero_or_none(
    view_count: int | None,
    like_count: int | None,
    comment_count: int | None,
) -> None:
    """Property 2: engagement_rate is always None when view_count <= 0 or None.

    This is the critical zero-bug guard: we must never divide by zero.
    """
    stats = VideoStats(
        video_id=_VIDEO_ID,
        captured_at=_BASE_DT,
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
    )
    result = engagement_rate(stats)
    assert result is None, (
        f"Expected None for view_count={view_count!r}, got {result!r}"
    )


# ---------------------------------------------------------------------------
# Property 3: views_velocity_24h — None when fewer than 2 snapshots
# ---------------------------------------------------------------------------

@given(
    view_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000)),
)
@settings(max_examples=100)
def test_velocity_none_for_single_snapshot(view_count: int | None) -> None:
    """Property 3: velocity is None for a single snapshot (need at least 2)."""
    history = [_make_stats(view_count=view_count)]
    assert views_velocity_24h(history) is None


@given(st.just([]))
def test_velocity_none_for_empty_history(history: list[VideoStats]) -> None:
    """Property 3b: velocity is None for empty history."""
    assert views_velocity_24h(history) is None


# ---------------------------------------------------------------------------
# Property 4: engagement_rate — non-negative when computable (additivity)
# ---------------------------------------------------------------------------

@given(
    view_count=st.integers(min_value=1, max_value=10_000_000),
    like_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000)),
    comment_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000)),
    repost_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000)),
    save_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000)),
)
@settings(max_examples=300)
def test_engagement_rate_non_negative_when_computable(
    view_count: int,
    like_count: int | None,
    comment_count: int | None,
    repost_count: int | None,
    save_count: int | None,
) -> None:
    """Property 4: engagement_rate >= 0 when view_count > 0 (additivity).

    The numerator is a sum of non-negative counts; dividing by a positive
    view_count must always yield a non-negative float.
    """
    stats = VideoStats(
        video_id=_VIDEO_ID,
        captured_at=_BASE_DT,
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
        repost_count=repost_count,
        save_count=save_count,
    )
    result = engagement_rate(stats)
    assert result is not None
    assert result >= 0.0, f"Expected non-negative engagement rate, got {result!r}"


# ---------------------------------------------------------------------------
# Deterministic regression tests (complement the property tests)
# ---------------------------------------------------------------------------

class TestViewsVelocity24hDeterministic:
    def test_basic_velocity(self) -> None:
        """200 views over 2 hours = 100 views/hour."""
        history = [
            _make_stats(offset_hours=0.0, view_count=1000),
            _make_stats(offset_hours=2.0, view_count=1200),
        ]
        result = views_velocity_24h(history)
        assert result == pytest.approx(100.0)

    def test_velocity_none_when_view_count_missing(self) -> None:
        """None counters make velocity None (D-03)."""
        history = [
            _make_stats(offset_hours=0.0, view_count=None),
            _make_stats(offset_hours=1.0, view_count=500),
        ]
        assert views_velocity_24h(history) is None

    def test_velocity_none_outside_24h_window(self) -> None:
        """Snapshots older than 24h from the latest are excluded from window."""
        history = [
            _make_stats(offset_hours=0.0, view_count=100),    # > 24h ago
            _make_stats(offset_hours=25.0, view_count=200),   # latest
        ]
        # Only 1 snapshot within 24h window → None
        assert views_velocity_24h(history) is None

    def test_velocity_same_captured_at_returns_none(self) -> None:
        """delta_seconds == 0 → None (avoid division by zero)."""
        t = _BASE_DT
        history = [
            VideoStats(video_id=_VIDEO_ID, captured_at=t, view_count=100),
            VideoStats(video_id=_VIDEO_ID, captured_at=t, view_count=200),
        ]
        assert views_velocity_24h(history) is None


class TestEngagementRateDeterministic:
    def test_basic_engagement_rate(self) -> None:
        """(50 + 20) / 1000 = 0.07."""
        stats = _make_stats(view_count=1000, like_count=50, comment_count=20)
        assert engagement_rate(stats) == pytest.approx(0.07)

    def test_all_none_counters_gives_zero_rate(self) -> None:
        """All None engagement counters → 0 / views = 0.0."""
        stats = _make_stats(view_count=1000)
        result = engagement_rate(stats)
        assert result == pytest.approx(0.0)

    def test_view_count_none_gives_none(self) -> None:
        stats = _make_stats(view_count=None, like_count=100)
        assert engagement_rate(stats) is None

    def test_view_count_zero_gives_none(self) -> None:
        stats = _make_stats(view_count=0, like_count=100)
        assert engagement_rate(stats) is None
