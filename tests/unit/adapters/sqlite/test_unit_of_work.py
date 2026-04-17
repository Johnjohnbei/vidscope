"""Tests for :class:`SqliteUnitOfWork` transaction semantics."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import Platform, PlatformId, Video
from vidscope.domain.errors import StorageError
from vidscope.ports import UnitOfWork


class TestSqliteUnitOfWork:
    def test_conforms_to_unit_of_work_protocol(self, engine: Engine) -> None:
        uow = SqliteUnitOfWork(engine)
        with uow:
            assert isinstance(uow, UnitOfWork)

    def test_commit_persists_writes_after_clean_exit(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("commit1"),
                    url="https://example.com/commit1",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.count() == 1
            row = uow.videos.get_by_platform_id(
                Platform.YOUTUBE, PlatformId("commit1")
            )
            assert row is not None

    def test_rollback_on_exception_discards_writes(
        self, engine: Engine
    ) -> None:
        class BoomError(RuntimeError):
            pass

        with pytest.raises(BoomError), SqliteUnitOfWork(engine) as uow:
            uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("rollback1"),
                    url="https://example.com/rollback1",
                )
            )
            raise BoomError("fail after insert")

        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.count() == 0
            assert (
                uow.videos.get_by_platform_id(
                    Platform.YOUTUBE, PlatformId("rollback1")
                )
                is None
            )

    def test_uow_is_not_reentrant(self, engine: Engine) -> None:
        uow = SqliteUnitOfWork(engine)
        with uow, pytest.raises(StorageError), uow:  # Nested enter on the same instance
            pass

    def test_fresh_uow_per_block(self, engine: Engine) -> None:
        """Each `with` block should open a brand new connection.
        Reusing the same UoW across blocks means fresh state each time.
        """
        uow1 = SqliteUnitOfWork(engine)
        with uow1:
            uow1.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("fresh1"),
                    url="https://example.com/fresh1",
                )
            )

        uow2 = SqliteUnitOfWork(engine)
        with uow2:
            assert uow2.videos.count() == 1

    def test_multiple_writes_in_one_transaction_are_atomic(
        self, engine: Engine
    ) -> None:
        class BoomError(RuntimeError):
            pass

        with pytest.raises(BoomError), SqliteUnitOfWork(engine) as uow:
            uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("atom1"),
                    url="https://example.com/atom1",
                )
            )
            uow.videos.add(
                Video(
                    platform=Platform.TIKTOK,
                    platform_id=PlatformId("atom2"),
                    url="https://example.com/atom2",
                )
            )
            # First two writes succeeded; now boom. Both must roll back.
            raise BoomError("after two writes")

        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.count() == 0


class TestCreatorInTransaction:
    """UoW exposes creators and shares the transaction with videos.

    This is the structural contract that makes the D-03 write-through
    safe: both repos use the same Connection, so a creator upsert +
    video upsert commit or roll back together.
    """

    def test_uow_exposes_creator_repository(self, engine: Engine) -> None:
        from vidscope.ports import CreatorRepository

        with SqliteUnitOfWork(engine) as uow:
            assert isinstance(uow.creators, CreatorRepository)

    def test_creator_and_video_share_transaction_rollback(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import Creator, PlatformUserId

        class BoomError(RuntimeError):
            pass

        with pytest.raises(BoomError), SqliteUnitOfWork(engine) as uow:
            uow.creators.upsert(
                Creator(
                    platform=Platform.YOUTUBE,
                    platform_user_id=PlatformUserId("UC_ROLL"),
                    display_name="Rolled",
                )
            )
            uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("roll_v1"),
                    url="https://x/roll",
                )
            )
            raise BoomError("abort after both writes")

        # Neither row persisted.
        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 0
            assert uow.videos.count() == 0

    def test_creator_and_video_share_transaction_commit(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import Creator, PlatformUserId

        with SqliteUnitOfWork(engine) as uow:
            uow.creators.upsert(
                Creator(
                    platform=Platform.YOUTUBE,
                    platform_user_id=PlatformUserId("UC_OK"),
                    display_name="Ok",
                )
            )
            uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("ok_v1"),
                    url="https://x/ok",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 1
            assert uow.videos.count() == 1
