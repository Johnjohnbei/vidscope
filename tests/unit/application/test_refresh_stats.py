"""Unit tests for RefreshStatsUseCase — single + batch + error isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from vidscope.application.refresh_stats import (
    RefreshStatsResult,
    RefreshStatsUseCase,
)
from vidscope.domain import DomainError, Platform, PlatformId, Video, VideoId, VideoStats


class _FrozenClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _make_video(*, vid: int, url: str = "https://x.y/a", days_old: int = 0) -> Video:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    return Video(
        id=VideoId(vid),
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=url,
        created_at=now - timedelta(days=days_old),
    )


def _make_uow_factory(
    *,
    videos: list[Video],
    latest_stats: dict[int, VideoStats] | None = None,
) -> Any:
    latest_stats = latest_stats or {}

    class _FakeUoW:
        def __init__(self) -> None:
            self.videos = MagicMock()
            self.videos.get = MagicMock(
                side_effect=lambda vid: next((v for v in videos if v.id == vid), None)
            )
            self.videos.list_recent = MagicMock(return_value=videos)
            self.video_stats = MagicMock()
            self.video_stats.latest_for_video = MagicMock(
                side_effect=lambda vid: latest_stats.get(int(vid))
            )
            self.video_stats.append = MagicMock(side_effect=lambda s: s)

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    def factory() -> Any:
        return _FakeUoW()

    return factory


def _make_stage(*, ok: bool = True, error_msg: str = "") -> Any:
    stage = MagicMock()
    result = MagicMock()
    result.skipped = not ok
    result.message = "stats appended" if ok else error_msg
    stage.execute = MagicMock(return_value=result)
    return stage


def _make_stage_raises(exc: Exception) -> Any:
    stage = MagicMock()
    stage.execute = MagicMock(side_effect=exc)
    return stage


# ---------------------------------------------------------------------------
# execute_one tests
# ---------------------------------------------------------------------------


def test_execute_one_video_not_found() -> None:
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(),
        unit_of_work_factory=_make_uow_factory(videos=[]),
        clock=_FrozenClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    result = uc.execute_one(VideoId(999))
    assert result.success is False
    assert "not found" in result.message


def test_execute_one_happy_path() -> None:
    video = _make_video(vid=1)
    latest = VideoStats(
        video_id=VideoId(1),
        captured_at=datetime(2026, 1, 10, tzinfo=UTC),
        view_count=500,
    )
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(ok=True),
        unit_of_work_factory=_make_uow_factory(videos=[video], latest_stats={1: latest}),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    result = uc.execute_one(VideoId(1))
    assert result.success is True
    assert result.stats is not None
    assert result.stats.view_count == 500
    assert result.video_id == 1


def test_execute_one_probe_failure_domain_error() -> None:
    """Stage raises DomainError (probe returned None) -> success=False."""
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage_raises(DomainError("stats probe returned no data")),
        unit_of_work_factory=_make_uow_factory(videos=[_make_video(vid=1)]),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    result = uc.execute_one(VideoId(1))
    assert result.success is False
    assert "probe" in result.message or "no data" in result.message


def test_execute_one_probe_stage_skipped() -> None:
    """Stage returns skipped=True -> success=False with message."""
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(ok=False, error_msg="probe returned no data"),
        unit_of_work_factory=_make_uow_factory(videos=[_make_video(vid=1)]),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    result = uc.execute_one(VideoId(1))
    assert result.success is False


# ---------------------------------------------------------------------------
# execute_all tests
# ---------------------------------------------------------------------------


def test_execute_all_isolates_per_video_errors() -> None:
    videos = [_make_video(vid=1), _make_video(vid=2), _make_video(vid=3)]
    call_count = {"n": 0}

    stage = MagicMock()

    def _exec(ctx: Any, uow: Any) -> Any:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("network down")
        r = MagicMock()
        r.skipped = False
        r.message = "ok"
        return r

    stage.execute = _exec

    uc = RefreshStatsUseCase(
        stats_stage=stage,
        unit_of_work_factory=_make_uow_factory(videos=videos),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    batch = uc.execute_all(limit=10)
    assert batch.total == 3
    assert batch.refreshed == 2
    assert batch.failed == 1


def test_execute_all_since_filter() -> None:
    old = _make_video(vid=1, days_old=30)
    recent = _make_video(vid=2, days_old=3)
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(ok=True),
        unit_of_work_factory=_make_uow_factory(videos=[old, recent]),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    batch = uc.execute_all(since=timedelta(days=7), limit=10)
    assert batch.total == 1
    assert batch.per_video[0].video_id == 2


def test_execute_all_rejects_limit_zero() -> None:
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(),
        unit_of_work_factory=_make_uow_factory(videos=[]),
        clock=_FrozenClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="limit"):
        uc.execute_all(limit=0)


def test_execute_all_rejects_limit_negative() -> None:
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(),
        unit_of_work_factory=_make_uow_factory(videos=[]),
        clock=_FrozenClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="limit"):
        uc.execute_all(limit=-5)


def test_execute_all_happy_path_multiple_videos() -> None:
    videos = [_make_video(vid=i) for i in range(1, 4)]
    latest_stats = {
        i: VideoStats(
            video_id=VideoId(i),
            captured_at=datetime(2026, 1, 10, tzinfo=UTC),
            view_count=i * 100,
        )
        for i in range(1, 4)
    }
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(ok=True),
        unit_of_work_factory=_make_uow_factory(videos=videos, latest_stats=latest_stats),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    batch = uc.execute_all(limit=10)
    assert batch.total == 3
    assert batch.refreshed == 3
    assert batch.failed == 0


# ---------------------------------------------------------------------------
# S03 — RefreshStatsForWatchlistUseCase
# ---------------------------------------------------------------------------


def _make_watched_account(*, platform: Platform, handle: str) -> Any:
    from vidscope.domain import WatchedAccount
    return WatchedAccount(
        platform=platform,
        handle=handle,
        url=f"https://x.y/@{handle}",
    )


def _make_s03_uow_factory(
    *,
    accounts: list[Any],
    videos_by_handle: dict[str, list[Video]],
) -> Any:
    """Build a fake UoW factory for S03 watchlist tests.

    Supports watch_accounts.list_all and videos.list_by_author(platform, handle).
    """

    class _FakeUoW:
        def __init__(self) -> None:
            from unittest.mock import MagicMock
            self.watch_accounts = MagicMock()
            self.watch_accounts.list_all = MagicMock(return_value=accounts)
            self.videos = MagicMock()
            self.videos.list_by_author = MagicMock(
                side_effect=lambda platform, handle, limit=1000: videos_by_handle.get(handle, [])
            )
            self.video_stats = MagicMock()
            self.video_stats.latest_for_video = MagicMock(return_value=None)
            self.video_stats.append = MagicMock(side_effect=lambda s: s)

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    def factory() -> Any:
        return _FakeUoW()

    return factory


def test_refresh_stats_watchlist_empty() -> None:
    """No watched accounts => all counters zero."""
    from vidscope.application.refresh_stats import (
        RefreshStatsForWatchlistUseCase,
    )

    refresh_mock = MagicMock()
    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=_make_s03_uow_factory(accounts=[], videos_by_handle={}),
    )
    result = uc.execute()
    assert result.accounts_checked == 0
    assert result.videos_checked == 0
    assert result.stats_refreshed == 0
    refresh_mock.execute_one.assert_not_called()


def test_refresh_stats_watchlist_happy_path() -> None:
    """2 accounts x 3 videos each => videos_checked=6, stats_refreshed=6."""
    from vidscope.application.refresh_stats import (
        RefreshStatsForWatchlistUseCase,
    )

    account = _make_watched_account(platform=Platform.YOUTUBE, handle="alice")
    videos = [
        Video(id=VideoId(i), platform=Platform.YOUTUBE, platform_id=PlatformId(f"p{i}"), url=f"https://x.y/{i}")
        for i in (10, 11, 12)
    ]

    refresh_mock = MagicMock()
    refresh_mock.execute_one = MagicMock(return_value=RefreshStatsResult(
        success=True, video_id=1, stats=None, message="ok",
    ))

    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=_make_s03_uow_factory(
            accounts=[account],
            videos_by_handle={"alice": videos},
        ),
    )
    result = uc.execute()
    assert result.accounts_checked == 1
    assert result.videos_checked == 3
    assert result.stats_refreshed == 3
    assert result.failed == 0
    assert refresh_mock.execute_one.call_count == 3


def test_refresh_stats_watchlist_per_video_error_isolation() -> None:
    """Error on one video => failed++, batch continues for next video."""
    from vidscope.application.refresh_stats import (
        RefreshStatsForWatchlistUseCase,
    )

    account = _make_watched_account(platform=Platform.YOUTUBE, handle="alice")
    videos = [
        Video(id=VideoId(10), platform=Platform.YOUTUBE, platform_id=PlatformId("p10"), url="https://x.y/10"),
        Video(id=VideoId(11), platform=Platform.YOUTUBE, platform_id=PlatformId("p11"), url="https://x.y/11"),
    ]

    call_n: dict[str, int] = {"n": 0}

    def _exec(vid: Any) -> Any:
        call_n["n"] += 1
        if call_n["n"] == 1:
            raise RuntimeError("network down")
        return RefreshStatsResult(success=True, video_id=int(vid), stats=None, message="ok")

    refresh_mock = MagicMock()
    refresh_mock.execute_one = _exec

    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=_make_s03_uow_factory(
            accounts=[account],
            videos_by_handle={"alice": videos},
        ),
    )
    result = uc.execute()
    assert result.videos_checked == 2
    assert result.stats_refreshed == 1
    assert result.failed == 1
    assert any("network down" in e for e in result.errors)


def test_refresh_stats_watchlist_per_account_error_isolation() -> None:
    """list_by_author failure for account A => account B still processed."""
    from vidscope.application.refresh_stats import (
        RefreshStatsForWatchlistUseCase,
    )

    account_a = _make_watched_account(platform=Platform.YOUTUBE, handle="ghost")
    account_b = _make_watched_account(platform=Platform.YOUTUBE, handle="bob")

    # ghost raises on list_by_author, bob returns one video
    bob_video = Video(id=VideoId(20), platform=Platform.YOUTUBE, platform_id=PlatformId("p20"), url="https://x.y/20")

    class _FakeUoW:
        def __init__(self) -> None:
            self.watch_accounts = MagicMock()
            self.watch_accounts.list_all = MagicMock(return_value=[account_a, account_b])
            self.videos = MagicMock()

            def _list_by_author(platform: Any, handle: str, limit: int = 1000) -> Any:
                if handle == "ghost":
                    raise RuntimeError("ghost account vanished")
                return [bob_video]

            self.videos.list_by_author = _list_by_author
            self.video_stats = MagicMock()
            self.video_stats.latest_for_video = MagicMock(return_value=None)

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    refresh_mock = MagicMock()
    refresh_mock.execute_one = MagicMock(return_value=RefreshStatsResult(
        success=True, video_id=20, stats=None, message="ok"
    ))

    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=lambda: _FakeUoW(),
    )
    result = uc.execute()
    assert result.accounts_checked == 2
    assert result.videos_checked == 1
    assert result.stats_refreshed == 1
    assert any("ghost" in e for e in result.errors)


def test_s02_refresh_stats_use_case_unchanged() -> None:
    """Regression: RefreshStatsUseCase still exports execute_one and execute_all."""
    assert hasattr(RefreshStatsUseCase, "execute_one")
    assert hasattr(RefreshStatsUseCase, "execute_all")
