"""Unit tests for vidscope.domain.values.

These tests must have no I/O and no third-party imports beyond pytest.
"""

from __future__ import annotations

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


class TestPlatform:
    def test_members_are_canonical_strings(self) -> None:
        assert Platform.INSTAGRAM.value == "instagram"
        assert Platform.TIKTOK.value == "tiktok"
        assert Platform.YOUTUBE.value == "youtube"

    def test_string_behavior_enables_direct_comparison(self) -> None:
        assert Platform.INSTAGRAM == "instagram"
        assert Platform.YOUTUBE.value == "youtube"

    def test_enum_is_stable_for_iteration(self) -> None:
        names = {p.name for p in Platform}
        assert names == {"INSTAGRAM", "TIKTOK", "YOUTUBE"}


class TestStageName:
    def test_execution_order_is_declaration_order(self) -> None:
        order = list(StageName)
        assert order == [
            StageName.INGEST,
            StageName.TRANSCRIBE,
            StageName.FRAMES,
            StageName.ANALYZE,
            StageName.INDEX,
        ]

    def test_string_values_match_names_lowercased(self) -> None:
        for stage in StageName:
            assert stage.value == stage.name.lower()


class TestRunStatus:
    def test_terminal_states_are_distinguishable(self) -> None:
        terminal = {RunStatus.OK, RunStatus.FAILED, RunStatus.SKIPPED}
        non_terminal = {RunStatus.PENDING, RunStatus.RUNNING}
        assert terminal.isdisjoint(non_terminal)

    def test_all_status_values_are_unique(self) -> None:
        values = [s.value for s in RunStatus]
        assert len(values) == len(set(values))


class TestLanguage:
    def test_unknown_is_a_valid_fallback(self) -> None:
        assert Language.UNKNOWN.value == "unknown"

    def test_supported_languages_cover_fr_en(self) -> None:
        supported = {Language.FRENCH, Language.ENGLISH}
        assert all(isinstance(lang.value, str) for lang in supported)


class TestNewTypes:
    def test_video_id_is_runtime_int(self) -> None:
        vid = VideoId(42)
        assert vid == 42
        assert isinstance(vid, int)

    def test_platform_id_is_runtime_str(self) -> None:
        pid = PlatformId("abc123")
        assert pid == "abc123"
        assert isinstance(pid, str)


class TestCreatorId:
    def test_is_int_newtype(self) -> None:
        cid = CreatorId(42)
        assert cid == 42
        assert isinstance(cid, int)

    def test_round_trip_preserves_value(self) -> None:
        assert int(CreatorId(0)) == 0
        assert int(CreatorId(999_999)) == 999_999


class TestPlatformUserId:
    def test_is_str_newtype(self) -> None:
        puid = PlatformUserId("UC123")
        assert puid == "UC123"
        assert isinstance(puid, str)

    def test_accepts_empty_string(self) -> None:
        # NewType is type-level only; empty strings are legal at
        # runtime. Adapter-layer validation handles rejection.
        assert PlatformUserId("") == ""
