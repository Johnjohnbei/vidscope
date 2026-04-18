"""Unit tests for vidscope.domain.entities.

Pure-Python assertions on immutable dataclasses. No DB, no filesystem.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from vidscope.domain.entities import (
    Analysis,
    Creator,
    Frame,
    FrameText,
    Hashtag,
    Link,
    Mention,
    PipelineRun,
    Transcript,
    TranscriptSegment,
    Video,
    WatchedAccount,
    WatchRefresh,
)
from vidscope.domain.values import (
    CreatorId,
    Language,
    Platform,
    PlatformId,
    PlatformUserId,
    RunStatus,
    StageName,
    VideoId,
)

UTC_NOW = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)


class TestVideo:
    def test_minimal_video_has_no_media_yet(self) -> None:
        v = Video(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("dQw4w9WgXcQ"),
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        assert v.is_ingested() is False
        assert v.id is None

    def test_video_with_media_key_is_considered_ingested(self) -> None:
        v = Video(
            platform=Platform.TIKTOK,
            platform_id=PlatformId("7123456789"),
            url="https://www.tiktok.com/@user/video/7123456789",
            media_key="videos/1/media.mp4",
            id=VideoId(1),
        )
        assert v.is_ingested() is True

    def test_video_is_frozen(self) -> None:
        v = Video(
            platform=Platform.INSTAGRAM,
            platform_id=PlatformId("Cabcdef"),
            url="https://www.instagram.com/reel/Cabcdef/",
        )
        with pytest.raises(FrozenInstanceError):
            v.url = "mutated"  # type: ignore[misc]


class TestTranscriptSegment:
    def test_duration_is_end_minus_start(self) -> None:
        seg = TranscriptSegment(start=1.25, end=3.75, text="bonjour")
        assert seg.duration() == pytest.approx(2.5)

    def test_duration_clamps_to_zero_on_inverted_times(self) -> None:
        seg = TranscriptSegment(start=5.0, end=2.0, text="oops")
        assert seg.duration() == 0.0


class TestTranscript:
    def test_is_empty_detects_blank_text(self) -> None:
        t = Transcript(
            video_id=VideoId(1), language=Language.FRENCH, full_text="   \n\t"
        )
        assert t.is_empty() is True

    def test_non_empty_transcript_reports_not_empty(self) -> None:
        t = Transcript(
            video_id=VideoId(1),
            language=Language.FRENCH,
            full_text="bonjour tout le monde",
        )
        assert t.is_empty() is False

    def test_segments_default_to_empty_tuple(self) -> None:
        t = Transcript(
            video_id=VideoId(1), language=Language.UNKNOWN, full_text="x"
        )
        assert t.segments == ()


class TestFrame:
    def test_frame_default_is_not_keyframe(self) -> None:
        f = Frame(
            video_id=VideoId(1), image_key="videos/1/frames/00.jpg", timestamp_ms=5000
        )
        assert f.is_keyframe is False

    def test_keyframe_flag_preserved(self) -> None:
        f = Frame(
            video_id=VideoId(1),
            image_key="videos/1/frames/00.jpg",
            timestamp_ms=0,
            is_keyframe=True,
        )
        assert f.is_keyframe is True


class TestAnalysis:
    def test_empty_analysis_has_no_summary(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
        )
        assert a.has_summary() is False

    def test_analysis_with_summary_reports_it(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
            summary="Short summary",
            keywords=("a", "b"),
            topics=("t1",),
            score=80.0,
        )
        assert a.has_summary() is True
        assert a.keywords == ("a", "b")


class TestPipelineRun:
    def test_running_without_finish_has_no_duration(self) -> None:
        r = PipelineRun(
            phase=StageName.INGEST,
            status=RunStatus.RUNNING,
            started_at=UTC_NOW,
        )
        assert r.duration() is None
        assert r.is_terminal() is False

    def test_ok_run_has_positive_duration_and_is_terminal(self) -> None:
        r = PipelineRun(
            phase=StageName.TRANSCRIBE,
            status=RunStatus.OK,
            started_at=UTC_NOW,
            finished_at=UTC_NOW + timedelta(seconds=12.5),
        )
        assert r.is_terminal() is True
        d = r.duration()
        assert d is not None
        assert d.total_seconds() == pytest.approx(12.5)

    def test_failed_run_is_terminal(self) -> None:
        r = PipelineRun(
            phase=StageName.ANALYZE,
            status=RunStatus.FAILED,
            started_at=UTC_NOW,
            finished_at=UTC_NOW,
            error="provider timeout",
        )
        assert r.is_terminal() is True

    def test_skipped_run_is_terminal(self) -> None:
        r = PipelineRun(
            phase=StageName.FRAMES,
            status=RunStatus.SKIPPED,
            started_at=UTC_NOW,
            finished_at=UTC_NOW,
        )
        assert r.is_terminal() is True

    def test_source_url_is_carried_when_video_id_unset(self) -> None:
        r = PipelineRun(
            phase=StageName.INGEST,
            status=RunStatus.PENDING,
            started_at=UTC_NOW,
            source_url="https://www.youtube.com/watch?v=xyz",
        )
        assert r.video_id is None
        assert r.source_url == "https://www.youtube.com/watch?v=xyz"


class TestWatchedAccount:
    def test_minimal_instance(self) -> None:
        acc = WatchedAccount(
            platform=Platform.YOUTUBE,
            handle="@YouTube",
            url="https://www.youtube.com/@YouTube",
        )
        assert acc.id is None
        assert acc.last_checked_at is None

    def test_is_frozen(self) -> None:
        acc = WatchedAccount(
            platform=Platform.TIKTOK,
            handle="@tiktok",
            url="https://www.tiktok.com/@tiktok",
        )
        with pytest.raises(FrozenInstanceError):
            acc.handle = "@other"  # type: ignore[misc]


class TestWatchRefresh:
    def test_running_has_no_duration(self) -> None:
        r = WatchRefresh(
            started_at=UTC_NOW,
            accounts_checked=0,
            new_videos_ingested=0,
        )
        assert r.duration() is None

    def test_completed_has_duration(self) -> None:
        from datetime import timedelta

        r = WatchRefresh(
            started_at=UTC_NOW,
            accounts_checked=2,
            new_videos_ingested=3,
            finished_at=UTC_NOW + timedelta(seconds=5),
        )
        d = r.duration()
        assert d is not None
        assert d.total_seconds() == pytest.approx(5.0)

    def test_errors_default_to_empty_tuple(self) -> None:
        r = WatchRefresh(
            started_at=UTC_NOW,
            accounts_checked=1,
            new_videos_ingested=0,
        )
        assert r.errors == ()


class TestCreator:
    def _minimal(self) -> Creator:
        return Creator(
            platform=Platform.YOUTUBE,
            platform_user_id=PlatformUserId("UC_ABC"),
        )

    def test_minimal_creator_has_defaults(self) -> None:
        c = self._minimal()
        assert c.id is None
        assert c.handle is None
        assert c.display_name is None
        assert c.profile_url is None
        assert c.avatar_url is None
        assert c.follower_count is None
        assert c.is_verified is None
        assert c.is_orphan is False
        assert c.first_seen_at is None
        assert c.last_seen_at is None
        assert c.created_at is None

    def test_creator_is_frozen(self) -> None:
        c = self._minimal()
        with pytest.raises(FrozenInstanceError):
            c.handle = "@new"  # type: ignore[misc]

    def test_creator_uses_slots(self) -> None:
        c = self._minimal()
        assert not hasattr(c, "__dict__")

    def test_creator_equality_by_fields(self) -> None:
        a = Creator(
            platform=Platform.YOUTUBE,
            platform_user_id=PlatformUserId("UC_ABC"),
            handle="@creator",
            display_name="The Creator",
        )
        b = Creator(
            platform=Platform.YOUTUBE,
            platform_user_id=PlatformUserId("UC_ABC"),
            handle="@creator",
            display_name="The Creator",
        )
        assert a == b

    def test_orphan_flag_round_trips(self) -> None:
        c = Creator(
            platform=Platform.INSTAGRAM,
            platform_user_id=PlatformUserId("orphan:legacy_author"),
            is_orphan=True,
        )
        assert c.is_orphan is True

    def test_full_fields_construction(self) -> None:
        now = UTC_NOW
        c = Creator(
            platform=Platform.TIKTOK,
            platform_user_id=PlatformUserId("12345"),
            id=CreatorId(7),
            handle="@test",
            display_name="Test",
            profile_url="https://tiktok.com/@test",
            avatar_url="https://cdn/test.jpg",
            follower_count=100_000,
            is_verified=True,
            is_orphan=False,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
        )
        assert c.id == 7
        assert c.follower_count == 100_000
        assert c.is_verified is True


class TestVideoMetadataColumns:
    """M007 D-01: description, music_track, music_artist on Video."""

    def _minimal(self) -> Video:
        return Video(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://youtube.com/watch?v=abc",
        )

    def test_metadata_defaults_are_none(self) -> None:
        v = self._minimal()
        assert v.description is None
        assert v.music_track is None
        assert v.music_artist is None

    def test_metadata_round_trip(self) -> None:
        v = Video(
            platform=Platform.TIKTOK,
            platform_id=PlatformId("t123"),
            url="https://tiktok.com/@x/video/t123",
            description="#Cooking at home @alice https://shop.com",
            music_track="Original sound",
            music_artist="@creator",
        )
        assert v.description == "#Cooking at home @alice https://shop.com"
        assert v.music_track == "Original sound"
        assert v.music_artist == "@creator"

    def test_description_is_frozen(self) -> None:
        v = self._minimal()
        with pytest.raises(FrozenInstanceError):
            v.description = "mutate"  # type: ignore[misc]


class TestHashtag:
    def _minimal(self) -> Hashtag:
        return Hashtag(video_id=VideoId(1), tag="coding")

    def test_minimal_hashtag_has_defaults(self) -> None:
        h = self._minimal()
        assert h.video_id == VideoId(1)
        assert h.tag == "coding"
        assert h.id is None
        assert h.created_at is None

    def test_hashtag_preserves_caller_value_verbatim(self) -> None:
        # Canonicalisation (lowercase + strip #) is the adapter's job;
        # the dataclass stores what the caller passed.
        h = Hashtag(video_id=VideoId(1), tag="#Coding")
        assert h.tag == "#Coding"

    def test_hashtag_is_frozen(self) -> None:
        h = self._minimal()
        with pytest.raises(FrozenInstanceError):
            h.tag = "other"  # type: ignore[misc]

    def test_hashtag_uses_slots(self) -> None:
        h = self._minimal()
        assert not hasattr(h, "__dict__")

    def test_hashtag_equality_by_fields(self) -> None:
        a = Hashtag(video_id=VideoId(1), tag="coding")
        b = Hashtag(video_id=VideoId(1), tag="coding")
        assert a == b


class TestMention:
    def _minimal(self) -> Mention:
        return Mention(video_id=VideoId(1), handle="alice")

    def test_minimal_mention_has_defaults(self) -> None:
        m = self._minimal()
        assert m.video_id == VideoId(1)
        assert m.handle == "alice"
        assert m.platform is None
        assert m.id is None
        assert m.created_at is None

    def test_mention_accepts_optional_platform(self) -> None:
        m = Mention(
            video_id=VideoId(1),
            handle="alice",
            platform=Platform.TIKTOK,
        )
        assert m.platform is Platform.TIKTOK

    def test_mention_is_frozen(self) -> None:
        m = self._minimal()
        with pytest.raises(FrozenInstanceError):
            m.handle = "other"  # type: ignore[misc]

    def test_mention_uses_slots(self) -> None:
        m = self._minimal()
        assert not hasattr(m, "__dict__")

    def test_mention_equality_by_fields(self) -> None:
        a = Mention(video_id=VideoId(1), handle="alice", platform=Platform.TIKTOK)
        b = Mention(video_id=VideoId(1), handle="alice", platform=Platform.TIKTOK)
        assert a == b


class TestLink:
    def _minimal(self) -> Link:
        return Link(
            video_id=VideoId(1),
            url="https://example.com/path",
            normalized_url="https://example.com/path",
            source="description",
        )

    def test_minimal_link_has_defaults(self) -> None:
        ln = self._minimal()
        assert ln.video_id == VideoId(1)
        assert ln.source == "description"
        assert ln.position_ms is None
        assert ln.id is None
        assert ln.created_at is None

    def test_link_is_frozen(self) -> None:
        ln = self._minimal()
        with pytest.raises(FrozenInstanceError):
            ln.url = "other"  # type: ignore[misc]

    def test_link_uses_slots(self) -> None:
        ln = self._minimal()
        assert not hasattr(ln, "__dict__")

    def test_link_preserves_raw_url_and_normalized_distinctly(self) -> None:
        ln = Link(
            video_id=VideoId(1),
            url="https://Example.COM/Path?utm_source=x",
            normalized_url="https://example.com/Path",
            source="description",
        )
        assert ln.url == "https://Example.COM/Path?utm_source=x"
        assert ln.normalized_url == "https://example.com/Path"

    def test_link_accepts_position_ms(self) -> None:
        ln = Link(
            video_id=VideoId(1),
            url="https://example.com",
            normalized_url="https://example.com",
            source="transcript",
            position_ms=12_345,
        )
        assert ln.position_ms == 12_345


class TestFrameText:
    def _minimal(self) -> FrameText:
        return FrameText(
            video_id=VideoId(1),
            frame_id=5,
            text="Link in bio",
            confidence=0.92,
        )

    def test_construction_with_defaults(self) -> None:
        ft = self._minimal()
        assert ft.video_id == VideoId(1)
        assert ft.frame_id == 5
        assert ft.text == "Link in bio"
        assert ft.confidence == 0.92
        assert ft.bbox is None
        assert ft.id is None
        assert ft.created_at is None

    def test_full_round_trip_including_bbox(self) -> None:
        now = UTC_NOW
        ft = FrameText(
            video_id=VideoId(2),
            frame_id=10,
            text="Promo code: SAVE20",
            confidence=0.88,
            bbox="[[0,0],[100,0],[100,20],[0,20]]",
            id=42,
            created_at=now,
        )
        assert ft.text == "Promo code: SAVE20"
        assert ft.bbox == "[[0,0],[100,0],[100,20],[0,20]]"
        assert ft.id == 42
        assert ft.created_at == now

    def test_is_frozen(self) -> None:
        ft = self._minimal()
        with pytest.raises(FrozenInstanceError):
            ft.text = "mutated"  # type: ignore[misc]

    def test_uses_slots(self) -> None:
        ft = self._minimal()
        assert not hasattr(ft, "__dict__")

    def test_equality_by_fields(self) -> None:
        a = FrameText(video_id=VideoId(1), frame_id=5, text="hello", confidence=0.9)
        b = FrameText(video_id=VideoId(1), frame_id=5, text="hello", confidence=0.9)
        assert a == b

    def test_confidence_accepts_floats_outside_unit_interval(self) -> None:
        # The dataclass does NOT validate the range — that's the adapter's job.
        ft = FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=1.5)
        assert ft.confidence == 1.5
        ft2 = FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=-0.1)
        assert ft2.confidence == -0.1


class TestVideoVisualMetadata:
    """M008/S03: thumbnail_key + content_shape fields on Video (R048, R049)."""

    def _minimal(self) -> Video:
        return Video(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("x"),
            url="u",
        )

    def test_defaults_none(self) -> None:
        v = self._minimal()
        assert v.thumbnail_key is None
        assert v.content_shape is None

    def test_round_trip(self) -> None:
        v = Video(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("x"),
            url="u",
            thumbnail_key="videos/youtube/x/thumb.jpg",
            content_shape="talking_head",
        )
        assert v.thumbnail_key == "videos/youtube/x/thumb.jpg"
        assert v.content_shape == "talking_head"

    def test_is_frozen(self) -> None:
        v = self._minimal()
        with pytest.raises(FrozenInstanceError):
            v.thumbnail_key = "x"  # type: ignore[misc]
