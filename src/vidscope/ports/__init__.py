"""VidScope ports layer.

Protocol-only interfaces describing everything the application needs
from the outside world: persistence, media storage, download, transcribe,
frame extraction, analysis, search, and time.

Every Protocol in this package is decorated with ``@runtime_checkable``
so tests can assert adapter conformance. No implementation lives here —
concrete adapters live under :mod:`vidscope.adapters`.

This package imports only from :mod:`vidscope.domain` (and stdlib
``typing``). The import-linter contract in ``.importlinter`` enforces
that rule mechanically.
"""

from __future__ import annotations

from vidscope.ports.clock import Clock
from vidscope.ports.link_extractor import LinkExtractor, RawLink
from vidscope.ports.pipeline import (
    Analyzer,
    ChannelEntry,
    CreatorInfo,
    Downloader,
    FrameExtractor,
    IngestOutcome,
    PipelineContext,
    ProbeResult,
    ProbeStatus,
    SearchIndex,
    SearchResult,
    Stage,
    StageResult,
    Transcriber,
)
from vidscope.ports.repositories import (
    AnalysisRepository,
    CreatorRepository,
    FrameRepository,
    HashtagRepository,
    LinkRepository,
    MentionRepository,
    PipelineRunRepository,
    TranscriptRepository,
    VideoRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)
from vidscope.ports.storage import MediaStorage
from vidscope.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "AnalysisRepository",
    "Analyzer",
    "ChannelEntry",
    "Clock",
    "CreatorInfo",
    "CreatorRepository",
    "Downloader",
    "FrameExtractor",
    "FrameRepository",
    "HashtagRepository",
    "IngestOutcome",
    "LinkExtractor",
    "LinkRepository",
    "MediaStorage",
    "MentionRepository",
    "PipelineContext",
    "PipelineRunRepository",
    "ProbeResult",
    "ProbeStatus",
    "RawLink",
    "SearchIndex",
    "SearchResult",
    "Stage",
    "StageResult",
    "Transcriber",
    "TranscriptRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "VideoRepository",
    "WatchAccountRepository",
    "WatchRefreshRepository",
]
