"""Unit tests for the OCR + face-count ports and FrameTextRepository."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vidscope.domain import FrameText, VideoId
from vidscope.ports import FaceCounter, FrameTextRepository, OcrEngine, OcrLine


class TestOcrLine:
    def test_defaults(self) -> None:
        line = OcrLine(text="hello", confidence=0.9)
        assert line.text == "hello"
        assert line.confidence == 0.9
        assert line.bbox is None

    def test_full_round_trip(self) -> None:
        line = OcrLine(
            text="Link in bio",
            confidence=0.95,
            bbox="[[0,0],[10,0],[10,5],[0,5]]",
        )
        assert line.bbox == "[[0,0],[10,0],[10,5],[0,5]]"

    def test_is_frozen(self) -> None:
        line = OcrLine(text="x", confidence=0.5)
        with pytest.raises(FrozenInstanceError):
            line.text = "y"  # type: ignore[misc]


class _StubOcrEngine:
    def extract_text(
        self, image_path: str, *, min_confidence: float = 0.5
    ) -> list[OcrLine]:
        return []


class _StubFaceCounter:
    def count_faces(self, image_path: str) -> int:
        return 0


class _StubFrameTextRepository:
    def add_many_for_frame(
        self,
        frame_id: int,
        video_id: VideoId,
        texts: list[FrameText],
    ) -> list[FrameText]:
        return []

    def list_for_video(self, video_id: VideoId) -> list[FrameText]:
        return []

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return False

    def find_video_ids_by_text(
        self, query: str, *, limit: int = 50
    ) -> list[VideoId]:
        return []


class TestOcrEngineProtocol:
    def test_stub_satisfies_protocol(self) -> None:
        engine: OcrEngine = _StubOcrEngine()
        assert isinstance(engine, OcrEngine)
        assert engine.extract_text("x.jpg") == []


class TestFaceCounterProtocol:
    def test_stub_satisfies_protocol(self) -> None:
        counter: FaceCounter = _StubFaceCounter()
        assert isinstance(counter, FaceCounter)
        assert counter.count_faces("x.jpg") == 0


class TestFrameTextRepositoryProtocol:
    def test_stub_satisfies_protocol(self) -> None:
        repo: FrameTextRepository = _StubFrameTextRepository()
        assert isinstance(repo, FrameTextRepository)
        assert repo.list_for_video(VideoId(1)) == []
        assert repo.has_any_for_video(VideoId(1)) is False
