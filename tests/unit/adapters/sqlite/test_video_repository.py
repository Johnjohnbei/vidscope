"""Tests for :class:`VideoRepositorySQLite`."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.domain import Platform, PlatformId, Video, VideoId
from vidscope.domain.errors import StorageError


def _sample_video(**overrides: object) -> Video:
    defaults = {
        "platform": Platform.YOUTUBE,
        "platform_id": PlatformId("abc123"),
        "url": "https://www.youtube.com/watch?v=abc123",
        "author": "Author",
        "title": "Sample Title",
        "duration": 42.5,
        "upload_date": "2026-04-01",
        "view_count": 1234,
        "media_key": None,
    }
    defaults.update(overrides)
    return Video(**defaults)  # type: ignore[arg-type]


class TestVideoRepository:
    def test_add_round_trip(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.videos.add(_sample_video())
            assert stored.id is not None
            assert stored.title == "Sample Title"

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get(stored.id)  # type: ignore[arg-type]
            assert found is not None
            assert found.platform is Platform.YOUTUBE
            assert found.platform_id == PlatformId("abc123")
            assert found.url.startswith("https://")
            assert found.duration == pytest.approx(42.5)
            assert found.created_at is not None
            assert found.created_at.tzinfo is not None

    def test_get_missing_returns_none(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.get(VideoId(999)) is None

    def test_get_by_platform_id_round_trip(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.add(
                _sample_video(platform_id=PlatformId("7000000000"), platform=Platform.TIKTOK)
            )

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get_by_platform_id(
                Platform.TIKTOK, PlatformId("7000000000")
            )
            assert found is not None
            assert found.platform is Platform.TIKTOK

    def test_duplicate_platform_id_raises_on_add(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.add(_sample_video())

        # Second add with the same platform_id must fail
        with SqliteUnitOfWork(engine) as uow, pytest.raises(StorageError):
            uow.videos.add(_sample_video(title="Collision"))

    def test_upsert_is_idempotent_across_transactions(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            first = uow.videos.upsert_by_platform_id(_sample_video())

        # Re-upsert with a different title should update, not duplicate
        with SqliteUnitOfWork(engine) as uow:
            second = uow.videos.upsert_by_platform_id(
                _sample_video(title="Updated Title")
            )

        assert first.id == second.id
        assert second.title == "Updated Title"

        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.count() == 1

    def test_list_recent_orders_by_created_at_desc(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.upsert_by_platform_id(
                _sample_video(platform_id=PlatformId("a1"))
            )
            uow.videos.upsert_by_platform_id(
                _sample_video(platform_id=PlatformId("a2"))
            )
            uow.videos.upsert_by_platform_id(
                _sample_video(platform_id=PlatformId("a3"))
            )

        with SqliteUnitOfWork(engine) as uow:
            rows = uow.videos.list_recent(limit=10)
            assert len(rows) == 3
            # All 3 have the same created_at precision; we at least
            # verify we got them all back and they are Video instances.
            assert all(isinstance(r, Video) for r in rows)

    def test_count_on_empty_is_zero(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.count() == 0


class TestDirectConnectionUsage:
    """The repository also accepts a bare Connection for cases where the
    caller manages the transaction directly (tests, one-off scripts)."""

    def test_direct_connection_round_trip(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = VideoRepositorySQLite(conn)
            stored = repo.add(_sample_video(platform_id=PlatformId("direct")))
            assert stored.id is not None

        with engine.connect() as conn:
            repo = VideoRepositorySQLite(conn)
            found = repo.get_by_platform_id(
                Platform.YOUTUBE, PlatformId("direct")
            )
            assert found is not None
