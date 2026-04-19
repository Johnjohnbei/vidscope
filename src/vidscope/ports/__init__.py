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
from vidscope.ports.exporter import Exporter
from vidscope.ports.ocr_engine import FaceCounter, OcrEngine, OcrLine
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
    CollectionRepository,
    CreatorRepository,
    FrameRepository,
    FrameTextRepository,
    HashtagRepository,
    LinkRepository,
    MentionRepository,
    PipelineRunRepository,
    TagRepository,
    TranscriptRepository,
    VideoRepository,
    VideoStatsRepository,
    VideoTrackingRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)
from vidscope.ports.link_extractor import LinkExtractor, RawLink
from vidscope.ports.stats_probe import StatsProbe
from vidscope.ports.storage import MediaStorage
from vidscope.ports.taxonomy_catalog import TaxonomyCatalog
from vidscope.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "AnalysisRepository",
    "Analyzer",
    "ChannelEntry",
    "Clock",
    "CollectionRepository",
    "CreatorInfo",
    "CreatorRepository",
    "Downloader",
    "Exporter",
    "FaceCounter",
    "FrameExtractor",
    "FrameRepository",
    "FrameTextRepository",
    "HashtagRepository",
    "IngestOutcome",
    "LinkExtractor",
    "LinkRepository",
    "RawLink",
    "MediaStorage",
    "MentionRepository",
    "OcrEngine",
    "OcrLine",
    "PipelineContext",
    "PipelineRunRepository",
    "ProbeResult",
    "ProbeStatus",
    "SearchIndex",
    "SearchResult",
    "Stage",
    "StageResult",
    "StatsProbe",
    "TagRepository",
    "TaxonomyCatalog",
    "Transcriber",
    "TranscriptRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "VideoRepository",
    "VideoStatsRepository",
    "VideoTrackingRepository",
    "WatchAccountRepository",
    "WatchRefreshRepository",
]
