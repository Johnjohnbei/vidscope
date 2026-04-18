"""Tests for ListCreatorVideosUseCase (M006/S03-P01)."""

from __future__ import annotations

from datetime import UTC, datetime

from vidscope.application.list_creator_videos import (
    ListCreatorVideosResult,
    ListCreatorVideosUseCase,
)
from vidscope.domain import Creator, Platform, Video
from vidscope.domain.values import PlatformId, PlatformUserId
from vidscope.ports import UnitOfWorkFactory


def _creator(
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_alice",
) -> Creator:
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _video(
    platform_id: str = "vid1",
    url: str = "https://y/watch?v=vid1",
    platform: Platform = Platform.YOUTUBE,
) -> Video:
    return Video(
        platform=platform,
        platform_id=PlatformId(platform_id),
        url=url,
        title=f"Video {platform_id}",
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
    )


class TestListCreatorVideosFound:
    def test_returns_videos_for_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            creator = uow.creators.upsert(_creator())
            vid = _video()
            uow.videos.upsert_by_platform_id(vid, creator=creator)

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert result.creator is not None
        assert result.creator.handle == "@alice"
        assert len(result.videos) == 1
        assert result.videos[0].platform_id == PlatformId("vid1")

    def test_returns_multiple_videos(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            creator = uow.creators.upsert(_creator())
            for i in range(3):
                uow.videos.upsert_by_platform_id(
                    _video(platform_id=f"v{i}", url=f"https://y/v{i}"),
                    creator=creator,
                )

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert len(result.videos) == 3
        assert result.total == 3

    def test_total_reflects_all_videos(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            creator = uow.creators.upsert(_creator())
            for i in range(5):
                uow.videos.upsert_by_platform_id(
                    _video(platform_id=f"v{i}", url=f"https://y/v{i}"),
                    creator=creator,
                )

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice", limit=2)

        assert len(result.videos) == 2  # page capped
        assert result.total == 5       # total unbounded


class TestListCreatorVideosNotFound:
    def test_not_found_when_creator_absent(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@ghost")

        assert result.found is False
        assert result.creator is None
        assert result.videos == ()
        assert result.total == 0

    def test_empty_videos_for_existing_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator(handle="@lonely"))

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@lonely")

        assert result.found is True
        assert result.videos == ()
        assert result.total == 0

    def test_excludes_videos_from_other_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            alice = uow.creators.upsert(_creator("@alice", platform_user_id="alice"))
            bob = uow.creators.upsert(_creator("@bob", platform_user_id="bob"))
            uow.videos.upsert_by_platform_id(_video("v1", "https://y/v1"), creator=alice)
            uow.videos.upsert_by_platform_id(_video("v2", "https://y/v2"), creator=bob)

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert len(result.videos) == 1
        assert result.videos[0].platform_id == PlatformId("v1")
