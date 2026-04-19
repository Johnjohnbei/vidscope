"""FasterWhisperTranscriber — faster-whisper implementation of Transcriber.

Wraps :class:`faster_whisper.WhisperModel` behind the Transcriber
Protocol from :mod:`vidscope.ports.pipeline`. Every faster-whisper
exception is translated into a typed
:class:`~vidscope.domain.errors.TranscriptionError`.

Design notes
------------

- **Single import boundary.** ``faster_whisper`` is imported only in
  this file. import-linter forbids any other layer from touching it.
- **Lazy model loading.** The model is NOT loaded in ``__init__``.
  The first call to :meth:`transcribe` loads it. This means
  ``build_container()`` does not trigger a 150MB download just to
  start the CLI — the cost is paid on the first ingest only.
- **Model cache.** ``models_dir`` is passed as ``download_root`` to
  WhisperModel so the model lives under ``<vidscope-data>/models/``,
  not in faster-whisper's default location. Future invocations
  reuse the cached model.
- **VAD filtering.** Voice activity detection is enabled
  (``vad_filter=True``) which strips silence and dramatically
  improves quality for short videos with intro/outro silence.
- **Language detection.** We let faster-whisper detect the language
  automatically. The detected language is mapped to our :class:`Language`
  enum (FRENCH, ENGLISH, UNKNOWN). Anything outside fr/en falls back
  to UNKNOWN — the analyzer in S05 will still run on the text but
  the language column carries the honest signal.
- **CPU-friendly defaults.** ``device='auto'`` lets faster-whisper
  pick CPU on machines without CUDA, ``compute_type='default'`` uses
  int8 on CPU which is the sweet spot for short-form content.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vidscope.domain import (
    Language,
    Transcript,
    TranscriptionError,
    TranscriptSegment,
    VideoId,
)

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

__all__ = ["FasterWhisperTranscriber"]


# faster-whisper detects 100+ languages. We map only the ones our
# pipeline cares about; everything else becomes UNKNOWN.
_LANGUAGE_MAP: dict[str, Language] = {
    "fr": Language.FRENCH,
    "en": Language.ENGLISH,
}


class FasterWhisperTranscriber:
    """Transcriber port implementation backed by faster-whisper.

    Parameters
    ----------
    model_name:
        faster-whisper model name (e.g. ``"base"``, ``"small"``).
        Validated by :func:`vidscope.infrastructure.config._resolve_whisper_model`
        before reaching here.
    models_dir:
        Directory where faster-whisper caches downloaded model weights.
        Passed as ``download_root`` to :class:`WhisperModel`.
    device:
        Device hint for the underlying CTranslate2 backend. Defaults
        to ``"cpu"`` because that's the safe choice for the dev
        machine and the documented baseline (D008). Users with a
        working CUDA install can override to ``"cuda"`` or ``"auto"``.
    compute_type:
        Quantization type. ``"default"`` uses int8 on CPU, float16
        on GPU — the sweet spot for short-form content.
    """

    def __init__(
        self,
        *,
        model_name: str,
        models_dir: Path,
        device: str = "cpu",
        compute_type: str = "int8",
        initial_prompt: str | None = None,
        post_corrections: list[tuple[str, str]] | None = None,
        hotwords: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._models_dir = models_dir
        self._device = device
        self._compute_type = compute_type
        self._initial_prompt = initial_prompt
        self._post_corrections: list[tuple[str, str]] = post_corrections or []
        self._hotwords = hotwords
        self._model: WhisperModel | None = None

    @property
    def model_name(self) -> str:
        """Public read-only accessor for the configured model name."""
        return self._model_name

    def transcribe(self, media_path: str) -> Transcript:
        """Transcribe ``media_path`` and return a domain Transcript.

        The model is loaded lazily on the first call. Subsequent
        calls reuse the cached model. The returned Transcript has
        ``video_id`` set to a placeholder ``VideoId(0)`` — the
        TranscribeStage replaces it with the real video id before
        persisting.

        Raises
        ------
        TranscriptionError
            On any faster-whisper failure (model load failure,
            audio decode error, language detection failure, etc.).
            Always ``retryable=False`` — transcription failures
            usually mean the input is bad or the model can't be
            loaded, neither of which self-heal by retrying.
        """
        if not media_path or not Path(media_path).exists():
            raise TranscriptionError(
                f"media file does not exist: {media_path!r}"
            )

        model = self._ensure_model_loaded()

        try:
            # VAD filter is OFF by default for short-form content:
            # YouTube Shorts and Reels often have such tight pacing
            # that VAD's silence detection strips entire utterances.
            # Users can opt back in via a future config flag.
            segments_iter, info = model.transcribe(
                media_path,
                vad_filter=False,
                beam_size=5,
                initial_prompt=self._initial_prompt,
                hotwords=self._hotwords,
            )
            # faster-whisper returns a generator — drain it eagerly
            # so any underlying decode error surfaces here, not later.
            segments = tuple(
                TranscriptSegment(
                    start=float(seg.start),
                    end=float(seg.end),
                    text=str(seg.text).strip(),
                )
                for seg in segments_iter
            )
        except Exception as exc:
            raise TranscriptionError(
                f"faster-whisper failed on {media_path!r}: {exc}",
                cause=exc,
            ) from exc

        if self._post_corrections:
            segments = tuple(
                TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=_apply_corrections(seg.text, self._post_corrections),
                )
                for seg in segments
            )

        full_text = " ".join(seg.text for seg in segments if seg.text)
        language = _map_language(getattr(info, "language", None))

        return Transcript(
            video_id=VideoId(0),  # placeholder, stage fills the real id
            language=language,
            full_text=full_text,
            segments=segments,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_model_loaded(self) -> WhisperModel:
        """Load the WhisperModel on first call, return the cached
        instance on subsequent calls.

        Wraps the import + constructor in a typed-error block so a
        broken faster-whisper install fails as a TranscriptionError
        rather than a raw ImportError.
        """
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel  # noqa: PLC0415
        except ImportError as exc:
            raise TranscriptionError(
                f"faster-whisper is not installed: {exc}",
                cause=exc,
            ) from exc

        try:
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
                download_root=str(self._models_dir),
            )
        except Exception as exc:
            raise TranscriptionError(
                f"failed to load whisper model {self._model_name!r}: {exc}",
                cause=exc,
            ) from exc

        return self._model


def _apply_corrections(text: str, corrections: list[tuple[str, str]]) -> str:
    for wrong, right in corrections:
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)
    return text


def _map_language(detected: Any) -> Language:
    """Map a faster-whisper language code to our :class:`Language` enum.

    Anything outside fr/en becomes UNKNOWN — the analyzer can still
    run on the text but the language column carries the honest signal.
    """
    if detected is None:
        return Language.UNKNOWN
    code = str(detected).lower().strip()
    return _LANGUAGE_MAP.get(code, Language.UNKNOWN)
