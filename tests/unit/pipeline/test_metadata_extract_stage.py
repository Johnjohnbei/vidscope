"""Unit tests for MetadataExtractStage (M007/S03-P02 T01).

Tests cover:
- is_satisfied: None video_id, links exist, links absent
- execute: description-only, transcript-only, both sources, both empty,
  missing video_id, missing video row, StageResult shape
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vidscope.domain import IndexingError, Link, VideoId
from vidscope.pipeline.stages.metadata_extract import MetadataExtractStage
from vidscope.ports.link_extractor import RawLink


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeLinkExtractor:
    """Controllable LinkExtractor stub.

    ``per_source_results`` maps ``source -> list[RawLink]`` injected per test.
    """

    def __init__(self, per_source_results: dict[str, list[RawLink]] | None = None) -> None:
        self._results: dict[str, list[RawLink]] = per_source_results or {}
        self.calls: list[tuple[str, str]] = []  # [(text, source), ...]

    def extract(self, text: str, *, source: str) -> list[RawLink]:
        self.calls.append((text, source))
        return self._results.get(source, [])


def _make_raw_link(url: str, source: str) -> RawLink:
    return RawLink(
        url=url,
        normalized_url=url.lower(),
        source=source,
        position_ms=None,
    )


class FakeTranscript:
    def __init__(self, full_text: str) -> None:
        self.full_text = full_text


class FakeVideo:
    def __init__(self, description: str | None) -> None:
        self.description = description


class FakeVideoRepo:
    def __init__(self, video: FakeVideo | None) -> None:
        self._video = video

    def get(self, video_id: VideoId) -> FakeVideo | None:
        return self._video


class FakeTranscriptRepo:
    def __init__(self, transcript: FakeTranscript | None) -> None:
        self._transcript = transcript

    def get_for_video(self, video_id: VideoId) -> FakeTranscript | None:
        return self._transcript


class FakeLinkRepo:
    def __init__(self, *, has_any: bool = False) -> None:
        self._has_any = has_any
        self.added_calls: list[tuple[VideoId, list[Link]]] = []

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return self._has_any

    def add_many_for_video(self, video_id: VideoId, links: list[Link]) -> list[Link]:
        self.added_calls.append((video_id, links))
        # Simulate persistence by returning the same links (id not set but OK for tests)
        return links


class FakeUoW:
    """Minimal UnitOfWork stub."""

    def __init__(
        self,
        *,
        video: FakeVideo | None = None,
        transcript: FakeTranscript | None = None,
        links_has_any: bool = False,
    ) -> None:
        self.videos = FakeVideoRepo(video)
        self.transcripts = FakeTranscriptRepo(transcript)
        self.links = FakeLinkRepo(has_any=links_has_any)


# ---------------------------------------------------------------------------
# is_satisfied tests
# ---------------------------------------------------------------------------


class TestIsSatisfied:
    def _stage(self, **kwargs: object) -> MetadataExtractStage:
        return MetadataExtractStage(link_extractor=FakeLinkExtractor())

    def _ctx(self, video_id: VideoId | None) -> MagicMock:
        ctx = MagicMock()
        ctx.video_id = video_id
        return ctx

    def test_none_video_id_returns_false(self) -> None:
        """Test 1: ctx.video_id=None → False (defensive pattern)."""
        stage = self._stage()
        ctx = self._ctx(None)
        uow = FakeUoW()
        assert stage.is_satisfied(ctx, uow) is False  # type: ignore[arg-type]

    def test_links_exist_returns_true(self) -> None:
        """Test 2: links.has_any_for_video returns True → is_satisfied True."""
        stage = self._stage()
        ctx = self._ctx(VideoId(42))
        uow = FakeUoW(links_has_any=True)
        assert stage.is_satisfied(ctx, uow) is True  # type: ignore[arg-type]

    def test_no_links_returns_false(self) -> None:
        """Test 3: links.has_any_for_video returns False → is_satisfied False."""
        stage = self._stage()
        ctx = self._ctx(VideoId(42))
        uow = FakeUoW(links_has_any=False)
        assert stage.is_satisfied(ctx, uow) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# execute tests
# ---------------------------------------------------------------------------


class TestExecute:
    def _ctx(self, video_id: VideoId | None) -> MagicMock:
        ctx = MagicMock()
        ctx.video_id = video_id
        return ctx

    def test_description_only_extracts_and_persists_one_link(self) -> None:
        """Test 4: description with URL → 1 link with source='description'."""
        raw = _make_raw_link("https://shop.com", "description")
        extractor = FakeLinkExtractor(per_source_results={"description": [raw]})
        stage = MetadataExtractStage(link_extractor=extractor)

        video = FakeVideo(description="visit https://shop.com")
        uow = FakeUoW(video=video, transcript=FakeTranscript(""))

        ctx = self._ctx(VideoId(1))
        result = stage.execute(ctx, uow)  # type: ignore[arg-type]

        assert len(uow.links.added_calls) == 1
        _, links = uow.links.added_calls[0]
        assert len(links) == 1
        assert links[0].source == "description"
        assert links[0].url == "https://shop.com"
        assert "1" in result.message  # "extracted 1 link(s)"

    def test_transcript_only_extracts_and_persists_one_link(self) -> None:
        """Test 5: description=None, transcript has URL → 1 link with source='transcript'."""
        raw = _make_raw_link("https://docs.com", "transcript")
        extractor = FakeLinkExtractor(per_source_results={"transcript": [raw]})
        stage = MetadataExtractStage(link_extractor=extractor)

        video = FakeVideo(description=None)
        transcript = FakeTranscript(full_text="check out https://docs.com")
        uow = FakeUoW(video=video, transcript=transcript)

        ctx = self._ctx(VideoId(2))
        result = stage.execute(ctx, uow)  # type: ignore[arg-type]

        assert len(uow.links.added_calls) == 1
        _, links = uow.links.added_calls[0]
        assert len(links) == 1
        assert links[0].source == "transcript"
        assert links[0].url == "https://docs.com"
        assert "1" in result.message

    def test_both_sources_extracts_two_links(self) -> None:
        """Test 6: description + transcript both have URLs → 2 links, one per source."""
        raw_desc = _make_raw_link("https://a.com", "description")
        raw_trans = _make_raw_link("https://b.com", "transcript")
        extractor = FakeLinkExtractor(
            per_source_results={
                "description": [raw_desc],
                "transcript": [raw_trans],
            }
        )
        stage = MetadataExtractStage(link_extractor=extractor)

        video = FakeVideo(description="https://a.com")
        transcript = FakeTranscript(full_text="also https://b.com")
        uow = FakeUoW(video=video, transcript=transcript)

        ctx = self._ctx(VideoId(3))
        result = stage.execute(ctx, uow)  # type: ignore[arg-type]

        assert len(uow.links.added_calls) == 1
        _, links = uow.links.added_calls[0]
        assert len(links) == 2
        sources = {lnk.source for lnk in links}
        assert sources == {"description", "transcript"}
        assert "2" in result.message

    def test_both_empty_calls_add_with_empty_list(self) -> None:
        """Test 7: description=None, transcript missing → add_many called with []."""
        extractor = FakeLinkExtractor()
        stage = MetadataExtractStage(link_extractor=extractor)

        video = FakeVideo(description=None)
        uow = FakeUoW(video=video, transcript=None)

        ctx = self._ctx(VideoId(4))
        result = stage.execute(ctx, uow)  # type: ignore[arg-type]

        # add_many_for_video MUST be called with empty list (idempotence contract)
        assert len(uow.links.added_calls) == 1
        _, links = uow.links.added_calls[0]
        assert links == []
        assert "0" in result.message

    def test_missing_video_id_raises_indexing_error(self) -> None:
        """Test 8: ctx.video_id=None → raises IndexingError."""
        stage = MetadataExtractStage(link_extractor=FakeLinkExtractor())
        ctx = self._ctx(None)
        uow = FakeUoW()

        with pytest.raises(IndexingError):
            stage.execute(ctx, uow)  # type: ignore[arg-type]

    def test_missing_video_row_description_treated_as_none(self) -> None:
        """Test 9: uow.videos.get returns None → description=None → extractor returns []."""
        extractor = FakeLinkExtractor()
        stage = MetadataExtractStage(link_extractor=extractor)

        # video=None simulates a row that doesn't exist yet
        uow = FakeUoW(video=None, transcript=None)
        ctx = self._ctx(VideoId(5))
        result = stage.execute(ctx, uow)  # type: ignore[arg-type]

        # Should not crash; extractor should not be called with description
        desc_calls = [c for c in extractor.calls if c[1] == "description"]
        assert desc_calls == []
        assert "0" in result.message

    def test_execute_returns_stage_result_with_count_message(self) -> None:
        """Test 10: StageResult.message contains number of persisted links."""
        from vidscope.ports.pipeline import StageResult

        raw = _make_raw_link("https://example.com", "description")
        extractor = FakeLinkExtractor(per_source_results={"description": [raw]})
        stage = MetadataExtractStage(link_extractor=extractor)

        video = FakeVideo(description="https://example.com")
        uow = FakeUoW(video=video, transcript=None)
        ctx = self._ctx(VideoId(6))

        result = stage.execute(ctx, uow)  # type: ignore[arg-type]

        assert isinstance(result, StageResult)
        assert "1" in result.message
