"""Pipeline neutrality regression guard (M011/S01/R056).

Re-ingesting a video via VideoRepository.upsert_by_platform_id must NOT
touch the associated video_tracking row. This is the invariant that
keeps user annotations safe across re-ingests.
"""

from __future__ import annotations

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Platform,
    PlatformId,
    TrackingStatus,
    Video,
    VideoId,
    VideoTracking,
)


class TestPipelineNeutrality:
    def test_reingest_preserves_tracking(self, engine: Engine) -> None:
        # Step 1: ingest video.
        with SqliteUnitOfWork(engine) as uow:
            v = uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("neutral1"),
                    url="https://y.be/neutral1",
                    title="Original title",
                )
            )
            assert v.id is not None
            video_id = v.id

        # Step 2: user sets tracking.
        with SqliteUnitOfWork(engine) as uow:
            uow.video_tracking.upsert(
                VideoTracking(
                    video_id=VideoId(int(video_id)),
                    status=TrackingStatus.SAVED,
                    starred=True,
                    notes="important",
                )
            )

        # Step 3: re-ingest the SAME URL with different metadata.
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("neutral1"),
                    url="https://y.be/neutral1",
                    title="Updated title",
                    view_count=12345,
                )
            )

        # Step 4: assert tracking row is INTACT.
        with SqliteUnitOfWork(engine) as uow:
            tracking = uow.video_tracking.get_for_video(VideoId(int(video_id)))
        assert tracking is not None
        assert tracking.status is TrackingStatus.SAVED
        assert tracking.starred is True
        assert tracking.notes == "important"

    def test_tracking_has_exactly_one_row_per_video(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            v = uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("neutral2"),
                    url="https://y.be/neutral2",
                )
            )
            assert v.id is not None
            vid = int(v.id)

        with SqliteUnitOfWork(engine) as uow:
            uow.video_tracking.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.NEW))
            uow.video_tracking.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.REVIEWED))
            uow.video_tracking.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.SAVED))

        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM video_tracking WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert count == 1
