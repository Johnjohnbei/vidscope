"""Unit tests for HaarcascadeFaceCounter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vidscope.adapters.vision import HaarcascadeFaceCounter


class TestHaarcascadeLazy:
    def test_init_does_not_load(self) -> None:
        counter = HaarcascadeFaceCounter()
        assert counter._cv2 is None
        assert counter._cascade is None

    def test_missing_file_returns_zero(self) -> None:
        counter = HaarcascadeFaceCounter()
        assert counter.count_faces("/nonexistent.jpg") == 0

    def test_library_missing_returns_zero(self, tmp_path: Path) -> None:
        jpg = tmp_path / "f.jpg"
        jpg.write_bytes(b"x")
        counter = HaarcascadeFaceCounter()
        counter._unavailable = True
        assert counter.count_faces(str(jpg)) == 0


class _StubCascade:
    def __init__(self, face_count: int) -> None:
        self._count = face_count

    def empty(self) -> bool:
        return False

    def detectMultiScale(self, *args: Any, **kwargs: Any) -> list[tuple[int, int, int, int]]:
        return [(0, 0, 10, 10)] * self._count


class _StubCv2:
    """Minimal cv2 mock exposing imread + cvtColor + COLOR_BGR2GRAY."""

    COLOR_BGR2GRAY = 42

    def imread(self, path: str) -> Any:
        return object() if Path(path).exists() else None

    def cvtColor(self, img: Any, code: int) -> Any:
        return img


class TestHaarcascadeCounting:
    def _prime(
        self,
        counter: HaarcascadeFaceCounter,
        face_count: int,
        tmp_path: Path,
    ) -> str:
        jpg = tmp_path / "f.jpg"
        jpg.write_bytes(b"x")
        counter._cv2 = _StubCv2()
        counter._cascade = _StubCascade(face_count)
        return str(jpg)

    def test_counts_single_face(self, tmp_path: Path) -> None:
        counter = HaarcascadeFaceCounter()
        path = self._prime(counter, 1, tmp_path)
        assert counter.count_faces(path) == 1

    def test_counts_multiple_faces(self, tmp_path: Path) -> None:
        counter = HaarcascadeFaceCounter()
        path = self._prime(counter, 3, tmp_path)
        assert counter.count_faces(path) == 3

    def test_no_faces(self, tmp_path: Path) -> None:
        counter = HaarcascadeFaceCounter()
        path = self._prime(counter, 0, tmp_path)
        assert counter.count_faces(path) == 0

    def test_cv2_exception_returns_zero(self, tmp_path: Path) -> None:
        jpg = tmp_path / "f.jpg"
        jpg.write_bytes(b"x")

        class _Boom:
            def empty(self) -> bool:
                return False

            def detectMultiScale(self, *args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("boom")

        counter = HaarcascadeFaceCounter()
        counter._cv2 = _StubCv2()
        counter._cascade = _Boom()
        assert counter.count_faces(str(jpg)) == 0

    def test_imread_none_returns_zero(self, tmp_path: Path) -> None:
        jpg = tmp_path / "f.jpg"
        jpg.write_bytes(b"x")

        class _Cv2Fails:
            COLOR_BGR2GRAY = 42

            def imread(self, path: str) -> Any:
                return None

            def cvtColor(self, img: Any, code: int) -> Any:
                return img

        counter = HaarcascadeFaceCounter()
        counter._cv2 = _Cv2Fails()
        counter._cascade = _StubCascade(5)
        assert counter.count_faces(str(jpg)) == 0
