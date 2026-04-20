"""Unit tests for the IngestOutcome M007 extension.

IngestOutcome gains 5 optional fields in M007/S03-P01 (T01) so the
ingest pipeline can carry rich content metadata (description, hashtags,
mentions, music) through to persistence. Tests assert:
  (a) new fields default to safe values, preserving backward compat
  (b) every field round-trips through construction
  (c) the dataclass stays frozen
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vidscope.domain import Mention, Platform, PlatformId, VideoId
from vidscope.ports import IngestOutcome


class TestIngestOutcomeDefaults:
    def test_minimal_construction_backward_compat(self) -> None:
        """M006 callers can still construct IngestOutcome with only the 4
        required fields — all new M007 fields must have safe defaults."""
        o = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("x"),
            url="u",
            media_path="p",
        )
        assert o.platform is Platform.YOUTUBE
        assert o.platform_id == PlatformId("x")
        assert o.url == "u"
        assert o.media_path == "p"

    def test_new_fields_default_to_none_or_empty(self) -> None:
        """Each new M007 field must have its documented default value."""
        o = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("x"),
            url="u",
            media_path="p",
        )
        assert o.description is None
        assert o.hashtags == ()
        assert o.mentions == ()
        assert o.music_track is None
        assert o.music_artist is None

    def test_full_construction_with_all_new_fields(self) -> None:
        """All 5 new fields round-trip correctly when supplied."""
        mention = Mention(video_id=VideoId(0), handle="alice", platform=None)
        o = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("x"),
            url="u",
            media_path="p",
            description="A description #cooking @alice",
            hashtags=("cooking", "recipe"),
            mentions=(mention,),
            music_track="Original sound",
            music_artist="CreatorXYZ",
        )
        assert o.description == "A description #cooking @alice"
        assert o.hashtags == ("cooking", "recipe")
        assert len(o.mentions) == 1
        assert o.mentions[0].handle == "alice"
        assert o.music_track == "Original sound"
        assert o.music_artist == "CreatorXYZ"

    def test_ingest_outcome_is_frozen(self) -> None:
        """IngestOutcome must stay frozen — direct mutation must raise."""
        o = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("x"),
            url="u",
            media_path="p",
        )
        with pytest.raises(FrozenInstanceError):
            o.description = "mutate"  # type: ignore[misc]


class TestIngestOutcomeEngagement:
    """R061 — IngestOutcome carries initial engagement counters."""

    def test_engagement_fields_default_to_none(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            url="https://example.com/v/abc123",
            media_path="/tmp/x.mp4",
        )
        assert outcome.like_count is None
        assert outcome.comment_count is None

    def test_engagement_fields_round_trip(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            url="https://example.com/v/abc123",
            media_path="/tmp/x.mp4",
            like_count=42,
            comment_count=7,
        )
        assert outcome.like_count == 42
        assert outcome.comment_count == 7
