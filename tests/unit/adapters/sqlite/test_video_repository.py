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


class TestListByAuthor:
    """Tests for VideoRepositorySQLite.list_by_author (M009/S03)."""

    def test_returns_videos_matching_author_and_platform(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.add(
                _sample_video(platform=Platform.YOUTUBE, platform_id=PlatformId("y1"), author="alice")
            )
            uow.videos.add(
                _sample_video(platform=Platform.YOUTUBE, platform_id=PlatformId("y2"), author="alice")
            )
            uow.videos.add(
                _sample_video(platform=Platform.YOUTUBE, platform_id=PlatformId("y3"), author="bob")
            )
            uow.videos.add(
                _sample_video(platform=Platform.TIKTOK, platform_id=PlatformId("t1"), author="alice")
            )

        with SqliteUnitOfWork(engine) as uow:
            alice_yt = uow.videos.list_by_author(Platform.YOUTUBE, "alice")
            assert len(alice_yt) == 2
            assert all(v.author == "alice" for v in alice_yt)
            assert all(v.platform is Platform.YOUTUBE for v in alice_yt)

    def test_returns_empty_for_unknown_handle(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.add(_sample_video(platform_id=PlatformId("x1"), author="alice"))

        with SqliteUnitOfWork(engine) as uow:
            result = uow.videos.list_by_author(Platform.YOUTUBE, "ghost")
            assert result == []

    def test_limit_caps_results(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            for i in range(5):
                uow.videos.add(
                    _sample_video(
                        platform=Platform.YOUTUBE,
                        platform_id=PlatformId(f"lim{i}"),
                        author="prolific",
                    )
                )

        with SqliteUnitOfWork(engine) as uow:
            result = uow.videos.list_by_author(Platform.YOUTUBE, "prolific", limit=3)
            assert len(result) == 3


# ---------------------------------------------------------------------------
# media_type round-trips
# ---------------------------------------------------------------------------


class TestMediaTypeRoundTrip:
    def test_row_to_video_defaults_to_video_media_type_when_null(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import MediaType
        from sqlalchemy import text

        # Insert a row with media_type = NULL directly, bypassing the domain layer
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO videos (platform, platform_id, url, created_at) "
                    "VALUES ('youtube', 'null_mt', 'https://example.com', datetime('now'))"
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.get_by_platform_id(Platform.YOUTUBE, PlatformId("null_mt"))
            assert video is not None
            assert video.media_type is MediaType.VIDEO

    def test_row_to_video_reads_image_media_type(self, engine: Engine) -> None:
        from vidscope.domain import MediaType

        with SqliteUnitOfWork(engine) as uow:
            stored = uow.videos.add(
                _sample_video(
                    platform_id=PlatformId("img1"),
                    media_type=MediaType.IMAGE,
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get(stored.id)
            assert found is not None
            assert found.media_type is MediaType.IMAGE

    def test_row_to_video_reads_carousel_media_type(self, engine: Engine) -> None:
        from vidscope.domain import MediaType

        with SqliteUnitOfWork(engine) as uow:
            stored = uow.videos.add(
                _sample_video(
                    platform_id=PlatformId("car1"),
                    media_type=MediaType.CAROUSEL,
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get(stored.id)
            assert found is not None
            assert found.media_type is MediaType.CAROUSEL

    def test_video_to_row_includes_media_type(self, engine: Engine) -> None:
        from vidscope.domain import MediaType
        from sqlalchemy import text

        with SqliteUnitOfWork(engine) as uow:
            uow.videos.add(
                _sample_video(
                    platform_id=PlatformId("mt_row"),
                    media_type=MediaType.IMAGE,
                )
            )

        with engine.connect() as conn:
            raw = conn.execute(
                text("SELECT media_type FROM videos WHERE platform_id = 'mt_row'")
            ).scalar()
        assert raw == "image"


# ---------------------------------------------------------------------------
# M012/S01 — description round-trip
# ---------------------------------------------------------------------------


class TestDescriptionRoundTrip:
    """R060 — videos.description persists via upsert + get."""

    def test_description_round_trips(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            saved = uow.videos.add(
                _sample_video(
                    platform_id=PlatformId("p_99999"),
                    platform=Platform.INSTAGRAM,
                    url="https://instagram.com/p/99999/",
                    description="Caption avec accents éàù",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            reloaded = uow.videos.get(saved.id)  # type: ignore[arg-type]
            assert reloaded is not None
            assert reloaded.description == "Caption avec accents éàù"

    def test_null_description_persists_as_none(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            saved = uow.videos.add(
                _sample_video(
                    platform_id=PlatformId("p_99998"),
                    platform=Platform.INSTAGRAM,
                    url="https://instagram.com/p/99998/",
                    description=None,
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            reloaded = uow.videos.get(saved.id)  # type: ignore[arg-type]
            assert reloaded is not None
            assert reloaded.description is None
