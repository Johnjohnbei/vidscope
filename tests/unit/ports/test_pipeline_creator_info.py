"""Contract tests for CreatorInfo TypedDict and IngestOutcome.creator_info (M006/S02-P01, D-01)."""

from __future__ import annotations

from typing import get_type_hints

from vidscope.domain import Platform, PlatformId
from vidscope.ports import CreatorInfo, IngestOutcome


class TestCreatorInfoShape:
    """CreatorInfo is the contract both adapters/ytdlp and pipeline/stages
    agree on. Its shape is not negotiable — it maps 1-for-1 to the 7
    mutable fields of domain.Creator.
    """

    def test_creator_info_has_exactly_seven_keys(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert set(hints.keys()) == {
            "platform_user_id",
            "handle",
            "display_name",
            "profile_url",
            "avatar_url",
            "follower_count",
            "is_verified",
        }, f"unexpected CreatorInfo keys: {hints.keys()}"

    def test_platform_user_id_is_required_str(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["platform_user_id"] is str

    def test_handle_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["handle"] == (str | None)

    def test_display_name_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["display_name"] == (str | None)

    def test_profile_url_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["profile_url"] == (str | None)

    def test_avatar_url_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["avatar_url"] == (str | None)

    def test_follower_count_is_optional_int(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["follower_count"] == (int | None)

    def test_is_verified_is_optional_bool(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["is_verified"] == (bool | None)

    def test_construction_with_all_fields(self) -> None:
        info: CreatorInfo = {
            "platform_user_id": "UC_abc",
            "handle": "@alice",
            "display_name": "Alice",
            "profile_url": "https://y/c/alice",
            "avatar_url": "https://y/img.jpg",
            "follower_count": 12345,
            "is_verified": True,
        }
        assert info["platform_user_id"] == "UC_abc"
        assert info["follower_count"] == 12345
        assert info["is_verified"] is True

    def test_construction_with_nullable_fields_as_none(self) -> None:
        info: CreatorInfo = {
            "platform_user_id": "UC_xyz",
            "handle": None,
            "display_name": None,
            "profile_url": None,
            "avatar_url": None,
            "follower_count": None,
            "is_verified": None,
        }
        assert info["platform_user_id"] == "UC_xyz"
        assert info["handle"] is None


class TestIngestOutcomeBackwardCompat:
    """IngestOutcome.creator_info defaults to None so existing callers
    that don't know about creators keep compiling (D-01 rétrocompat)."""

    def test_default_creator_info_is_none(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://y/watch?v=abc",
            media_path="/tmp/abc.mp4",
        )
        assert outcome.creator_info is None

    def test_creator_info_can_be_populated(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://y/watch?v=abc",
            media_path="/tmp/abc.mp4",
            creator_info={
                "platform_user_id": "UC_abc",
                "handle": "@alice",
                "display_name": "Alice",
                "profile_url": None,
                "avatar_url": None,
                "follower_count": None,
                "is_verified": None,
            },
        )
        assert outcome.creator_info is not None
        assert outcome.creator_info["platform_user_id"] == "UC_abc"
        assert outcome.creator_info["display_name"] == "Alice"

    def test_creator_info_none_keeps_other_fields_intact(self) -> None:
        """D-02 scenario: ingest succeeds without creator_info — every
        other field still populates normally."""
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://y/watch?v=abc",
            media_path="/tmp/abc.mp4",
            title="Hello",
            author="Unknown",
            duration=42.0,
            creator_info=None,
        )
        assert outcome.title == "Hello"
        assert outcome.author == "Unknown"
        assert outcome.creator_info is None


class TestCreatorInfoExposedInPortsPublicApi:
    """CreatorInfo must be importable from the ports public surface so
    the pipeline stage (P03) can consume it without reaching into
    vidscope.ports.pipeline."""

    def test_creator_info_importable_from_vidscope_ports(self) -> None:
        from vidscope import ports as ports_pkg

        assert hasattr(ports_pkg, "CreatorInfo")
        assert ports_pkg.CreatorInfo is CreatorInfo

    def test_creator_info_listed_in_all(self) -> None:
        from vidscope import ports as ports_pkg

        assert "CreatorInfo" in ports_pkg.__all__
