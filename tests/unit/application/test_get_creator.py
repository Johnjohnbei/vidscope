"""Tests for GetCreatorUseCase (M006/S03-P01)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from vidscope.application.get_creator import GetCreatorResult, GetCreatorUseCase
from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.ports import UnitOfWorkFactory


def _make_creator(
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_abc",
) -> Creator:
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name="Alice",
        follower_count=1000,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestGetCreatorUseCaseFound:
    def test_returns_found_true_when_creator_exists(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        creator = _make_creator()
        with uow_factory() as uow:
            uow.creators.upsert(creator)

        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert result.creator is not None
        assert result.creator.handle == "@alice"
        assert result.creator.display_name == "Alice"

    def test_returns_creator_with_follower_count(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        creator = _make_creator(handle="@bob", platform_user_id="UC_bob")
        creator = dataclasses.replace(creator, follower_count=42000)
        with uow_factory() as uow:
            uow.creators.upsert(creator)

        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@bob")

        assert result.found is True
        assert result.creator is not None
        assert result.creator.follower_count == 42000

    def test_result_is_frozen(self, uow_factory: UnitOfWorkFactory) -> None:
        import dataclasses as _dc
        result = GetCreatorResult(found=False)
        with pytest.raises(_dc.FrozenInstanceError):
            result.found = True  # type: ignore[misc]


class TestGetCreatorUseCaseNotFound:
    def test_returns_found_false_when_no_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@nobody")

        assert result.found is False
        assert result.creator is None

    def test_returns_found_false_for_wrong_platform(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        creator = _make_creator(handle="@charlie", platform=Platform.YOUTUBE)
        with uow_factory() as uow:
            uow.creators.upsert(creator)

        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        # Same handle but on TikTok — different creator
        result = uc.execute(Platform.TIKTOK, "@charlie")
        assert result.found is False

    def test_not_found_does_not_raise(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        # Must return, not raise
        result = uc.execute(Platform.YOUTUBE, "@ghost")
        assert not result.found
