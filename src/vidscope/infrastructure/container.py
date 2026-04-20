"""Composition root for VidScope.

This module is the single place in the codebase allowed to instantiate
concrete adapters and wire them to their ports. Every other module
receives its dependencies via a :class:`Container` passed through
constructor injection.

Why a composition root?
-----------------------

- **Substitution is trivial.** Tests build a container with a
  :class:`FixedClock` and an ``InMemoryMediaStorage``. Production builds
  one with the real adapters. No mock libraries, no patching.
- **Dependency direction is obvious.** import-linter forbids any layer
  except :mod:`vidscope.infrastructure` from importing
  :mod:`vidscope.adapters`, which makes this module the single point
  where layering rules get to bend.
- **Startup sequencing is explicit.** Want to create the DB only once
  per process? Do it in :func:`build_container`. Want to fail fast on a
  bad config? The container build is the place to raise.

Growth model
------------

Today this container holds ``config``, ``engine``, and a
:class:`SystemClock`. Later tasks extend it:

- T06 wires :class:`MediaStorage`, :class:`UnitOfWorkFactory`, and the
  five repository adapters.
- T07 wires :class:`PipelineRunner`, the five stages, and the use cases.
- S02–S06 plug concrete :class:`Downloader`, :class:`Transcriber`,
  :class:`FrameExtractor`, :class:`Analyzer`, :class:`SearchIndex`.

Every extension adds a field to :class:`Container` and a line to
:func:`build_container`. Nothing else changes anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from vidscope.adapters.config import YamlTaxonomy, YamlVocabularySource
from vidscope.adapters.ffmpeg import FfmpegFrameExtractor
from vidscope.adapters.fs.local_media_storage import LocalMediaStorage
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.adapters.text import RegexLinkExtractor
from vidscope.adapters.vision import HaarcascadeFaceCounter, RapidOcrEngine
from vidscope.adapters.whisper import FasterWhisperTranscriber
from vidscope.adapters.composite import FallbackDownloader
from vidscope.adapters.instaloader import InstaLoaderDownloader
from vidscope.adapters.ytdlp import YtdlpDownloader, YtdlpStatsProbe
from vidscope.infrastructure.analyzer_registry import build_analyzer
from vidscope.infrastructure.config import Config, get_config
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline import PipelineRunner
from vidscope.pipeline.stages import (
    AnalyzeStage,
    FramesStage,
    IndexStage,
    IngestStage,
    MetadataExtractStage,
    StatsStage,
    TranscribeStage,
    VisualIntelligenceStage,
)
from vidscope.ports.clock import Clock
from vidscope.ports.pipeline import (
    Analyzer,
    Downloader,
    FrameExtractor,
    Transcriber,
)
from vidscope.ports.stats_probe import StatsProbe
from vidscope.ports.storage import MediaStorage
from vidscope.ports.taxonomy_catalog import TaxonomyCatalog
from vidscope.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = ["Container", "SystemClock", "build_container"]


class SystemClock:
    """Production :class:`Clock` returning ``datetime.now(timezone.utc)``.

    Tests inject a frozen alternative. This class is module-level (not
    a nested one) so mypy sees it as a named type and import-linter sees
    it as an importable symbol.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Container:
    """Wired application container.

    A :class:`Container` instance is the result of composing every
    adapter and service for a single process. It is immutable after
    construction — if you need a different wiring (tests, alternate
    backends), build a fresh container.

    Fields
    ------
    config:
        Resolved runtime configuration (paths, data dir, db path).
    engine:
        SQLAlchemy Engine bound to the DB. Do not share across
        containers.
    clock:
        Time source. :class:`SystemClock` in production, a frozen
        alternative in tests.
    media_storage:
        :class:`MediaStorage` implementation. In production this is a
        :class:`LocalMediaStorage` rooted at ``config.data_dir``.
    unit_of_work:
        Zero-arg factory that returns a fresh :class:`UnitOfWork`. Every
        use case that mutates the DB calls this to open its own
        transactional scope: ``with container.unit_of_work() as uow:``.
    downloader:
        :class:`Downloader` implementation. S02 wires
        :class:`YtdlpDownloader`.
    pipeline_runner:
        :class:`PipelineRunner` configured with every concrete stage
        registered in :func:`build_container`. Use cases call
        ``container.pipeline_runner.run(ctx)`` to execute the full
        pipeline.
    """

    config: Config
    engine: Engine
    media_storage: MediaStorage
    unit_of_work: UnitOfWorkFactory
    downloader: Downloader
    transcriber: Transcriber
    frame_extractor: FrameExtractor
    analyzer: Analyzer
    stats_probe: StatsProbe
    taxonomy_catalog: TaxonomyCatalog
    stats_stage: StatsStage
    pipeline_runner: PipelineRunner
    clock: Clock = field(default_factory=SystemClock)


def build_container(config: Config | None = None) -> Container:
    """Build a :class:`Container` ready for use.

    Performs the full wiring of every layer:

    1. Resolve configuration (honoring ``VIDSCOPE_DATA_DIR``).
    2. Build the SQLAlchemy engine bound to the configured DB path and
       call :func:`init_db` to idempotently create tables and the FTS5
       virtual table.
    3. Instantiate :class:`LocalMediaStorage` rooted at the data dir.
    4. Instantiate a :class:`YtdlpDownloader`.
    5. Instantiate every pipeline stage (S02: :class:`IngestStage`;
       future slices will append TranscribeStage, FramesStage, etc.).
    6. Build a :class:`PipelineRunner` with the stages, the unit-of-
       work factory, and a :class:`SystemClock`.
    7. Assemble everything into an immutable :class:`Container`.

    Parameters
    ----------
    config:
        Optional pre-built :class:`Config`. When ``None`` (the default),
        the container calls :func:`get_config` which honors the
        ``VIDSCOPE_DATA_DIR`` environment variable.

    Returns
    -------
    Container
        Immutable container instance. Callers should build exactly one
        per process except in tests.
    """
    resolved_config = config if config is not None else get_config()
    engine = build_engine(resolved_config.db_path)
    init_db(engine)

    media_storage = LocalMediaStorage(resolved_config.data_dir)
    clock = SystemClock()

    def _uow_factory() -> UnitOfWork:
        return SqliteUnitOfWork(engine)

    # YtdlpDownloader validates `cookies_file` at init: a misconfigured
    # VIDSCOPE_COOKIES_FILE fails build_container() with a typed
    # IngestError so the operator sees the problem at startup, not on
    # the first ingest. When cookies_file is None (the default) the
    # downloader behaves exactly as it did before S07.
    downloader = FallbackDownloader(
        primary=YtdlpDownloader(cookies_file=resolved_config.cookies_file),
        fallback=InstaLoaderDownloader(cookies_file=resolved_config.cookies_file),
    )
    stats_probe: StatsProbe = YtdlpStatsProbe(cookies_file=resolved_config.cookies_file)
    # StatsStage is standalone — NOT added to pipeline_runner.stages (anti-pitfall M009)
    stats_stage = StatsStage(stats_probe=stats_probe)

    # M010: load the controlled vertical taxonomy from config/taxonomy.yaml
    # at the repo root. The file is required — fail-fast on missing/invalid.
    _taxonomy_path = Path("config") / "taxonomy.yaml"
    if not _taxonomy_path.is_absolute():
        _taxonomy_path = Path.cwd() / _taxonomy_path
    taxonomy_catalog: TaxonomyCatalog = YamlTaxonomy(_taxonomy_path)

    # FasterWhisperTranscriber loads the model lazily on the first
    # transcribe call (S03/D026), so this constructor never triggers
    # a model download. The first `vidscope add` invocation pays
    # the ~150MB cost; subsequent calls reuse the cached model.
    # Vocabulary: YAML seeds + termes DB (titres, hashtags, créateurs).
    # Buildé une fois au démarrage — dynamique vis-à-vis des runs précédents.
    _vocab_path = Path("config") / "vocabulary.yaml"
    if not _vocab_path.is_absolute():
        _vocab_path = Path.cwd() / _vocab_path
    _vocab_source = YamlVocabularySource(_vocab_path, engine=engine)
    _vocab_prompt = _vocab_source.build_prompt()
    _vocab_corrections = _vocab_source.load_corrections()
    _vocab_hotwords = _vocab_source.build_hotwords()

    transcriber = FasterWhisperTranscriber(
        model_name=resolved_config.whisper_model,
        models_dir=resolved_config.models_dir,
        initial_prompt=_vocab_prompt,
        post_corrections=_vocab_corrections,
        hotwords=_vocab_hotwords,
    )

    # FfmpegFrameExtractor checks for the ffmpeg binary lazily at
    # extract_frames time, not at construction. So container build
    # never fails on a missing ffmpeg — only the FramesStage will,
    # and the runner will mark that stage FAILED while keeping
    # ingest+transcribe rows OK. R009 (cross-platform) preserved.
    frame_extractor = FfmpegFrameExtractor()

    # Analyzer is selected by name from the registry (R010). Default
    # is 'heuristic' (zero cost, zero network). M004 will register
    # additional providers without changing this line.
    analyzer = build_analyzer(resolved_config.analyzer_name)

    link_extractor = RegexLinkExtractor()
    ocr_engine = RapidOcrEngine()
    face_counter = HaarcascadeFaceCounter()

    ingest_stage = IngestStage(
        downloader=downloader,
        media_storage=media_storage,
        cache_dir=resolved_config.cache_dir,
        post_corrections=_vocab_corrections,
    )
    transcribe_stage = TranscribeStage(
        transcriber=transcriber,
        media_storage=media_storage,
    )
    frames_stage = FramesStage(
        frame_extractor=frame_extractor,
        media_storage=media_storage,
        cache_dir=resolved_config.cache_dir,
    )
    visual_intelligence_stage = VisualIntelligenceStage(
        ocr_engine=ocr_engine,
        face_counter=face_counter,
        link_extractor=link_extractor,
        media_storage=media_storage,
    )
    analyze_stage = AnalyzeStage(analyzer=analyzer)
    metadata_extract_stage = MetadataExtractStage(link_extractor=link_extractor)
    index_stage = IndexStage()

    pipeline_runner = PipelineRunner(
        stages=[
            ingest_stage,
            transcribe_stage,
            frames_stage,
            visual_intelligence_stage,
            analyze_stage,
            metadata_extract_stage,
            index_stage,
        ],
        unit_of_work_factory=_uow_factory,
        clock=clock,
    )

    return Container(
        config=resolved_config,
        engine=engine,
        media_storage=media_storage,
        unit_of_work=_uow_factory,
        downloader=downloader,
        transcriber=transcriber,
        frame_extractor=frame_extractor,
        analyzer=analyzer,
        stats_probe=stats_probe,
        taxonomy_catalog=taxonomy_catalog,
        stats_stage=stats_stage,
        pipeline_runner=pipeline_runner,
        clock=clock,
    )
