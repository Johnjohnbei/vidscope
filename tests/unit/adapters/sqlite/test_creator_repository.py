"""Tests for CreatorRepositorySQLite (M006/S01)."""

from __future__ import annotations

from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import Creator, CreatorId, Platform, PlatformUserId


def _sample_creator(
    *,
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_ABC",
    handle: str | None = "@creator",
    display_name: str | None = "The Creator",
    follower_count: int | None = 1_000,
    is_orphan: bool = False,
) -> Creator:
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name=display_name,
        profile_url=f"https://youtube.com/{handle}" if handle else None,
        avatar_url="https://yt3.cdn/avatar.jpg",
        follower_count=follower_count,
        is_verified=True,
        is_orphan=is_orphan,
    )


class TestCreatorRepositoryWrites:
    def test_upsert_insert_round_trip(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.creators.upsert(_sample_creator())
            assert stored.id is not None
            assert stored.platform is Platform.YOUTUBE
            assert stored.display_name == "The Creator"
            assert stored.is_orphan is False
            assert stored.created_at is not None
            assert stored.first_seen_at is not None

        with SqliteUnitOfWork(engine) as uow:
            found = uow.creators.find_by_platform_user_id(
                Platform.YOUTUBE, PlatformUserId("UC_ABC")
            )
            assert found is not None
            assert found.display_name == "The Creator"

    def test_upsert_is_idempotent_across_transactions(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            first = uow.creators.upsert(_sample_creator())

        with SqliteUnitOfWork(engine) as uow:
            second = uow.creators.upsert(_sample_creator(display_name="Renamed"))
            assert second.id == first.id  # same surrogate id
            assert second.display_name == "Renamed"

        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 1

    def test_same_platform_user_id_on_different_platforms_ok(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            a = uow.creators.upsert(
                _sample_creator(platform=Platform.YOUTUBE, platform_user_id="shared")
            )
            b = uow.creators.upsert(
                _sample_creator(platform=Platform.TIKTOK, platform_user_id="shared")
            )
            assert a.id != b.id
            assert uow.creators.count() == 2

    def test_upsert_preserves_created_at_on_update(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            initial = uow.creators.upsert(_sample_creator())
            original_created = initial.created_at

        with SqliteUnitOfWork(engine) as uow:
            updated = uow.creators.upsert(_sample_creator(display_name="New"))
            assert updated.created_at == original_created  # preserved

    def test_is_orphan_round_trips(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            orphan = uow.creators.upsert(
                _sample_creator(
                    platform=Platform.INSTAGRAM,
                    platform_user_id="orphan:legacy_author",
                    is_orphan=True,
                )
            )
            assert orphan.is_orphan is True

        with SqliteUnitOfWork(engine) as uow:
            found = uow.creators.find_by_platform_user_id(
                Platform.INSTAGRAM, PlatformUserId("orphan:legacy_author")
            )
            assert found is not None
            assert found.is_orphan is True


class TestCreatorRepositoryReads:
    def test_get_missing_returns_none(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.get(CreatorId(999)) is None

    def test_find_by_handle(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.creators.upsert(
                _sample_creator(platform=Platform.TIKTOK, handle="@tiktoker")
            )
        with SqliteUnitOfWork(engine) as uow:
            found = uow.creators.find_by_handle(Platform.TIKTOK, "@tiktoker")
            assert found is not None
            assert found.handle == "@tiktoker"
            assert (
                uow.creators.find_by_handle(Platform.YOUTUBE, "@tiktoker")
                is None
            )

    def test_list_by_platform(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.creators.upsert(_sample_creator(platform_user_id="a"))
            uow.creators.upsert(_sample_creator(platform_user_id="b"))
            uow.creators.upsert(
                _sample_creator(platform=Platform.TIKTOK, platform_user_id="c")
            )

        with SqliteUnitOfWork(engine) as uow:
            yts = uow.creators.list_by_platform(Platform.YOUTUBE)
            tiks = uow.creators.list_by_platform(Platform.TIKTOK)
            assert len(yts) == 2
            assert len(tiks) == 1

    def test_list_by_min_followers_excludes_nulls(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.creators.upsert(
                _sample_creator(platform_user_id="big", follower_count=100_000)
            )
            uow.creators.upsert(
                _sample_creator(platform_user_id="small", follower_count=100)
            )
            uow.creators.upsert(
                _sample_creator(platform_user_id="null", follower_count=None)
            )

        with SqliteUnitOfWork(engine) as uow:
            top = uow.creators.list_by_min_followers(1_000)
            ids = [c.platform_user_id for c in top]
            assert ids == [PlatformUserId("big")]
            # small (<1000) and null are excluded.

    def test_count(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 0
            uow.creators.upsert(_sample_creator())
            assert uow.creators.count() == 1
