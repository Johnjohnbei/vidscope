"""Tests for ListCreatorsUseCase (M006/S03-P01)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vidscope.application.list_creators import ListCreatorsResult, ListCreatorsUseCase
from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.ports import UnitOfWorkFactory


def _creator(
    handle: str,
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str | None = None,
    follower_count: int | None = None,
) -> Creator:
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id or f"uid_{handle}"),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        follower_count=follower_count,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestListCreatorsNoFilter:
    def test_empty_db_returns_empty(self, uow_factory: UnitOfWorkFactory) -> None:
        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        assert result.creators == ()
        assert result.total == 0

    def test_returns_inserted_creators(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@alice"))
            uow.creators.upsert(_creator("@bob"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        handles = {c.handle for c in result.creators}
        assert "@alice" in handles
        assert "@bob" in handles

    def test_total_reflects_all_creators(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            for i in range(5):
                uow.creators.upsert(_creator(f"@user{i}", platform_user_id=f"uid{i}"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        assert result.total == 5

    def test_result_is_frozen_tuple(self, uow_factory: UnitOfWorkFactory) -> None:
        import dataclasses as _dc
        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        assert isinstance(result.creators, tuple)
        result2 = ListCreatorsResult(creators=(), total=0)
        with pytest.raises(_dc.FrozenInstanceError):
            result2.total = 99  # type: ignore[misc]


class TestListCreatorsByPlatform:
    def test_platform_filter_excludes_other_platforms(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@yt1", platform=Platform.YOUTUBE, platform_user_id="yt1"))
            uow.creators.upsert(_creator("@tt1", platform=Platform.TIKTOK, platform_user_id="tt1"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(platform=Platform.YOUTUBE)
        handles = {c.handle for c in result.creators}
        assert "@yt1" in handles
        assert "@tt1" not in handles


class TestListCreatorsByMinFollowers:
    def test_min_followers_filter(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@big", follower_count=100000, platform_user_id="big"))
            uow.creators.upsert(_creator("@small", follower_count=500, platform_user_id="small"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(min_followers=10000)
        handles = {c.handle for c in result.creators}
        assert "@big" in handles
        assert "@small" not in handles

    def test_null_follower_count_excluded(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@unknown", follower_count=None, platform_user_id="unk"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(min_followers=1)
        handles = {c.handle for c in result.creators}
        assert "@unknown" not in handles


class TestListCreatorsDualFilter:
    def test_platform_and_min_followers(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@yt_big", platform=Platform.YOUTUBE, follower_count=50000, platform_user_id="ytbig"))
            uow.creators.upsert(_creator("@yt_small", platform=Platform.YOUTUBE, follower_count=100, platform_user_id="ytsmall"))
            uow.creators.upsert(_creator("@tt_big", platform=Platform.TIKTOK, follower_count=50000, platform_user_id="ttbig"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(platform=Platform.YOUTUBE, min_followers=10000)
        handles = {c.handle for c in result.creators}
        assert "@yt_big" in handles
        assert "@yt_small" not in handles
        assert "@tt_big" not in handles
