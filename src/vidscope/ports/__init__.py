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
from vidscope.ports.pipeline import (
    Analyzer,
    ChannelEntry,
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
    FrameRepository,
    PipelineRunRepository,
    TagRepository,
    TranscriptRepository,
    VideoRepository,
    VideoStatsRepository,
    VideoTrackingRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)
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
    "Downloader",
    "FrameExtractor",
    "FrameRepository",
    "IngestOutcome",
    "MediaStorage",
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
