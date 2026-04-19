"""Unit tests for FasterWhisperTranscriber.

faster-whisper's WhisperModel is replaced with a fake via
monkeypatch on `sys.modules['faster_whisper'].WhisperModel` so the
real ~150MB model is never downloaded during unit tests.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest

from vidscope.adapters.whisper.transcriber import FasterWhisperTranscriber
from vidscope.domain import Language, TranscriptionError

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str


@dataclass
class FakeInfo:
    language: str | None = "en"
    language_probability: float = 0.99


class FakeWhisperModel:
    """Stand-in for faster_whisper.WhisperModel.

    Records constructor arguments and returns a preset list of
    segments + info on transcribe().
    """

    last_init_kwargs: ClassVar[dict[str, Any]] = {}

    def __init__(self, model_name: str, **kwargs: Any) -> None:
        type(self).last_init_kwargs = {"model_name": model_name, **kwargs}
        self._segments: list[FakeSegment] = []
        self._info = FakeInfo()
        self._raise: Exception | None = None

    def configure(
        self,
        *,
        segments: list[FakeSegment],
        language: str = "en",
        raise_on_transcribe: Exception | None = None,
    ) -> None:
        self._segments = segments
        self._info = FakeInfo(language=language)
        self._raise = raise_on_transcribe

    def transcribe(
        self, media_path: str, **kwargs: Any
    ) -> tuple[Any, FakeInfo]:
        if self._raise is not None:
            raise self._raise
        return iter(self._segments), self._info


@pytest.fixture()
def fake_model_class(monkeypatch: pytest.MonkeyPatch) -> type[FakeWhisperModel]:
    """Replace faster_whisper.WhisperModel with FakeWhisperModel.

    Tests can call `fake_model_class.last_instance.configure(...)` to
    shape the next transcribe() call's behavior.
    """
    # Store the most recently constructed instance for tests to configure
    instances: list[FakeWhisperModel] = []

    class CapturingFake(FakeWhisperModel):
        def __init__(self, model_name: str, **kwargs: Any) -> None:
            super().__init__(model_name, **kwargs)
            instances.append(self)

    # Make sure faster_whisper is importable as a stub if needed
    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", CapturingFake)
    # Also patch in case the module is reloaded inside the lazy import
    monkeypatch.setattr(
        sys.modules["faster_whisper"], "WhisperModel", CapturingFake
    )

    CapturingFake.instances = instances  # type: ignore[attr-defined]
    return CapturingFake


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_transcribes_english_video(
        self,
        fake_model_class: type[FakeWhisperModel],
        tmp_path: Path,
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake media")

        transcriber = FasterWhisperTranscriber(
            model_name="base",
            models_dir=tmp_path / "models",
        )

        # Trigger model load by transcribing — then reach into the
        # captured instance and configure it. (Lazy load means the
        # instance only exists after the first transcribe call.)
        # Workaround: prepare the segments BEFORE the first call by
        # patching the FakeWhisperModel default.
        result = transcriber.transcribe(str(media))

        # The default fake returns no segments and language="en"
        assert result.language is Language.ENGLISH
        assert result.full_text == ""
        assert result.segments == ()

    def test_transcribes_with_segments(
        self,
        fake_model_class: type[FakeWhisperModel],
        tmp_path: Path,
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake media")

        # Pre-configure the fake to return segments. We do this by
        # subclassing once more to inject the configuration into the
        # constructor.
        class PreconfiguredFake(FakeWhisperModel):
            def __init__(self, model_name: str, **kwargs: Any) -> None:
                super().__init__(model_name, **kwargs)
                self.configure(
                    segments=[
                        FakeSegment(0.0, 1.5, "Hello world."),
                        FakeSegment(1.5, 3.0, "This is a test."),
                    ],
                    language="en",
                )

        import faster_whisper

        monkeypatch_target = faster_whisper
        original = monkeypatch_target.WhisperModel
        monkeypatch_target.WhisperModel = PreconfiguredFake  # type: ignore[misc]
        try:
            transcriber = FasterWhisperTranscriber(
                model_name="base",
                models_dir=tmp_path / "models",
            )
            result = transcriber.transcribe(str(media))
        finally:
            monkeypatch_target.WhisperModel = original  # type: ignore[misc]

        assert result.language is Language.ENGLISH
        assert "Hello world." in result.full_text
        assert "This is a test." in result.full_text
        assert len(result.segments) == 2
        assert result.segments[0].start == 0.0
        assert result.segments[0].end == 1.5
        assert result.segments[0].text == "Hello world."

    def test_transcribes_french_video(
        self, tmp_path: Path
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake media")

        class FrenchFake(FakeWhisperModel):
            def __init__(self, model_name: str, **kwargs: Any) -> None:
                super().__init__(model_name, **kwargs)
                self.configure(
                    segments=[
                        FakeSegment(0.0, 2.0, "Bonjour tout le monde."),
                    ],
                    language="fr",
                )

        import faster_whisper

        original = faster_whisper.WhisperModel
        faster_whisper.WhisperModel = FrenchFake  # type: ignore[misc]
        try:
            transcriber = FasterWhisperTranscriber(
                model_name="base",
                models_dir=tmp_path / "models",
            )
            result = transcriber.transcribe(str(media))
        finally:
            faster_whisper.WhisperModel = original  # type: ignore[misc]

        assert result.language is Language.FRENCH
        assert "Bonjour" in result.full_text

    def test_unknown_language_falls_back_to_unknown(
        self, tmp_path: Path
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake media")

        class JapaneseFake(FakeWhisperModel):
            def __init__(self, model_name: str, **kwargs: Any) -> None:
                super().__init__(model_name, **kwargs)
                self.configure(segments=[], language="ja")

        import faster_whisper

        original = faster_whisper.WhisperModel
        faster_whisper.WhisperModel = JapaneseFake  # type: ignore[misc]
        try:
            transcriber = FasterWhisperTranscriber(
                model_name="base",
                models_dir=tmp_path / "models",
            )
            result = transcriber.transcribe(str(media))
        finally:
            faster_whisper.WhisperModel = original  # type: ignore[misc]

        # Japanese is not in the language map → UNKNOWN
        assert result.language is Language.UNKNOWN


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_missing_media_file_raises(
        self, fake_model_class: type[FakeWhisperModel], tmp_path: Path
    ) -> None:
        transcriber = FasterWhisperTranscriber(
            model_name="base",
            models_dir=tmp_path / "models",
        )
        with pytest.raises(TranscriptionError, match="does not exist"):
            transcriber.transcribe(str(tmp_path / "ghost.mp4"))

    def test_empty_media_path_raises(
        self, fake_model_class: type[FakeWhisperModel], tmp_path: Path
    ) -> None:
        transcriber = FasterWhisperTranscriber(
            model_name="base",
            models_dir=tmp_path / "models",
        )
        with pytest.raises(TranscriptionError):
            transcriber.transcribe("")

    def test_whisper_transcribe_failure_translates(
        self, tmp_path: Path
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake")

        class BrokenFake(FakeWhisperModel):
            def __init__(self, model_name: str, **kwargs: Any) -> None:
                super().__init__(model_name, **kwargs)
                self.configure(
                    segments=[],
                    raise_on_transcribe=RuntimeError("audio decode failed"),
                )

        import faster_whisper

        original = faster_whisper.WhisperModel
        faster_whisper.WhisperModel = BrokenFake  # type: ignore[misc]
        try:
            transcriber = FasterWhisperTranscriber(
                model_name="base",
                models_dir=tmp_path / "models",
            )
            with pytest.raises(TranscriptionError, match="audio decode failed"):
                transcriber.transcribe(str(media))
        finally:
            faster_whisper.WhisperModel = original  # type: ignore[misc]

    def test_model_load_failure_translates(
        self, tmp_path: Path
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake")

        class FailingLoad(FakeWhisperModel):
            def __init__(self, model_name: str, **kwargs: Any) -> None:
                raise OSError("model file corrupted")

        import faster_whisper

        original = faster_whisper.WhisperModel
        faster_whisper.WhisperModel = FailingLoad  # type: ignore[misc]
        try:
            transcriber = FasterWhisperTranscriber(
                model_name="base",
                models_dir=tmp_path / "models",
            )
            with pytest.raises(TranscriptionError, match="failed to load"):
                transcriber.transcribe(str(media))
        finally:
            faster_whisper.WhisperModel = original  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Lazy loading
# ---------------------------------------------------------------------------


class TestLazyLoading:
    def test_init_does_not_load_the_model(
        self, fake_model_class: type[FakeWhisperModel], tmp_path: Path
    ) -> None:
        # Construct the transcriber. The fake model class records every
        # construction in `instances`. Before any transcribe() call,
        # the list should be empty.
        FasterWhisperTranscriber(
            model_name="base",
            models_dir=tmp_path / "models",
        )
        instances = getattr(fake_model_class, "instances", [])
        assert len(instances) == 0

    def test_first_transcribe_loads_the_model(
        self, fake_model_class: type[FakeWhisperModel], tmp_path: Path
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake")

        transcriber = FasterWhisperTranscriber(
            model_name="base",
            models_dir=tmp_path / "models",
        )
        transcriber.transcribe(str(media))

        instances = getattr(fake_model_class, "instances", [])
        assert len(instances) == 1
        assert fake_model_class.last_init_kwargs["model_name"] == "base"

    def test_subsequent_transcribe_reuses_model(
        self, fake_model_class: type[FakeWhisperModel], tmp_path: Path
    ) -> None:
        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake")

        transcriber = FasterWhisperTranscriber(
            model_name="base",
            models_dir=tmp_path / "models",
        )
        transcriber.transcribe(str(media))
        transcriber.transcribe(str(media))
        transcriber.transcribe(str(media))

        instances = getattr(fake_model_class, "instances", [])
        assert len(instances) == 1, "model should be loaded only once"


# ---------------------------------------------------------------------------
# Post-corrections
# ---------------------------------------------------------------------------


def _make_fake_with_segments(
    segments: list[FakeSegment], language: str = "fr"
) -> type[FakeWhisperModel]:
    class _Fake(FakeWhisperModel):
        def __init__(self, model_name: str, **kwargs: Any) -> None:
            super().__init__(model_name, **kwargs)
            self.configure(segments=segments, language=language)

    return _Fake


class TestPostCorrections:
    def _transcribe_with(
        self,
        tmp_path: Path,
        segments: list[FakeSegment],
        corrections: list[tuple[str, str]],
    ):
        import faster_whisper

        media = tmp_path / "video.mp4"
        media.write_bytes(b"fake")
        original = faster_whisper.WhisperModel
        faster_whisper.WhisperModel = _make_fake_with_segments(segments)
        try:
            t = FasterWhisperTranscriber(
                model_name="base",
                models_dir=tmp_path / "models",
                post_corrections=corrections,
            )
            return t.transcribe(str(media))
        finally:
            faster_whisper.WhisperModel = original

    def test_corrects_segment_text(self, tmp_path: Path) -> None:
        result = self._transcribe_with(
            tmp_path,
            [FakeSegment(0.0, 2.0, "Lancer CloudCode dans le terminal.")],
            [("CloudCode", "Claude Code")],
        )
        assert result.segments[0].text == "Lancer Claude Code dans le terminal."

    def test_corrects_full_text(self, tmp_path: Path) -> None:
        result = self._transcribe_with(
            tmp_path,
            [FakeSegment(0.0, 2.0, "Lancer CloudCode dans le terminal.")],
            [("CloudCode", "Claude Code")],
        )
        assert "Claude Code" in result.full_text
        assert "CloudCode" not in result.full_text

    def test_corrections_are_case_insensitive(self, tmp_path: Path) -> None:
        result = self._transcribe_with(
            tmp_path,
            [FakeSegment(0.0, 1.0, "mes projets cloud code au terminal.")],
            [("Cloud Code", "Claude Code")],
        )
        assert "Claude Code" in result.segments[0].text
        assert "cloud code" not in result.segments[0].text

    def test_no_corrections_leaves_text_unchanged(self, tmp_path: Path) -> None:
        result = self._transcribe_with(
            tmp_path,
            [FakeSegment(0.0, 1.0, "Cloud Code")],
            [],
        )
        assert result.segments[0].text == "Cloud Code"

    def test_multi_segment_all_corrected(self, tmp_path: Path) -> None:
        result = self._transcribe_with(
            tmp_path,
            [
                FakeSegment(0.0, 1.0, "Cloud Code est utile."),
                FakeSegment(1.0, 2.0, "J'utilise cloud code tous les jours."),
            ],
            [("Cloud Code", "Claude Code")],
        )
        assert all("cloud code" not in s.text.lower() for s in result.segments)
        assert all("Claude Code" in s.text for s in result.segments)
