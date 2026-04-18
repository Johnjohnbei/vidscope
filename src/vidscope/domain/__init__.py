"""VidScope domain layer.

The innermost layer of the application. Pure Python — no third-party
runtime dependencies, no I/O, no project imports of outer layers.

Every other layer imports from here; this package imports nothing from
the project. That invariant is enforced mechanically by import-linter
(see ``.importlinter``).
"""

from __future__ import annotations

from vidscope.domain.entities import (
    Analysis,
    Frame,
    PipelineRun,
    Transcript,
    TranscriptSegment,
    Video,
    VideoStats,
    WatchedAccount,
    WatchRefresh,
)
from vidscope.domain.errors import (
    AnalysisError,
    ConfigError,
    CookieAuthError,
    DomainError,
    FrameExtractionError,
    IndexingError,
    IngestError,
    StageCrashError,
    StorageError,
    TranscriptionError,
)
from vidscope.domain.platform_detection import detect_platform
from vidscope.domain.values import (
    Language,
    Platform,
    PlatformId,
    RunStatus,
    StageName,
    VideoId,
)

__all__ = [  # noqa: RUF022 — grouped by concern (entities / errors / values / helpers), not alphabetized
    # entities
    "Analysis",
    "Frame",
    "PipelineRun",
    "Transcript",
    "TranscriptSegment",
    "Video",
    "VideoStats",
    "WatchedAccount",
    "WatchRefresh",
    # errors
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
    # values
    "Language",
    "Platform",
    "PlatformId",
    "RunStatus",
    "StageName",
    "VideoId",
    # helpers
    "detect_platform",
]
