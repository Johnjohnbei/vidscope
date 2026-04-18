"""Unit tests for VisualIntelligenceStage (M008/S02-P01 T01).

Tests cover:
- is_satisfied: None video_id, no frame_texts, frame_texts exist
- execute contract violations: None video_id
- execute happy paths: no frames, all-empty OCR, text without URL,
  text with URL (position_ms), multiple frames, deduplication
- execute unavailable engine detection
- execute media-resolution errors (per-frame graceful skip)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from vidscope.adapters.text import RegexLinkExtractor
from vidscope.domain import (
    Frame,
    FrameText,
    IndexingError,
    Link,
    Platform,
    PlatformId,
    Video,
    VideoId,
)
from vidscope.pipeline.stages import VisualIntelligenceStage
from vidscope.ports import PipelineContext
from vidscope.ports.ocr_engine import OcrEngine, OcrLine

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeOcrEngine:
    """Stub OcrEngine returning a deterministic per-image result."""

    def __init__(self, results: dict[str, list[OcrLine]] | None = None) -> None:
        self._results = results or {}
        self._unavailable = False
        self.calls: list[tuple[str, float]] = []

    def extract_text(
        self, image_path: str, *, min_confidence: float = 0.5
    ) -> list[OcrLine]:
        self.calls.append((image_path, min_confidence))
        return self._results.get(image_path, [])


class _UnavailableOcrEngine(_FakeOcrEngine):
    def __init__(self) -> None:
        super().__init__()
        self._unavailable = True


@dataclass
class _FakeFrameTextRepo:
    rows: list[FrameText] = field(default_factory=list)
    next_id: int = 1

    def add_many_for_frame(
        self, frame_id: int, video_id: VideoId, texts: list[FrameText]
    ) -> list[FrameText]:
        stored = []
        for t in texts:
            ft = FrameText(
                video_id=t.video_id,
                frame_id=t.frame_id,
                text=t.text,
                confidence=t.confidence,
                bbox=t.bbox,
                id=self.next_id,
            )
            self.next_id += 1
            self.rows.append(ft)
            stored.append(ft)
        return stored

    def list_for_video(self, video_id: VideoId) -> list[FrameText]:
        return [r for r in self.rows if r.video_id == video_id]

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return any(r.video_id == video_id for r in self.rows)

    def find_video_ids_by_text(self, query: str, *, limit: int = 50) -> list[VideoId]:
        return []


@dataclass
class _FakeFrameRepo:
    frames: list[Frame] = field(default_factory=list)

    def add_many(self, frames: list[Frame]) -> list[Frame]:
        self.frames.extend(frames)
        return list(frames)

    def list_for_video(self, video_id: VideoId) -> list[Frame]:
        return [f for f in self.frames if f.video_id == video_id]


@dataclass
class _FakeLinkRepo:
    rows: list[Link] = field(default_factory=list)
    next_id: int = 1

    def add_many_for_video(
        self, video_id: VideoId, links: list[Link]
    ) -> list[Link]:
        seen: set[tuple[str, str]] = set()
        added: list[Link] = []
        for link in links:
            key = (link.normalized_url, link.source)
            if key in seen:
                continue
            seen.add(key)
            new = Link(
                video_id=link.video_id,
                url=link.url,
                normalized_url=link.normalized_url,
                source=link.source,
                position_ms=link.position_ms,
                id=self.next_id,
            )
            self.next_id += 1
            added.append(new)
            self.rows.append(new)
        return added

    def list_for_video(self, video_id: VideoId, *, source: str | None = None) -> list[Link]:
        out = [r for r in self.rows if r.video_id == video_id]
        if source is not None:
            out = [r for r in out if r.source == source]
        return out

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return any(r.video_id == video_id for r in self.rows)

    def find_video_ids_with_any_link(self, *, limit: int = 50) -> list[VideoId]:
        return []


@dataclass
class _FakeUoW:
    frames: _FakeFrameRepo
    frame_texts: _FakeFrameTextRepo
    links: _FakeLinkRepo

    def __enter__(self) -> _FakeUoW:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _FakeFaceCounter:
    def __init__(self, results: dict[str, int] | None = None) -> None:
        self._results = results or {}
        self.calls: list[str] = []

    def count_faces(self, image_path: str) -> int:
        self.calls.append(image_path)
        return self._results.get(image_path, 0)


class _FakeMediaStorage:
    def __init__(self, base: Path) -> None:
        self._base = base
        self.stored: list[tuple[str, Path]] = []

    def resolve(self, key: str) -> Path:
        return self._base / key

    def store(self, key: str, source_path: Path) -> str:
        self.stored.append((key, source_path))
        return key


@dataclass
class _FakeVideoRepo:
    videos: dict[int, Video] = field(default_factory=dict)

    def add(self, video: Video) -> Video:
        new_id = VideoId(len(self.videos) + 1)
        stored = Video(
            platform=video.platform,
            platform_id=video.platform_id,
            url=video.url,
            id=new_id,
        )
        self.videos[int(new_id)] = stored
        return stored

    def get(self, video_id: VideoId) -> Video | None:
        return self.videos.get(int(video_id))

    def update_visual_metadata(
        self,
        video_id: VideoId,
        *,
        thumbnail_key: str | None,
        content_shape: str | None,
    ) -> None:
        v = self.videos.get(int(video_id))
        if v is None:
            raise ValueError(f"video {video_id} not found")
        self.videos[int(video_id)] = Video(
            platform=v.platform,
            platform_id=v.platform_id,
            url=v.url,
            id=v.id,
            thumbnail_key=thumbnail_key,
            content_shape=content_shape,
        )


@dataclass
class _FakeUoW:
    frames: _FakeFrameRepo
    frame_texts: _FakeFrameTextRepo
    links: _FakeLinkRepo
    videos: _FakeVideoRepo = field(default_factory=_FakeVideoRepo)

    def __enter__(self) -> _FakeUoW:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(video_id: int = 1) -> PipelineContext:
    c = PipelineContext(source_url="https://example.com/v1")
    c.video_id = VideoId(video_id)
    c.platform = Platform.YOUTUBE
    c.platform_id = PlatformId("abc")
    return c


def _stage(
    engine: OcrEngine | None = None,
    face_counter: _FakeFaceCounter | None = None,
    tmp_path: Path | None = None,
) -> tuple[VisualIntelligenceStage, _FakeUoW]:
    engine = engine or _FakeOcrEngine()
    counter = face_counter or _FakeFaceCounter()
    media = _FakeMediaStorage(tmp_path or Path("/tmp"))
    stage = VisualIntelligenceStage(
        ocr_engine=engine,
        face_counter=counter,
        link_extractor=RegexLinkExtractor(),
        media_storage=media,
    )
    uow = _FakeUoW(
        frames=_FakeFrameRepo(),
        frame_texts=_FakeFrameTextRepo(),
        links=_FakeLinkRepo(),
        videos=_FakeVideoRepo(),
    )
    # Always seed the target video (video_id=1) since the stage now calls
    # update_visual_metadata on it.
    uow.videos.videos[1] = Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId("abc"),
        url="u",
        id=VideoId(1),
    )
    return stage, uow


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClassifyContentShape:
    """Tests for the classify_content_shape helper (M008/R049)."""

    def test_empty_list_returns_unknown(self) -> None:
        from vidscope.domain import ContentShape
        from vidscope.pipeline.stages.visual_intelligence import classify_content_shape

        assert classify_content_shape([]) == ContentShape.UNKNOWN

    def test_all_zeros_returns_broll(self) -> None:
        from vidscope.domain import ContentShape
        from vidscope.pipeline.stages.visual_intelligence import classify_content_shape

        assert classify_content_shape([0, 0, 0]) == ContentShape.BROLL

    def test_sixty_percent_faces_returns_talking_head(self) -> None:
        from vidscope.domain import ContentShape
        from vidscope.pipeline.stages.visual_intelligence import classify_content_shape

        # 3/5 = 60% ≥ 40%
        assert classify_content_shape([1, 0, 1, 0, 1]) == ContentShape.TALKING_HEAD

    def test_exactly_forty_percent_returns_talking_head(self) -> None:
        from vidscope.domain import ContentShape
        from vidscope.pipeline.stages.visual_intelligence import classify_content_shape

        # 2/5 = 40%
        assert classify_content_shape([1, 0, 1, 0, 0]) == ContentShape.TALKING_HEAD

    def test_twenty_percent_returns_mixed(self) -> None:
        from vidscope.domain import ContentShape
        from vidscope.pipeline.stages.visual_intelligence import classify_content_shape

        # 1/5 = 20% < 40%
        assert classify_content_shape([1, 0, 0, 0, 0]) == ContentShape.MIXED

    def test_single_frame_with_face_returns_talking_head(self) -> None:
        from vidscope.domain import ContentShape
        from vidscope.pipeline.stages.visual_intelligence import classify_content_shape

        assert classify_content_shape([1]) == ContentShape.TALKING_HEAD

    def test_multiface_frames_count_as_one(self) -> None:
        from vidscope.domain import ContentShape
        from vidscope.pipeline.stages.visual_intelligence import classify_content_shape

        # 2 frames with ≥1 face out of 5 = 40% → TALKING_HEAD
        assert classify_content_shape([3, 0, 2, 0, 0]) == ContentShape.TALKING_HEAD


class TestIsSatisfied:
    def test_returns_false_when_video_id_missing(self) -> None:
        stage, uow = _stage()
        ctx = PipelineContext(source_url="x")
        assert stage.is_satisfied(ctx, uow) is False  # type: ignore[arg-type]

    def test_returns_false_when_no_frame_texts(self) -> None:
        stage, uow = _stage()
        assert stage.is_satisfied(_ctx(), uow) is False  # type: ignore[arg-type]

    def test_returns_true_when_all_outputs_present(self) -> None:
        # S03: compound check — frame_texts + thumbnail_key + content_shape
        stage, uow = _stage()
        uow.frame_texts.rows.append(
            FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=0.9, id=1)
        )
        uow.videos.update_visual_metadata(
            VideoId(1),
            thumbnail_key="videos/youtube/abc/thumb.jpg",
            content_shape="broll",
        )
        assert stage.is_satisfied(_ctx(), uow) is True  # type: ignore[arg-type]

    def test_returns_false_when_frame_texts_exist_but_thumbnail_missing(self) -> None:
        # Half-completed run: OCR done but thumbnail not yet copied
        stage, uow = _stage()
        uow.frame_texts.rows.append(
            FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=0.9, id=1)
        )
        # thumbnail_key and content_shape still None
        assert stage.is_satisfied(_ctx(), uow) is False  # type: ignore[arg-type]


class TestExecuteContractViolations:
    def test_raises_indexing_error_when_video_id_missing(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        ctx = PipelineContext(source_url="x")
        with pytest.raises(IndexingError) as exc_info:
            stage.execute(ctx, uow)  # type: ignore[arg-type]
        assert "visual_intelligence" in str(exc_info.value)
        assert "video_id" in str(exc_info.value)


class TestExecuteHappyPaths:
    def test_no_frames_returns_skipped(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert result.skipped is True
        assert "no frames" in result.message.lower()

    def test_all_frames_empty_ocr_returns_ok_zero(self, tmp_path: Path) -> None:
        engine = _FakeOcrEngine()  # no results for any path
        stage, uow = _stage(engine=engine, tmp_path=tmp_path)
        for i, ts in enumerate([0, 1000, 2000]):
            uow.frames.frames.append(
                Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=ts, id=i + 1)
            )
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert result.skipped is False
        assert "no text" in result.message.lower()
        assert len(uow.frame_texts.rows) == 0
        assert len(uow.links.rows) == 0
        # Verify engine was called for each frame
        assert len(engine.calls) == 3

    def test_one_frame_with_text_no_url(self, tmp_path: Path) -> None:
        engine = _FakeOcrEngine(
            results={
                str(tmp_path / "f/0.jpg"): [
                    OcrLine(text="Hello world", confidence=0.9),
                ]
            }
        )
        stage, uow = _stage(engine=engine, tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
        )
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert result.skipped is False
        assert len(uow.frame_texts.rows) == 1
        assert uow.frame_texts.rows[0].text == "Hello world"
        assert len(uow.links.rows) == 0

    def test_frame_with_link_persists_ocr_link(self, tmp_path: Path) -> None:
        engine = _FakeOcrEngine(
            results={
                str(tmp_path / "f/0.jpg"): [
                    OcrLine(text="Link in bio: https://example.com", confidence=0.95),
                ]
            }
        )
        stage, uow = _stage(engine=engine, tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=2500, id=1)
        )
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert result.skipped is False
        assert len(uow.frame_texts.rows) == 1
        assert len(uow.links.rows) == 1
        link = uow.links.rows[0]
        assert link.source == "ocr"
        assert link.position_ms == 2500
        assert "example.com" in link.normalized_url

    def test_multiple_frames_multiple_links(self, tmp_path: Path) -> None:
        engine = _FakeOcrEngine(
            results={
                str(tmp_path / "f/0.jpg"): [
                    OcrLine(text="Visit promo.com now", confidence=0.9)
                ],
                str(tmp_path / "f/1.jpg"): [
                    OcrLine(text="Also: https://shop.net/deal", confidence=0.85)
                ],
            }
        )
        stage, uow = _stage(engine=engine, tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=1000, id=1)
        )
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/1.jpg", timestamp_ms=3000, id=2)
        )
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert result.skipped is False
        assert len(uow.frame_texts.rows) == 2
        # Each frame's links should carry its own timestamp
        timestamps = {link.position_ms for link in uow.links.rows}
        assert timestamps == {1000, 3000}

    def test_same_url_across_frames_deduplicated(self, tmp_path: Path) -> None:
        engine = _FakeOcrEngine(
            results={
                str(tmp_path / "f/0.jpg"): [
                    OcrLine(text="See example.com", confidence=0.9)
                ],
                str(tmp_path / "f/1.jpg"): [
                    OcrLine(text="example.com again", confidence=0.9)
                ],
            }
        )
        stage, uow = _stage(engine=engine, tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=1000, id=1)
        )
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/1.jpg", timestamp_ms=2000, id=2)
        )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        # add_many_for_video dedups by (normalized_url, source) — one row only
        assert len(uow.links.rows) == 1


class TestExecuteUnavailableEngine:
    def test_unavailable_engine_with_frames_returns_skipped(self, tmp_path: Path) -> None:
        engine = _UnavailableOcrEngine()
        stage, uow = _stage(engine=engine, tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
        )
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert result.skipped is True
        assert "rapidocr" in result.message.lower()
        assert len(uow.frame_texts.rows) == 0


class TestExecuteMediaResolutionErrors:
    def test_resolve_exception_is_skipped_per_frame(self, tmp_path: Path) -> None:
        class _BrokenStorage:
            stored: list[tuple[str, Path]] = []

            def resolve(self, key: str) -> Path:
                raise RuntimeError("disk unplugged")

            def store(self, key: str, source_path: Path) -> str:
                self.stored.append((key, source_path))
                return key

        engine = _FakeOcrEngine()
        stage = VisualIntelligenceStage(
            ocr_engine=engine,
            face_counter=_FakeFaceCounter(),
            link_extractor=RegexLinkExtractor(),
            media_storage=_BrokenStorage(),  # type: ignore[arg-type]
        )
        uow = _FakeUoW(
            frames=_FakeFrameRepo(),
            frame_texts=_FakeFrameTextRepo(),
            links=_FakeLinkRepo(),
            videos=_FakeVideoRepo(),
        )
        uow.videos.videos[1] = Video(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="u",
            id=VideoId(1),
        )
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
        )
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        # No crash — just skipped frame, returned as empty result
        assert result.skipped is False
        assert len(uow.frame_texts.rows) == 0


# ---------------------------------------------------------------------------
# T02 new test classes: thumbnail copy, content_shape, compound is_satisfied
# ---------------------------------------------------------------------------


class TestThumbnail:
    def test_middle_frame_copied_odd_count(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        for i, ts in enumerate([0, 1000, 2000, 3000, 4000]):
            uow.frames.frames.append(
                Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=ts, id=i + 1)
            )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        stored_keys = [k for k, _ in stage._media_storage.stored]  # type: ignore[attr-defined]
        # 5 frames, middle_idx=2 → f/2.jpg → key ends with thumb.jpg
        assert any(k.endswith("/thumb.jpg") for k in stored_keys)

    def test_middle_frame_copied_even_count(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        for i, ts in enumerate([0, 1000, 2000, 3000]):
            uow.frames.frames.append(
                Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=ts, id=i + 1)
            )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        # N=4, middle_idx=2 → source is f/2.jpg
        sources = [s for _, s in stage._media_storage.stored]  # type: ignore[attr-defined]
        assert any("2.jpg" in str(s) for s in sources)

    def test_single_frame_used_as_thumbnail(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
        )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        sources = [s for _, s in stage._media_storage.stored]  # type: ignore[attr-defined]
        assert any("0.jpg" in str(s) for s in sources)

    def test_thumbnail_key_format(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=0, id=1)
        )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        stored_keys = [k for k, _ in stage._media_storage.stored]  # type: ignore[attr-defined]
        assert any(k == "videos/youtube/abc/thumb.jpg" for k in stored_keys)

    def test_videos_thumbnail_key_updated(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        uow.frames.frames.append(
            Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=0, id=1)
        )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        v = uow.videos.get(VideoId(1))
        assert v is not None
        assert v.thumbnail_key == "videos/youtube/abc/thumb.jpg"


class TestContentShape:
    def test_no_frames_leaves_video_untouched(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        # No frames → skipped, content_shape not updated
        result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert result.skipped is True
        v = uow.videos.get(VideoId(1))
        assert v is not None
        assert v.content_shape is None

    def test_all_frames_have_faces_classified_talking_head(self, tmp_path: Path) -> None:
        counter = _FakeFaceCounter(
            {str(tmp_path / f"f/{i}.jpg"): 1 for i in range(3)}
        )
        stage, uow = _stage(face_counter=counter, tmp_path=tmp_path)
        for i in range(3):
            uow.frames.frames.append(
                Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
            )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        v = uow.videos.get(VideoId(1))
        assert v is not None
        assert v.content_shape == "talking_head"

    def test_no_faces_anywhere_classified_broll(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)  # default counter returns 0 for all
        for i in range(3):
            uow.frames.frames.append(
                Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
            )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        v = uow.videos.get(VideoId(1))
        assert v is not None
        assert v.content_shape == "broll"

    def test_partial_face_presence_classified_mixed(self, tmp_path: Path) -> None:
        counter = _FakeFaceCounter({str(tmp_path / "f/0.jpg"): 1})
        stage, uow = _stage(face_counter=counter, tmp_path=tmp_path)
        for i in range(5):  # 1/5 = 20% < 40%
            uow.frames.frames.append(
                Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
            )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        v = uow.videos.get(VideoId(1))
        assert v is not None
        assert v.content_shape == "mixed"

    def test_face_counter_called_per_frame(self, tmp_path: Path) -> None:
        counter = _FakeFaceCounter()
        stage, uow = _stage(face_counter=counter, tmp_path=tmp_path)
        for i in range(4):
            uow.frames.frames.append(
                Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
            )
        stage.execute(_ctx(), uow)  # type: ignore[arg-type]
        assert len(counter.calls) == 4


class TestCompoundIsSatisfied:
    def test_not_satisfied_when_frame_texts_missing(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        # video exists, no frame_texts
        assert stage.is_satisfied(_ctx(), uow) is False  # type: ignore[arg-type]

    def test_not_satisfied_when_thumbnail_key_is_none(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        uow.frame_texts.rows.append(
            FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=0.9, id=1)
        )
        # thumbnail_key still None on the video
        assert stage.is_satisfied(_ctx(), uow) is False  # type: ignore[arg-type]

    def test_satisfied_when_all_three_present(self, tmp_path: Path) -> None:
        stage, uow = _stage(tmp_path=tmp_path)
        uow.frame_texts.rows.append(
            FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=0.9, id=1)
        )
        uow.videos.update_visual_metadata(
            VideoId(1), thumbnail_key="videos/yt/abc/thumb.jpg", content_shape="mixed"
        )
        assert stage.is_satisfied(_ctx(), uow) is True  # type: ignore[arg-type]
