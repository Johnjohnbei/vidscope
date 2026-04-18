"""Unit tests for RapidOcrEngine — library-absent + stubbed paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vidscope.adapters.vision import RapidOcrEngine
from vidscope.ports import OcrLine


class TestRapidOcrEngineLazy:
    def test_init_does_not_load_engine(self) -> None:
        engine = RapidOcrEngine()
        # The underlying rapidocr engine is lazy: None until first call.
        assert engine._engine is None
        assert engine._unavailable is False

    def test_extract_text_missing_file_returns_empty(self) -> None:
        engine = RapidOcrEngine()
        assert engine.extract_text("/nonexistent/path.jpg") == []

    def test_extract_text_when_library_missing_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Force the ImportError path.
        engine = RapidOcrEngine()
        engine._unavailable = True
        jpg = tmp_path / "f.jpg"
        jpg.write_bytes(b"not-a-real-jpg-but-exists")
        assert engine.extract_text(str(jpg)) == []


class _StubEngine:
    """Mimics rapidocr_onnxruntime.RapidOCR.__call__ return shape."""

    def __init__(self, result: Any) -> None:
        self._result = result

    def __call__(self, image_path: str) -> tuple[Any, float]:
        return self._result, 0.01


class TestRapidOcrEngineParsing:
    def _with_stub(self, result: Any, tmp_path: Path) -> tuple[RapidOcrEngine, str]:
        jpg = tmp_path / "f.jpg"
        jpg.write_bytes(b"fake-jpg-file")
        engine = RapidOcrEngine()
        engine._engine = _StubEngine(result)
        return engine, str(jpg)

    def test_none_result_returns_empty(self, tmp_path: Path) -> None:
        engine, path = self._with_stub(None, tmp_path)
        assert engine.extract_text(path) == []

    def test_single_line_parsed(self, tmp_path: Path) -> None:
        stub_result = [
            [
                [[0, 0], [10, 0], [10, 5], [0, 5]],
                "Link in bio",
                0.95,
            ]
        ]
        engine, path = self._with_stub(stub_result, tmp_path)
        lines = engine.extract_text(path)
        assert len(lines) == 1
        assert lines[0].text == "Link in bio"
        assert lines[0].confidence == 0.95
        assert lines[0].bbox is not None

    def test_confidence_filter_drops_low_conf(self, tmp_path: Path) -> None:
        stub_result = [
            [[[0, 0], [10, 0], [10, 5], [0, 5]], "Hello", 0.9],
            [[[0, 0], [10, 0], [10, 5], [0, 5]], "Noise", 0.3],
        ]
        engine, path = self._with_stub(stub_result, tmp_path)
        lines = engine.extract_text(path, min_confidence=0.5)
        assert len(lines) == 1
        assert lines[0].text == "Hello"

    def test_empty_text_dropped(self, tmp_path: Path) -> None:
        stub_result = [
            [[[0, 0], [10, 0], [10, 5], [0, 5]], "   ", 0.9],
        ]
        engine, path = self._with_stub(stub_result, tmp_path)
        assert engine.extract_text(path) == []

    def test_bbox_is_json_string(self, tmp_path: Path) -> None:
        stub_result = [
            [[[1, 2], [3, 4], [5, 6], [7, 8]], "X", 0.9],
        ]
        engine, path = self._with_stub(stub_result, tmp_path)
        lines = engine.extract_text(path)
        parsed = json.loads(lines[0].bbox or "null")
        assert parsed == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]

    def test_engine_exception_returns_empty(self, tmp_path: Path) -> None:
        class _Boom:
            def __call__(self, image_path: str) -> Any:
                raise RuntimeError("boom")

        jpg = tmp_path / "f.jpg"
        jpg.write_bytes(b"x")
        engine = RapidOcrEngine()
        engine._engine = _Boom()
        assert engine.extract_text(str(jpg)) == []

    def test_returns_ocr_line_instances(self, tmp_path: Path) -> None:
        stub_result = [[[[0, 0], [1, 0], [1, 1], [0, 1]], "X", 0.9]]
        engine, path = self._with_stub(stub_result, tmp_path)
        lines = engine.extract_text(path)
        assert all(isinstance(line, OcrLine) for line in lines)
