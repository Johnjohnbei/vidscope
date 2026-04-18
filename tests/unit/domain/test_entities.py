"""Unit tests for vidscope.domain.entities.

Pure-Python assertions on immutable dataclasses. No DB, no filesystem.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from vidscope.domain.entities import (
    Analysis,
    Frame,
    PipelineRun,
    Transcript,
    TranscriptSegment,
    Video,
    VideoStats,
    WatchedAccount,
    WatchRefresh,
)
from vidscope.domain.values import (
    Language,
    Platform,
    PlatformId,
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


class TestVideoStats:
    """Tests for the VideoStats frozen dataclass (M009-S01)."""

    def test_is_frozen(self) -> None:
        """Test 1: VideoStats is frozen — mutation raises FrozenInstanceError."""
        stats = VideoStats(
            video_id=VideoId(1),
            captured_at=UTC_NOW,
        )
        with pytest.raises(FrozenInstanceError):
            stats.view_count = 42  # type: ignore[misc]

    def test_all_counters_default_to_none(self) -> None:
        """Test 2: all 5 counters default to None when not provided."""
        stats = VideoStats(
            video_id=VideoId(1),
            captured_at=UTC_NOW,
        )
        assert stats.view_count is None
        assert stats.like_count is None
        assert stats.repost_count is None
        assert stats.comment_count is None
        assert stats.save_count is None
        assert stats.id is None
        assert stats.created_at is None

    def test_zero_is_distinct_from_none(self) -> None:
        """Test 3: view_count=0 must NOT compare equal to None (D-03)."""
        stats = VideoStats(
            video_id=VideoId(1),
            captured_at=UTC_NOW,
            view_count=0,
        )
        assert stats.view_count is not None
        assert stats.view_count == 0

    def test_counters_populated(self) -> None:
        """All 5 counters can be set and retrieved."""
        stats = VideoStats(
            video_id=VideoId(42),
            captured_at=UTC_NOW,
            view_count=1000,
            like_count=50,
            repost_count=10,
            comment_count=25,
            save_count=5,
        )
        assert stats.view_count == 1000
        assert stats.like_count == 50
        assert stats.repost_count == 10
        assert stats.comment_count == 25
        assert stats.save_count == 5

    def test_partial_counters_preserve_none(self) -> None:
        """Unset counters stay None even when others are provided (D-03)."""
        stats = VideoStats(
            video_id=VideoId(1),
            captured_at=UTC_NOW,
            view_count=500,
            like_count=None,
        )
        assert stats.view_count == 500
        assert stats.like_count is None
        assert stats.repost_count is None


class TestAnalysisM010Extension:
    def test_construct_with_all_defaults(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
        )
        assert a.verticals == ()
        assert a.information_density is None
        assert a.actionability is None
        assert a.novelty is None
        assert a.production_quality is None
        assert a.sentiment is None
        assert a.is_sponsored is None
        assert a.content_type is None
        assert a.reasoning is None

    def test_construct_with_all_m010_fields(self) -> None:
        from vidscope.domain import ContentType, SentimentLabel

        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
            verticals=("tech", "ai"),
            information_density=72.5,
            actionability=80.0,
            novelty=40.0,
            production_quality=65.0,
            sentiment=SentimentLabel.POSITIVE,
            is_sponsored=False,
            content_type=ContentType.TUTORIAL,
            reasoning="Clear step-by-step tutorial with concrete examples.",
        )
        assert a.verticals == ("tech", "ai")
        assert a.information_density == 72.5
        assert a.sentiment is SentimentLabel.POSITIVE
        assert a.content_type is ContentType.TUTORIAL
        assert a.is_sponsored is False  # explicitly False != None
        assert "step-by-step" in (a.reasoning or "")

    def test_frozen_prevents_mutation(self) -> None:
        import dataclasses

        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.reasoning = "nope"  # type: ignore[misc]

    def test_slots_prevents_new_attributes(self) -> None:
        import dataclasses

        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
        )
        # slots=True prevents __dict__; frozen=True also blocks attribute
        # mutation. Depending on Python version the raised exception type
        # may be AttributeError, FrozenInstanceError, or TypeError.
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError, TypeError)):
            a.bogus_field = "x"  # type: ignore[attr-defined]

    def test_has_summary_still_works(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
            summary="something",
        )
        assert a.has_summary() is True

    def test_is_sponsored_none_vs_false_distinct(self) -> None:
        unknown = Analysis(
            video_id=VideoId(1), provider="heuristic", language=Language.ENGLISH,
        )
        explicit_false = Analysis(
            video_id=VideoId(1), provider="heuristic",
            language=Language.ENGLISH, is_sponsored=False,
        )
        assert unknown.is_sponsored is None
        assert explicit_false.is_sponsored is False
        assert unknown.is_sponsored != explicit_false.is_sponsored


class TestContentTypeEnum:
    def test_contains_expected_members(self) -> None:
        from vidscope.domain import ContentType

        expected_values = {
            "tutorial", "review", "vlog", "news", "story",
            "opinion", "comedy", "educational", "promo", "unknown",
        }
        assert expected_values.issubset({c.value for c in ContentType})

    def test_is_strenum_serialises_to_str(self) -> None:
        from vidscope.domain import ContentType

        assert str(ContentType.TUTORIAL) == "tutorial"
        assert ContentType.TUTORIAL == "tutorial"

    def test_construction_from_string(self) -> None:
        from vidscope.domain import ContentType

        assert ContentType("tutorial") is ContentType.TUTORIAL


class TestSentimentLabelEnum:
    def test_contains_exactly_four_labels(self) -> None:
        from vidscope.domain import SentimentLabel

        assert {s.value for s in SentimentLabel} == {
            "positive", "negative", "neutral", "mixed",
        }

    def test_invalid_label_raises(self) -> None:
        from vidscope.domain import SentimentLabel

        with pytest.raises(ValueError):
            SentimentLabel("joyful")


class TestPyyamlAvailable:
    """Ensure pyyaml is a direct dependency (not just transitive)."""

    def test_yaml_importable(self) -> None:
        import yaml  # noqa: PLC0415
        assert hasattr(yaml, "safe_load")
