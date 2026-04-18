"""Concrete pipeline stages.

Each stage implements the :class:`~vidscope.ports.pipeline.Stage`
Protocol from :mod:`vidscope.ports.pipeline`. Stages consume the
per-stage service Protocols (Downloader, Transcriber, FrameExtractor,
Analyzer, SearchIndex) via constructor injection. They never import
concrete adapters.

This package lives in :mod:`vidscope.pipeline`, not in
:mod:`vidscope.adapters`, because stages are orchestration logic:
they decide which port to call, in what order, and how to persist
results through a UnitOfWork. The ports do the actual work.
"""

from __future__ import annotations

from vidscope.pipeline.stages.analyze import AnalyzeStage
from vidscope.pipeline.stages.frames import FramesStage
from vidscope.pipeline.stages.index import IndexStage
from vidscope.pipeline.stages.ingest import IngestStage
from vidscope.pipeline.stages.metadata_extract import MetadataExtractStage
from vidscope.pipeline.stages.transcribe import TranscribeStage

__all__ = [
    "AnalyzeStage",
    "FramesStage",
    "IndexStage",
    "IngestStage",
    "MetadataExtractStage",
    "TranscribeStage",
]
