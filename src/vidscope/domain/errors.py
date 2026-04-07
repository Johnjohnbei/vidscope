"""Typed error hierarchy for the VidScope domain.

Every stage of the pipeline, every adapter, and every use case raises one
of these — never a bare :class:`Exception`. The :class:`PipelineRunner`
dispatches on the exception type to decide whether to retry, fail fast,
or surface a user-actionable message.

All domain errors carry three structured fields:

- ``stage``: which :class:`~vidscope.domain.values.StageName` triggered it
  (``None`` for non-stage errors like :class:`ConfigError`)
- ``cause``: the original exception that was wrapped, if any
- ``retryable``: hint for the runner — if ``True``, the runner is allowed
  to re-execute the same stage on a subsequent invocation

Design rules
------------
- ``DomainError`` does not inherit from :class:`Exception` directly — it
  inherits via Python's native exception machinery so ``raise`` works.
- Subclasses override the default ``retryable`` flag to encode the usual
  behavior of that failure mode (network issues are retryable, config
  errors are not).
- The structured fields are set via ``__init__`` keyword arguments, not
  attribute assignment, so mypy sees them on the instance.
- The error message passed to ``super().__init__`` is what ``str(err)``
  returns; callers can rely on it being human-readable.
"""

from __future__ import annotations

from vidscope.domain.values import StageName

__all__ = [
    "AnalysisError",
    "ConfigError",
    "CookieAuthError",
    "DomainError",
    "FrameExtractionError",
    "IndexingError",
    "IngestError",
    "StageCrashError",
    "StorageError",
    "TranscriptionError",
]


class DomainError(Exception):
    """Base class for every VidScope-raised error.

    Parameters
    ----------
    message:
        Human-readable explanation. Shown to the user on the CLI when the
        error bubbles up.
    stage:
        Pipeline stage this error belongs to. Use ``None`` for errors that
        happen outside any stage (configuration, startup checks, etc.).
    cause:
        Optional underlying exception that triggered this one. Stored for
        diagnostics; not included in ``str(err)`` unless callers want it.
    retryable:
        Whether the pipeline runner is allowed to retry the failing stage
        on a subsequent invocation. Defaults are set by each subclass.
    """

    default_retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        stage: StageName | None = None,
        cause: BaseException | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.stage: StageName | None = stage
        self.cause: BaseException | None = cause
        self.retryable: bool = (
            retryable if retryable is not None else self.default_retryable
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"message={self.message!r}, "
            f"stage={self.stage}, "
            f"retryable={self.retryable})"
        )


class IngestError(DomainError):
    """Raised when yt-dlp (or any future downloader) fails.

    Retryable by default because most ingest failures are transient
    (network hiccup, rate limit, upstream patch in flight).
    """

    default_retryable = True

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(
            message, stage=StageName.INGEST, cause=cause, retryable=retryable
        )


class CookieAuthError(IngestError):
    """Raised when the downloader fails because cookies are missing or expired.

    Distinct subclass of :class:`IngestError` so the CLI can show a
    targeted remediation message pointing at ``vidscope cookies test``
    instead of the generic ingest failure message.

    Always non-retryable: a cookie auth failure won't self-heal — the
    user has to refresh their browser session and re-export the cookies
    file.
    """

    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, cause=cause, retryable=False)
        self.url = url


class TranscriptionError(DomainError):
    """Raised when faster-whisper (or any future transcriber) fails.

    Not retryable by default: transcription failures usually mean the audio
    is corrupt, the model can't be loaded, or the language isn't supported
    — none of which self-heal by retrying.
    """

    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(
            message, stage=StageName.TRANSCRIBE, cause=cause, retryable=retryable
        )


class FrameExtractionError(DomainError):
    """Raised when ffmpeg (or any future frame extractor) fails.

    Not retryable: ffmpeg failures almost always mean the input is malformed
    or the binary is missing, which a retry cannot fix.
    """

    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(
            message, stage=StageName.FRAMES, cause=cause, retryable=retryable
        )


class AnalysisError(DomainError):
    """Raised when the analyzer provider fails.

    Retryable for LLM-backed providers (429s, transient 5xx), not retryable
    for the default heuristic provider (which should never fail at runtime).
    Callers override the default per-provider.
    """

    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(
            message, stage=StageName.ANALYZE, cause=cause, retryable=retryable
        )


class IndexingError(DomainError):
    """Raised when FTS5 insertion fails.

    Not retryable by default: an FTS5 write failure means the DB is in a
    broken state that needs human attention, not automated retries.
    """

    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(
            message, stage=StageName.INDEX, cause=cause, retryable=retryable
        )


class StorageError(DomainError):
    """Raised by the :class:`MediaStorage` port when a filesystem/object-store
    operation fails.

    Not associated with a specific stage because storage is cross-cutting.
    Not retryable by default — most storage failures are permissions or
    disk-full issues, which need human action.
    """

    default_retryable = False


class ConfigError(DomainError):
    """Raised when configuration is invalid or the environment is unusable.

    Never retryable. Typically raised during container construction, long
    before any stage runs.
    """

    default_retryable = False


class StageCrashError(DomainError):
    """Wrapper raised by :class:`PipelineRunner` around an unexpected
    non-:class:`DomainError` exception bubbling out of a stage.

    Its existence is itself a bug signal: stages are supposed to translate
    every failure into a typed domain error. When this is raised, something
    in the adapter layer leaked.

    Carries the original traceback in ``cause`` so operators can diagnose.
    """

    default_retryable = False
