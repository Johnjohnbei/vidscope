"""Tests for the watchlist use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from vidscope.application.watchlist import (
    AddWatchedAccountUseCase,
    ListWatchedAccountsUseCase,
    RefreshWatchlistUseCase,
    RemoveWatchedAccountUseCase,
    _handle_from_url,
)
from vidscope.domain import (
    IngestError,
    Platform,
    PlatformId,
    RunStatus,
    Video,
    WatchedAccount,
)
from vidscope.pipeline.runner import PipelineContext, RunResult, StageOutcome
from vidscope.ports import ChannelEntry, UnitOfWorkFactory

from .conftest import FrozenClock

# ---------------------------------------------------------------------------
# _handle_from_url helper
# ---------------------------------------------------------------------------


class TestHandleFromUrl:
    def test_youtube_at_handle(self) -> None:
        h = _handle_from_url(
            "https://www.youtube.com/@YouTube", Platform.YOUTUBE
        )
        assert h == "@YouTube"

    def test_tiktok_at_handle(self) -> None:
        h = _handle_from_url(
            "https://www.tiktok.com/@tiktok", Platform.TIKTOK
        )
        assert h == "@tiktok"

    def test_instagram_at_handle(self) -> None:
        h = _handle_from_url(
            "https://www.instagram.com/@instagram", Platform.INSTAGRAM
        )
        assert h == "@instagram"

    def test_youtube_channel_path(self) -> None:
        h = _handle_from_url(
            "https://www.youtube.com/channel/UC1234567890",
            Platform.YOUTUBE,
        )
        assert h == "UC1234567890"


# ---------------------------------------------------------------------------
# AddWatchedAccountUseCase
# ---------------------------------------------------------------------------


class TestAddWatchedAccountUseCase:
    def test_add_youtube_account(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute("https://www.youtube.com/@YouTube")
        assert result.success is True
        assert result.account is not None
        assert result.account.platform is Platform.YOUTUBE
        assert result.account.handle == "@YouTube"

    def test_add_persists_to_db(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        uc.execute("https://www.youtube.com/@YouTube")
        with uow_factory() as uow:
            assert len(uow.watch_accounts.list_all()) == 1

    def test_empty_url_fails_gracefully(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute("")
        assert result.success is False
        assert "empty" in result.message

    def test_invalid_url_fails(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute("not a url at all")
        assert result.success is False

    def test_duplicate_returns_existing(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        uc.execute("https://www.youtube.com/@YouTube")
        again = uc.execute("https://www.youtube.com/@YouTube")
        assert again.success is False
        assert again.account is not None
        assert "already" in again.message


# ---------------------------------------------------------------------------
# ListWatchedAccountsUseCase
# ---------------------------------------------------------------------------


class TestListWatchedAccountsUseCase:
    def test_empty(self, uow_factory: UnitOfWorkFactory) -> None:
        uc = ListWatchedAccountsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        assert result.total == 0
        assert result.accounts == ()

    def test_lists_added_accounts(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        adder = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        adder.execute("https://www.youtube.com/@YouTube")
        adder.execute("https://www.tiktok.com/@tiktok")

        lister = ListWatchedAccountsUseCase(unit_of_work_factory=uow_factory)
        result = lister.execute()
        assert result.total == 2


# ---------------------------------------------------------------------------
# RemoveWatchedAccountUseCase
# ---------------------------------------------------------------------------


class TestRemoveWatchedAccountUseCase:
    def test_remove_by_handle(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        adder = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        adder.execute("https://www.youtube.com/@YouTube")

        remover = RemoveWatchedAccountUseCase(
            unit_of_work_factory=uow_factory
        )
        result = remover.execute("@YouTube")
        assert result.success is True
        assert result.platform is Platform.YOUTUBE

        with uow_factory() as uow:
            assert uow.watch_accounts.list_all() == []

    def test_remove_with_explicit_platform(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        adder = AddWatchedAccountUseCase(unit_of_work_factory=uow_factory)
        adder.execute("https://www.youtube.com/@YouTube")

        remover = RemoveWatchedAccountUseCase(
            unit_of_work_factory=uow_factory
        )
        result = remover.execute("@YouTube", platform=Platform.YOUTUBE)
        assert result.success is True

    def test_remove_missing_returns_failure(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        remover = RemoveWatchedAccountUseCase(
            unit_of_work_factory=uow_factory
        )
        result = remover.execute("@nope")
        assert result.success is False
        assert "no watched account" in result.message

    def test_remove_ambiguous_handle_requires_platform(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        # Same handle on YouTube + TikTok
        with uow_factory() as uow:
            uow.watch_accounts.add(
                WatchedAccount(
                    platform=Platform.YOUTUBE,
                    handle="@shared",
                    url="https://www.youtube.com/@shared",
                )
            )
            uow.watch_accounts.add(
                WatchedAccount(
                    platform=Platform.TIKTOK,
                    handle="@shared",
                    url="https://www.tiktok.com/@shared",
                )
            )

        remover = RemoveWatchedAccountUseCase(
            unit_of_work_factory=uow_factory
        )
        result = remover.execute("@shared")  # no platform
        assert result.success is False
        assert "specify --platform" in result.message


# ---------------------------------------------------------------------------
# RefreshWatchlistUseCase
# ---------------------------------------------------------------------------


class _FakeDownloader:
    """Stub Downloader returning preset channel entries.

    Only ``list_channel_videos`` is exercised by RefreshWatchlistUseCase.
    """

    def __init__(
        self,
        entries_by_url: dict[str, list[ChannelEntry]] | None = None,
        raise_for: dict[str, Exception] | None = None,
    ) -> None:
        self._entries_by_url = entries_by_url or {}
        self._raise_for = raise_for or {}
        self.calls: list[tuple[str, int]] = []

    def download(self, url: str, destination_dir: str) -> Any:
        raise NotImplementedError

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        self.calls.append((url, limit))
        if url in self._raise_for:
            raise self._raise_for[url]
        return self._entries_by_url.get(url, [])


class _FakeRunner:
    """Stub PipelineRunner returning a configurable success/failure list."""

    def __init__(
        self, results_by_url: dict[str, RunResult] | None = None
    ) -> None:
        self._results_by_url = results_by_url or {}
        self.calls: list[str] = []

    def run(self, ctx: PipelineContext) -> RunResult:
        self.calls.append(ctx.source_url)
        if ctx.source_url in self._results_by_url:
            return self._results_by_url[ctx.source_url]
        # Default: success
        return RunResult(success=True, context=ctx, outcomes=[])


def _seed_account(
    uow_factory: UnitOfWorkFactory,
    *,
    platform: Platform = Platform.YOUTUBE,
    handle: str = "@YouTube",
    url: str = "https://www.youtube.com/@YouTube",
) -> WatchedAccount:
    with uow_factory() as uow:
        return uow.watch_accounts.add(
            WatchedAccount(platform=platform, handle=handle, url=url)
        )


class TestRefreshWatchlistUseCase:
    def test_empty_watchlist(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=_FakeRunner(),  # type: ignore[arg-type]
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            clock=clock,
        )
        summary = uc.execute()
        assert summary.accounts_checked == 0
        assert summary.new_videos_ingested == 0
        assert summary.errors == ()

        with uow_factory() as uow:
            history = uow.watch_refreshes.list_recent()
            assert len(history) == 1

    def test_refresh_ingests_new_videos(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        _seed_account(uow_factory)

        downloader = _FakeDownloader(
            entries_by_url={
                "https://www.youtube.com/@YouTube": [
                    ChannelEntry(
                        platform_id=PlatformId("v1"),
                        url="https://www.youtube.com/watch?v=v1",
                    ),
                    ChannelEntry(
                        platform_id=PlatformId("v2"),
                        url="https://www.youtube.com/watch?v=v2",
                    ),
                ]
            }
        )
        runner = _FakeRunner()

        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=runner,  # type: ignore[arg-type]
            downloader=downloader,  # type: ignore[arg-type]
            clock=clock,
        )
        summary = uc.execute()

        assert summary.accounts_checked == 1
        assert summary.new_videos_ingested == 2
        assert summary.errors == ()
        assert len(runner.calls) == 2
        assert summary.per_account[0].new_videos == 2

    def test_refresh_skips_existing_videos(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        _seed_account(uow_factory)

        # Pre-seed an existing video
        with uow_factory() as uow:
            uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("v1"),
                    url="https://www.youtube.com/watch?v=v1",
                    title="Existing video",
                )
            )

        downloader = _FakeDownloader(
            entries_by_url={
                "https://www.youtube.com/@YouTube": [
                    ChannelEntry(
                        platform_id=PlatformId("v1"),
                        url="https://www.youtube.com/watch?v=v1",
                    ),
                    ChannelEntry(
                        platform_id=PlatformId("v2"),
                        url="https://www.youtube.com/watch?v=v2",
                    ),
                ]
            }
        )
        runner = _FakeRunner()

        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=runner,  # type: ignore[arg-type]
            downloader=downloader,  # type: ignore[arg-type]
            clock=clock,
        )
        summary = uc.execute()

        assert summary.new_videos_ingested == 1  # only v2 is new
        assert len(runner.calls) == 1
        assert runner.calls[0] == "https://www.youtube.com/watch?v=v2"

    def test_refresh_captures_per_account_errors(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        _seed_account(uow_factory, handle="@A", url="https://example.com/A")
        _seed_account(
            uow_factory,
            handle="@B",
            platform=Platform.TIKTOK,
            url="https://example.com/B",
        )

        downloader = _FakeDownloader(
            entries_by_url={
                "https://example.com/A": [
                    ChannelEntry(
                        platform_id=PlatformId("a1"),
                        url="https://www.youtube.com/watch?v=a1",
                    ),
                ],
            },
            raise_for={
                "https://example.com/B": IngestError(
                    "rate limited", retryable=True
                ),
            },
        )
        runner = _FakeRunner()

        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=runner,  # type: ignore[arg-type]
            downloader=downloader,  # type: ignore[arg-type]
            clock=clock,
        )
        summary = uc.execute()

        assert summary.accounts_checked == 2
        assert summary.new_videos_ingested == 1  # @A succeeded
        assert len(summary.errors) == 1
        assert "rate limited" in summary.errors[0]
        assert "@B" in summary.errors[0]
        # First account succeeded, second failed
        assert summary.per_account[0].error is None
        assert summary.per_account[1].error is not None

    def test_refresh_handles_pipeline_failure(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        _seed_account(uow_factory)

        downloader = _FakeDownloader(
            entries_by_url={
                "https://www.youtube.com/@YouTube": [
                    ChannelEntry(
                        platform_id=PlatformId("v1"),
                        url="https://www.youtube.com/watch?v=v1",
                    ),
                ]
            }
        )
        # Pipeline returns failure
        runner = _FakeRunner(
            results_by_url={
                "https://www.youtube.com/watch?v=v1": RunResult(
                    success=False,
                    context=PipelineContext(
                        source_url="https://www.youtube.com/watch?v=v1"
                    ),
                    outcomes=[
                        StageOutcome(
                            stage_name="ingest",
                            status=RunStatus.FAILED,
                            skipped=False,
                            error="boom",
                        )
                    ],
                    failed_at="ingest",
                )
            }
        )

        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=runner,  # type: ignore[arg-type]
            downloader=downloader,  # type: ignore[arg-type]
            clock=clock,
        )
        summary = uc.execute()

        assert summary.new_videos_ingested == 0
        assert len(summary.errors) == 1
        assert "boom" in summary.errors[0]

    def test_refresh_updates_last_checked_at(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        _seed_account(uow_factory)

        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=_FakeRunner(),  # type: ignore[arg-type]
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            clock=clock,
        )
        uc.execute()

        with uow_factory() as uow:
            accounts = uow.watch_accounts.list_all()
            assert accounts[0].last_checked_at is not None

    def test_refresh_persists_watch_refresh_row(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        _seed_account(uow_factory)

        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=_FakeRunner(),  # type: ignore[arg-type]
            downloader=_FakeDownloader(),  # type: ignore[arg-type]
            clock=clock,
        )
        uc.execute()

        with uow_factory() as uow:
            history = uow.watch_refreshes.list_recent()
            assert len(history) == 1
            assert history[0].accounts_checked == 1

    def test_refresh_idempotent(
        self, uow_factory: UnitOfWorkFactory, clock: FrozenClock
    ) -> None:
        _seed_account(uow_factory)

        downloader = _FakeDownloader(
            entries_by_url={
                "https://www.youtube.com/@YouTube": [
                    ChannelEntry(
                        platform_id=PlatformId("v1"),
                        url="https://www.youtube.com/watch?v=v1",
                    ),
                ]
            }
        )

        # Stub runner that actually creates a video row
        class _CreatingRunner:
            def __init__(self) -> None:
                self.calls = 0

            def run(self, ctx: PipelineContext) -> RunResult:
                self.calls += 1
                with uow_factory() as uow:
                    uow.videos.add(
                        Video(
                            platform=Platform.YOUTUBE,
                            platform_id=PlatformId("v1"),
                            url=ctx.source_url,
                            title="t",
                        )
                    )
                return RunResult(success=True, context=ctx, outcomes=[])

        runner = _CreatingRunner()

        uc = RefreshWatchlistUseCase(
            unit_of_work_factory=uow_factory,
            pipeline_runner=runner,  # type: ignore[arg-type]
            downloader=downloader,  # type: ignore[arg-type]
            clock=clock,
        )
        first = uc.execute()
        second = uc.execute()

        assert first.new_videos_ingested == 1
        assert second.new_videos_ingested == 0
        assert runner.calls == 1


# Module-level smoke for unused-import suppression
_ = (datetime, UTC, pytest)
