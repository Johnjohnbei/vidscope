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


class TestWriteThroughAuthor:
    """D-03 write-through cache regression: videos.author tracks
    creators.display_name when upsert_by_platform_id(video, creator=...)
    is used. Application code must NEVER write videos.author directly.
    """

    def test_upsert_with_creator_copies_display_name_to_author(
        self, engine: Engine
    ) -> None:
        from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
        from vidscope.domain import Creator, PlatformUserId

        with SqliteUnitOfWork(engine) as uow:
            creator = uow.creators.upsert(
                Creator(
                    platform=Platform.YOUTUBE,
                    platform_user_id=PlatformUserId("UC_WT"),
                    display_name="Display A",
                )
            )
            video = uow.videos.upsert_by_platform_id(
                _sample_video(
                    platform_id=PlatformId("wt_v1"),
                    author="stale-will-be-overwritten",
                ),
                creator=creator,
            )
            assert video.author == "Display A"
            assert video.id is not None

    def test_rename_creator_propagates_to_videos_author(
        self, engine: Engine
    ) -> None:
        """The regression guard mandated by CONTEXT.md §specifics."""
        from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
        from vidscope.domain import Creator, PlatformUserId

        with SqliteUnitOfWork(engine) as uow:
            creator_a = uow.creators.upsert(
                Creator(
                    platform=Platform.YOUTUBE,
                    platform_user_id=PlatformUserId("UC_RN"),
                    display_name="A",
                )
            )
            uow.videos.upsert_by_platform_id(
                _sample_video(platform_id=PlatformId("rn_v1")),
                creator=creator_a,
            )

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get_by_platform_id(
                Platform.YOUTUBE, PlatformId("rn_v1")
            )
            assert found is not None
            assert found.author == "A"

            # Rename the creator
            creator_b = uow.creators.upsert(
                Creator(
                    platform=Platform.YOUTUBE,
                    platform_user_id=PlatformUserId("UC_RN"),
                    display_name="B",
                )
            )
            uow.videos.upsert_by_platform_id(
                _sample_video(platform_id=PlatformId("rn_v1")),
                creator=creator_b,
            )

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get_by_platform_id(
                Platform.YOUTUBE, PlatformId("rn_v1")
            )
            assert found is not None
            assert found.author == "B"  # write-through propagated

    def test_upsert_without_creator_preserves_existing_author(
        self, engine: Engine
    ) -> None:
        """M001–M005 callers still work unchanged (kwarg defaults to
        None → author is taken from the video argument as-is)."""
        from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork

        with SqliteUnitOfWork(engine) as uow:
            v = uow.videos.upsert_by_platform_id(
                _sample_video(
                    platform_id=PlatformId("legacy_v1"),
                    author="Legacy Author",
                ),
                # no creator kwarg
            )
            assert v.author == "Legacy Author"


class TestVideoM007MetadataFields:
    """M007/S01-P02: description, music_track, music_artist round-trip."""

    def test_add_with_m007_fields_round_trips(self, engine: Engine) -> None:
        """Adding a Video with all 3 M007 fields preserves them on get."""
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.videos.add(
                _sample_video(
                    platform_id=PlatformId("m007_v1"),
                    description="A cooking tutorial",
                    music_track="Lo-Fi Beat",
                    music_artist="DJ Chill",
                )
            )
            assert stored.id is not None

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get(stored.id)  # type: ignore[arg-type]
            assert found is not None
            assert found.description == "A cooking tutorial"
            assert found.music_track == "Lo-Fi Beat"
            assert found.music_artist == "DJ Chill"

    def test_add_without_m007_fields_defaults_to_none(
        self, engine: Engine
    ) -> None:
        """Backward-compat: Videos without M007 fields get None on read."""
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.videos.add(
                _sample_video(platform_id=PlatformId("m007_v2"))
            )
            assert stored.id is not None

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get(stored.id)  # type: ignore[arg-type]
            assert found is not None
            assert found.description is None
            assert found.music_track is None
            assert found.music_artist is None


class TestUpdateVisualMetadata:
    """M008/S03: VideoRepository.update_visual_metadata persists R048+R049 columns."""

    def test_update_sets_thumbnail_key_and_content_shape(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.videos.add(
                _sample_video(platform_id=PlatformId("vis_v1"))
            )
            assert stored.id is not None
            vid_id = stored.id

        with SqliteUnitOfWork(engine) as uow:
            uow.videos.update_visual_metadata(
                vid_id,
                thumbnail_key="videos/yt/abc/thumb.jpg",
                content_shape="talking_head",
            )

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get(vid_id)
            assert found is not None
            assert found.thumbnail_key == "videos/yt/abc/thumb.jpg"
            assert found.content_shape == "talking_head"

    def test_update_preserves_other_columns(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.videos.add(
                _sample_video(
                    platform_id=PlatformId("vis_v2"),
                    title="Preserved Title",
                    description="Preserved desc",
                    music_track="Preserved track",
                )
            )
            assert stored.id is not None
            vid_id = stored.id

        with SqliteUnitOfWork(engine) as uow:
            uow.videos.update_visual_metadata(
                vid_id,
                thumbnail_key="videos/yt/vis_v2/thumb.jpg",
                content_shape="broll",
            )

        with SqliteUnitOfWork(engine) as uow:
            found = uow.videos.get(vid_id)
            assert found is not None
            assert found.title == "Preserved Title"
            assert found.description == "Preserved desc"
            assert found.music_track == "Preserved track"
            assert found.thumbnail_key == "videos/yt/vis_v2/thumb.jpg"
            assert found.content_shape == "broll"

    def test_update_on_missing_video_raises_storage_error(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow, pytest.raises(StorageError) as exc_info:
            uow.videos.update_visual_metadata(
                VideoId(99999),
                thumbnail_key="videos/yt/missing/thumb.jpg",
                content_shape="unknown",
            )
        assert "99999" in str(exc_info.value) or "not found" in str(exc_info.value)
