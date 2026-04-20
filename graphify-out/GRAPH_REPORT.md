# Graph Report - src  (2026-04-20)

## Corpus Check
- 145 files · ~50,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1983 nodes · 3799 edges · 59 communities detected
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 1510 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `VidScope ports layer.  Protocol-only interfaces describing everything the appl` - 154 edges
2. `UnitOfWork` - 91 edges
3. `StorageError` - 90 edges
4. `StageName` - 88 edges
5. `Platform` - 73 edges
6. `ContentType` - 67 edges
7. `SentimentLabel` - 67 edges
8. `TrackingStatus` - 67 edges
9. `Language` - 67 edges
10. `RunStatus` - 67 edges

## Surprising Connections (you probably didn't know these)
- `YAML-backed :class:`TaxonomyCatalog` implementation.  Loads ``config/taxonomy.` --uses--> `TaxonomyCatalog`  [INFERRED]
  src\vidscope\adapters\config\yaml_taxonomy.py → src\vidscope\ports\taxonomy_catalog.py
- `Concrete :class:`TaxonomyCatalog` reading a YAML file.      The file must be a` --uses--> `TaxonomyCatalog`  [INFERRED]
  src\vidscope\adapters\config\yaml_taxonomy.py → src\vidscope\ports\taxonomy_catalog.py
- `Filesystem implementation of :class:`MediaStorage`.      Parameters     --------` --uses--> `StorageError`  [INFERRED]
  src\vidscope\adapters\fs\local_media_storage.py → src\vidscope\domain\errors.py
- `SQLite implementation of :class:`TagRepository` (M011/S02/R057).  Tag names ar` --uses--> `StorageError`  [INFERRED]
  src\vidscope\adapters\sqlite\tag_repository.py → src\vidscope\domain\errors.py
- `Lowercase + strip. Empty result is a domain error (caller raises).` --uses--> `StorageError`  [INFERRED]
  src\vidscope\adapters\sqlite\tag_repository.py → src\vidscope\domain\errors.py

## Communities

### Community 0 - "Clock Port Infrastructure"
Cohesion: 0.01
Nodes (246): Clock, Clock port.  Every place in the codebase that needs the current time goes throug, Abstracts "what time is it now" so tests can inject a fixed clock.      Implemen, Return the current time as a timezone-aware ``datetime`` in UTC., FallbackDownloader, Composite Downloader adapters.  :class:`FallbackDownloader` wraps a primary and, Tries *primary*; falls back to *fallback* on specific error messages.      Param, Config (+238 more)

### Community 1 - "Analysis SQLite Repository"
Cohesion: 0.01
Nodes (140): _analysis_to_row(), AnalysisRepositorySQLite, _ensure_utc(), SQLite implementation of :class:`AnalysisRepository`., Repository for :class:`Analysis` backed by SQLite., Return video ids whose most-recent analysis matches the given filters., _row_to_analysis(), CollectionRepositorySQLite (+132 more)

### Community 2 - "Export Pipeline (CSV/JSON/MD)"
Cohesion: 0.04
Nodes (76): CsvExporter, CSV library exporter (M011/S04/R059).  Flat CSV via stdlib ``csv.DictWriter``., Write export records as a flat CSV with ``|`` multi-value separator., Exporter, Port for library export adapters (M011/S04/R059).  Stdlib only. Concrete imple, Write a list of export records to disk or stdout.      Implementors receive a, Serialise ``records``.          When ``out`` is ``None``, write to stdout. Whe, VidScope ports layer.  Protocol-only interfaces describing everything the appl (+68 more)

### Community 3 - "Domain Entities"
Cohesion: 0.12
Nodes (90): Analysis, Collection, Creator, Frame, FrameText, Hashtag, Link, Mention (+82 more)

### Community 4 - "Analyzer Registry"
Cohesion: 0.04
Nodes (73): build_analyzer(), _build_anthropic(), _build_groq(), _build_heuristic_v2(), _build_nvidia(), _build_openai(), _build_openrouter(), Analyzer registry — picks an Analyzer implementation by name.  Implements R010 (+65 more)

### Community 5 - "Collection Use Cases"
Cohesion: 0.04
Nodes (59): AddToCollectionUseCase, CollectionSummary, CreateCollectionUseCase, ListCollectionsUseCase, Collection use cases (M011/S02/R057).  4 use cases operating on the collection, Row used by `vidscope collection list`.      ``video_count`` is the exact coun, Create a new named collection. Raises on duplicate name., Add a video to a collection (by collection name). (+51 more)

### Community 6 - "Creator CLI Commands"
Cohesion: 0.04
Nodes (67): creator_videos(), list_creators(), _parse_platform(), `vidscope creator` sub-commands — show, list, videos., List creators in the library., List videos ingested from a specific creator., Show the full profile for a creator identified by handle., show_creator() (+59 more)

### Community 7 - "Entity Layer (Domain)"
Cohesion: 0.03
Nodes (86): Analysis Entity, Collection Entity, Creator Entity, Frame Entity, FrameText Entity, Hashtag Entity, Link Entity, Mention Entity (+78 more)

### Community 8 - "SQLite Adapters & Gaps"
Cohesion: 0.04
Nodes (71): AnalysisRepositorySQLite, Gap: frames.video_id FK would need carousel_item_id extension for per-slide frames, Gap: videos table lacks media_type/is_carousel/parent_id for carousel support, CollectionRepositorySQLite, CreatorRepositorySQLite, FrameRepositorySQLite, FrameTextRepositorySQLite, HashtagRepositorySQLite (+63 more)

### Community 9 - "Downloader Adapters (yt-dlp)"
Cohesion: 0.05
Nodes (56): CookieAuthError domain error, IngestError domain error, Platform enum, YtdlpDownloader, _bool_or_none(), _build_creator_info(), _detect_media_type_and_paths(), _download_images() (+48 more)

### Community 10 - "Cookies Use Cases"
Cohesion: 0.1
Nodes (44): clear(), ClearCookiesResult, ClearCookiesUseCase, CookiesProbeResult, CookiesProbeUseCase, CookiesStatus, _default_cookies_path(), from_browser() (+36 more)

### Community 11 - "Pipeline Stages Core"
Cohesion: 0.08
Nodes (41): Analysis domain entity, AnalyzeStage, Analyzer port, Frame domain entity, FrameExtractor port, FramesStage, IndexStage, Downloader port (+33 more)

### Community 12 - "OCR & Vision Adapters"
Cohesion: 0.09
Nodes (22): FaceCounter, OcrEngine, OcrLine, OCR + face-count ports (M008/R047, R049).  Both Protocols are pure — implement, One line of OCR-extracted text.      ``text`` is the raw string as reported by, OCR engine port. Default implementation:     :class:`~vidscope.adapters.vision., Return OCR lines above ``min_confidence`` found in         the image at ``image, Face-count port. Default implementation:     :class:`~vidscope.adapters.vision. (+14 more)

### Community 13 - "Heuristic Analyzer v2"
Cohesion: 0.1
Nodes (18): _actionability_score(), _build_reasoning(), _detect_content_type(), _estimate_duration(), HeuristicAnalyzerV2, _information_density(), _novelty_score(), _production_quality() (+10 more)

### Community 14 - "Frames & Transcription"
Cohesion: 0.08
Nodes (27): Frame domain entity, FrameExtractionError domain error, Transcript domain entity, TranscriptionError domain error, FfmpegFrameExtractor, FfmpegFrameExtractor.extract_frames(), Default FPS=0.2 (1 frame per 5s), Output template frame_%04d.jpg (+19 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (25): _backoff_seconds(), build_messages(), call_with_retry(), make_analysis(), _parse_bool_flag(), _parse_content_type(), parse_llm_json(), _parse_reasoning() (+17 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (16): LinkExtractor, LinkExtractor port.  Extracts URLs from arbitrary text (video description, tra, One URL extracted from text.      ``url`` is the raw string as captured (case, Pure URL extractor — no I/O.      The default implementation in :mod:`vidscope, Extract URLs from ``text``. Returns empty list when none.          ``source``, RawLink, MetadataExtractStage, MetadataExtractStage — fifth stage of the pipeline (M007/S03).  Extracts URLs (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (16): CreatorRepository, Persistence for :class:`Creator` rows (M006)., Insert or update the row matching ``(platform, platform_user_id)``., Return the creator by primary key, or None., Return the creator matching ``(platform, platform_user_id)``, or None., Persistence for :class:`Creator` rows (M006)., Insert or update the row matching ``(platform, platform_user_id)``., Return the creator by primary key, or None. (+8 more)

### Community 18 - "Community 18"
Cohesion: 0.14
Nodes (12): _deduplicate(), _pack_into_budget(), YamlVocabularySource — construit l'initial_prompt Whisper depuis vocabulary.yaml, Lit et parse vocabulary.yaml. Retourne None si absent ou invalide., Requêtes légères en lecture seule sur la bibliothèque DB., Déduplique en préservant l'ordre (clé = lowercase)., Assemble les termes séparés par ', ' jusqu'à ``max_chars``., Construit un initial_prompt Whisper depuis YAML + DB.      Parameters     ------ (+4 more)

### Community 19 - "Community 19"
Cohesion: 0.19
Nodes (15): `vidscope show <id>` — show the full record for a video id., Render on-screen text section (M008)., Render on-screen text section (M008)., D-05: display latest stats snapshot + computed velocity., D-05: display latest stats snapshot + computed velocity., Show the full domain record for one video id., _render_frame_texts(), _render_stats() (+7 more)

### Community 20 - "Community 20"
Cohesion: 0.18
Nodes (15): ListTrendingUseCase, ListTrendingUseCase — rank videos by views_velocity_24h on a time window.  Sca, One row in the vidscope trending output., Rank videos by views_velocity_24h on the given time window.      Scalability (, Return up to ``limit`` trending videos ranked by views_velocity_24h., TrendingEntry, _parse_platform(), _parse_window() (+7 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (11): PipelineRunner, Generic pipeline runner.  Takes a list of :class:`Stage` implementations and run, Execute every stage in order against ``ctx``.          Returns a :class:`RunResu, Execute a single stage inside its own transactional UoW., Translate a stage's string name to a :class:`StageName` enum.      Stages declar, Outcome of one stage execution as seen by the runner., Aggregate result of running a pipeline over a context.      ``success`` is ``Tru, Runs a sequence of stages against a shared pipeline context.      Construction t (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (14): _build_media_key(), _correct(), IngestStage, IngestStage — first stage of the pipeline.  Orchestrates three ports to turn a, Download the video, store the media file, and upsert the         videos row. Mu, Download the video, store the media file, and upsert the         videos row. Mu, Return the stable :class:`MediaStorage` key for a downloaded file.      Layout, Return the stable :class:`MediaStorage` key for a downloaded file.      Layout (+6 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (12): LinkRepository, Persistence for :class:`Link` rows (M007)., Insert links for ``video_id`` and return them with ids populated., Return links for ``video_id``, optionally filtered by ``source``., Persistence for :class:`Link` rows (M007)., Return True if at least one link exists for ``video_id``., Insert links for ``video_id`` and return them with ids populated., Return links for ``video_id``, optionally filtered by ``source``. (+4 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (14): _build_summary(), _compute_score(), HeuristicAnalyzer, _is_meaningful_word(), HeuristicAnalyzer — pure-Python zero-cost default analyzer.  Implements the :cla, Split ``text`` into lowercase word tokens., Return True for tokens worth counting as keyword candidates.      Excludes stopw, Return the ``n`` most frequent tokens, ties broken by first     appearance order (+6 more)

### Community 25 - "Community 25"
Cohesion: 0.15
Nodes (13): `vidscope suggest <id>` — propose related videos by keyword overlap., Suggest related videos from the library using keyword overlap.      Ranks candid, _jaccard(), SuggestRelatedUseCase — keyword-overlap-based related-video suggestion.  Given a, Return (Jaccard score, sorted matched keywords) for two sets.      Jaccard = |a, One related-video entry returned by SuggestRelatedUseCase., Result of a suggest_related call.      ``source_video_id`` is the requested vide, Return the top N videos related to a source video by keyword overlap. (+5 more)

### Community 26 - "Community 26"
Cohesion: 0.17
Nodes (13): add_command(), `vidscope add <url>` — ingest a video from a public URL., Run the full ingest pipeline for a single URL.      In S02 this downloads the me, Pretty-print an :class:`IngestResult` as a rich :class:`Panel`.      Shared betw, _render_result_panel(), IngestResult, IngestVideoUseCase, Ingest a video from a URL.  The primary user-facing operation. In S02 this is a (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.17
Nodes (12): ExplainAnalysisResult, ExplainAnalysisUseCase, ExplainAnalysisUseCase -- returns video + latest analysis for `vidscope explain`, Result of :meth:`ExplainAnalysisUseCase.execute`.      ``found`` is ``False``, Return the latest analysis for ``video_id`` -- powers `vidscope explain`., explain_command(), _fmt_bool(), _fmt_enum() (+4 more)

### Community 28 - "Community 28"
Cohesion: 0.21
Nodes (6): _normalize(), SQLite implementation of :class:`TagRepository` (M011/S02/R057).  Tag names ar, Lowercase + strip. Empty result is a domain error (caller raises)., Repository for :class:`Tag` and tag_assignments backed by SQLite., _row_to_tag(), TagRepositorySQLite

### Community 29 - "Community 29"
Cohesion: 0.18
Nodes (10): _parse_status(), `vidscope review <video_id> --status X [--star/--unstar] [--note TEXT] [--clear-, Set workflow overlay (status, starred, notes) on a video., review_command(), SetVideoTrackingUseCase — M011/S01/R056.  Writes a user workflow overlay for a, Outcome of :class:`SetVideoTrackingUseCase.execute`., Upsert the workflow overlay for a single video., Set or update the tracking row for ``video_id``.          Parameters (+2 more)

### Community 30 - "Community 30"
Cohesion: 0.19
Nodes (8): _apply_corrections(), FasterWhisperTranscriber, _map_language(), FasterWhisperTranscriber — faster-whisper implementation of Transcriber.  Wraps, Transcribe ``media_path`` and return a domain Transcript.          The model is, Load the WhisperModel on first call, return the cached         instance on subse, Map a faster-whisper language code to our :class:`Language` enum.      Anything, Transcriber port implementation backed by faster-whisper.      Parameters     --

### Community 31 - "Community 31"
Cohesion: 0.17
Nodes (10): VideoStats domain entity, YtdlpStatsProbe, _int_or_none(), probe-never-raises contract (T-PROBE-01), YtdlpStatsProbe.probe_stats(), YtdlpStatsProbe — yt-dlp implementation of the StatsProbe port.  Wraps ``yt_dl, Return ``value`` cast to ``int``, or ``None`` if not safely castable.      Acc, StatsProbe port implementation backed by yt-dlp.      Parameters     -------- (+2 more)

### Community 32 - "Community 32"
Cohesion: 0.18
Nodes (9): GetStatusResult, GetStatusUseCase, Return the last N pipeline runs — powers ``vidscope status``.  The status comman, List of the most recent pipeline runs.      ``runs`` is ordered newest-first. An, Return the most recent pipeline runs and quick aggregate counts., Return the ``limit`` most recent pipeline runs newest-first.          ``limit``, `vidscope status` — show the last N pipeline runs., Show the last N pipeline runs and quick aggregate counts. (+1 more)

### Community 33 - "Community 33"
Cohesion: 0.18
Nodes (9): links_command(), `vidscope links <id>` — list extracted URLs for a video., List every URL extracted from a video's description + transcript., ListLinksResult, ListLinksUseCase, List extracted links for a video — powers ``vidscope links <id>``., Outcome of :meth:`ListLinksUseCase.execute`.      ``found`` is ``False`` when, Return every :class:`Link` for a video, optionally filtered by source. (+1 more)

### Community 34 - "Community 34"
Cohesion: 0.18
Nodes (9): list_command(), `vidscope list` — list recently ingested videos., List the most recently ingested videos., ListVideosResult, ListVideosUseCase, List recently ingested videos — powers ``vidscope list``., Result of :meth:`ListVideosUseCase.execute`.      ``videos`` is ordered newest-f, Return the most recently ingested videos and the total count. (+1 more)

### Community 35 - "Community 35"
Cohesion: 0.17
Nodes (8): AnalyzeStage, AnalyzeStage — fourth stage of the pipeline.  Reads the transcript produced by t, Fourth stage of the pipeline — produce a structured analysis., Fourth stage of the pipeline — produce a structured analysis., Return True if any analysis already exists for the video., Return True if analysis can be skipped.          IMAGE and CAROUSEL have no tran, Read the transcript, analyze it, persist the result.          Mutates ``ctx.anal, Read the transcript, analyze it, persist the result.          Mutates ``ctx.anal

### Community 36 - "Community 36"
Cohesion: 0.17
Nodes (8): FramesStage, FramesStage — third stage of the pipeline.  Reads ``videos.media_key`` from the, Third stage of the pipeline — extract frames from media., Third stage of the pipeline — extract frames from media., Return True if frames already exist for the video., Return True if frames already exist for the video., Extract frames and persist them with stable storage keys.          Mutates ``ctx, Extract frames and persist them with stable storage keys.          Mutates ``ctx

### Community 37 - "Community 37"
Cohesion: 0.17
Nodes (8): TranscribeStage — second stage of the pipeline.  Reads ``videos.media_key`` from, Second stage of the pipeline — produce a transcript from media., Second stage of the pipeline — produce a transcript from media., Return True if a transcript already exists for the video.          Cheap DB quer, Return True if transcription is not needed or already done.          Images and, Transcribe the video's media file and persist the transcript.          Mutates `, Transcribe the video's media file and persist the transcript.          Mutates `, TranscribeStage

### Community 38 - "Community 38"
Cohesion: 0.17
Nodes (9): HashtagRepository, Persistence for :class:`Hashtag` rows (M007)., Delete existing hashtags for ``video_id`` and insert ``tags``., Return hashtags for ``video_id`` ordered by tag ascending., Return video_ids that have a hashtag matching ``tag`` (lowercased)., Persistence for :class:`Hashtag` rows (M007)., Delete existing hashtags for ``video_id`` and insert ``tags``., Return hashtags for ``video_id`` ordered by tag ascending. (+1 more)

### Community 39 - "Community 39"
Cohesion: 0.2
Nodes (9): acquire_container(), fail_system(), fail_user(), handle_domain_errors(), Shared helpers for CLI commands.  Keeps every ``commands/*.py`` file tiny and fo, Build the :class:`Container` once per CLI invocation.      This is the only func, Print a red error message and return a :class:`typer.Exit`.      Callers do ``ra, Same as :func:`fail_user` but uses exit code 2 (system error). (+1 more)

### Community 40 - "Community 40"
Cohesion: 0.2
Nodes (9): RawLink port type, RegexLinkExtractor, Pass 2: bare-domain regex (restricted TLD list), RegexLinkExtractor.extract() two-pass, Pass 1: scheme-explicit URL regex, normalize_url(), Pure-Python URL normalization — stdlib only.  Used by :class:`RegexLinkExtract, Return the canonical normalized form of ``url``.      See module docstring for (+1 more)

### Community 41 - "Community 41"
Cohesion: 0.25
Nodes (4): _load_and_validate(), YAML-backed :class:`TaxonomyCatalog` implementation.  Loads ``config/taxonomy., Concrete :class:`TaxonomyCatalog` reading a YAML file.      The file must be a, YamlTaxonomy

### Community 42 - "Community 42"
Cohesion: 0.25
Nodes (5): HaarcascadeFaceCounter, OpenCV Haarcascade-based FaceCounter adapter (M008/R049).  Wraps ``cv2.Cascade, FaceCounter implementation backed by OpenCV haarcascade., Return (cv2 module, cascade instance) or ``None``., Return the number of frontal faces in the image, or         ``0`` when any step

### Community 43 - "Community 43"
Cohesion: 0.25
Nodes (5): IndexStage, IndexStage — fifth and final stage of the pipeline.  Writes the transcript and a, Fifth stage of the pipeline — populate the FTS5 search index., Always False: re-indexing is cheap and idempotent., Index the latest transcript and analysis summary for the video.          Raises

### Community 44 - "Community 44"
Cohesion: 0.29
Nodes (4): FfmpegFrameExtractor, FfmpegFrameExtractor — ffmpeg implementation of FrameExtractor.  Wraps the ``ffm, FrameExtractor port implementation backed by the ffmpeg CLI.      Parameters, Extract up to ``max_frames`` frames from ``media_path`` and         return Frame

### Community 45 - "Community 45"
Cohesion: 0.4
Nodes (3): main(), Typer entry point for ``vidscope``.  Builds the root :class:`typer.Typer` app,, Root callback — accepts global options like ``--version``.

### Community 46 - "Community 46"
Cohesion: 0.5
Nodes (4): capture_platform_cookies(), Playwright-based cookie capture for gated platforms (M012/auth extra).  Opens a, Open a browser, wait for the user to log in, capture and save cookies.      Para, _write_netscape()

### Community 47 - "Community 47"
Cohesion: 0.5
Nodes (3): doctor_command(), `vidscope doctor` — run startup checks and print a report., Run every startup check and print a rich table.      Exit codes     ----------

### Community 48 - "Community 48"
Cohesion: 0.5
Nodes (3): `vidscope mcp ...` subcommands.  Currently exposes only ``vidscope mcp serve`` w, Start the vidscope MCP server on stdio.      Exposes every vidscope use case as, serve()

### Community 49 - "Community 49"
Cohesion: 0.5
Nodes (3): build_engine(), SQLAlchemy Engine factory for SQLite.  This module is the single place in the co, Return a SQLAlchemy Engine bound to ``db_path``.      The engine attaches a ``co

### Community 50 - "Community 50"
Cohesion: 0.5
Nodes (4): StorageError domain error, LocalMediaStorage, LocalMediaStorage.store() atomic copy, Path traversal guard (_resolve_safe)

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Stopword lists for the heuristic analyzer.  Minimal French + English stopword se

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (2): LinkExtractor Protocol, RawLink TypedDict

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Public read-only accessor for the configured model name.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): TagName NewType

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): CollectionName NewType

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): IngestOutcome (fields: platform, platform_id, url, media_path, title, author, duration, upload_date, view_count, creator_info, description, hashtags, mentions, music_track, music_artist)

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): CookieAuthError translation

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): watch_refreshes Table

## Knowledge Gaps
- **532 isolated node(s):** `YamlVocabularySource — construit l'initial_prompt Whisper depuis vocabulary.yaml`, `Construit un initial_prompt Whisper depuis YAML + DB.      Parameters     ------`, `Retourne les hotwords sous forme de chaîne pour faster-whisper.          Les hot`, `Retourne la liste (wrong, right) depuis la section ``corrections``.          Uti`, `Retourne une chaîne de termes séparés par des virgules, ou None.          Priori` (+527 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 51`** (2 nodes): `stopwords.py`, `Stopword lists for the heuristic analyzer.  Minimal French + English stopword se`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `LinkExtractor Protocol`, `RawLink TypedDict`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Public read-only accessor for the configured model name.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `TagName NewType`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `CollectionName NewType`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `IngestOutcome (fields: platform, platform_id, url, media_path, title, author, duration, upload_date, view_count, creator_info, description, hashtags, mentions, music_track, music_artist)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `CookieAuthError translation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `watch_refreshes Table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `VidScope ports layer.  Protocol-only interfaces describing everything the appl` connect `Export Pipeline (CSV/JSON/MD)` to `Clock Port Infrastructure`, `Analysis SQLite Repository`, `Domain Entities`, `Analyzer Registry`, `Collection Use Cases`, `Creator CLI Commands`, `Downloader Adapters (yt-dlp)`, `OCR & Vision Adapters`, `Heuristic Analyzer v2`, `Community 16`, `Community 17`, `Community 18`, `Community 19`, `Community 20`, `Community 21`, `Community 22`, `Community 23`, `Community 24`, `Community 25`, `Community 26`, `Community 27`, `Community 30`, `Community 31`, `Community 32`, `Community 34`, `Community 35`, `Community 36`, `Community 37`, `Community 38`, `Community 41`, `Community 42`, `Community 43`, `Community 44`?**
  _High betweenness centrality (0.626) - this node is a cross-community bridge._
- **Why does `StorageError` connect `Analysis SQLite Repository` to `Clock Port Infrastructure`, `Export Pipeline (CSV/JSON/MD)`, `Domain Entities`, `Collection Use Cases`, `Community 28`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `DomainError` connect `Collection Use Cases` to `Analysis SQLite Repository`, `Export Pipeline (CSV/JSON/MD)`, `Domain Entities`, `Analyzer Registry`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 153 inferred relationships involving `VidScope ports layer.  Protocol-only interfaces describing everything the appl` (e.g. with `YamlTaxonomy` and `YamlVocabularySource`) actually correct?**
  _`VidScope ports layer.  Protocol-only interfaces describing everything the appl` has 153 INFERRED edges - model-reasoned connections that need verification._
- **Are the 86 inferred relationships involving `UnitOfWork` (e.g. with `VidScope ports layer.  Protocol-only interfaces describing everything the appl` and `SystemClock`) actually correct?**
  _`UnitOfWork` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Are the 87 inferred relationships involving `StorageError` (e.g. with `VidScope ports layer.  Protocol-only interfaces describing everything the appl` and `LocalMediaStorage`) actually correct?**
  _`StorageError` has 87 INFERRED edges - model-reasoned connections that need verification._
- **Are the 84 inferred relationships involving `StageName` (e.g. with `VidScope ports layer.  Protocol-only interfaces describing everything the appl` and `Video`) actually correct?**
  _`StageName` has 84 INFERRED edges - model-reasoned connections that need verification._