# Graph Report - src/vidscope  (2026-04-20)

## Corpus Check
- 140 files · ~66,285 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1777 nodes · 3258 edges · 61 communities detected
- Extraction: 63% EXTRACTED · 37% INFERRED · 0% AMBIGUOUS · INFERRED: 1202 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `VidScope ports layer.  Protocol-only interfaces describing everything the appl` - 153 edges
2. `StorageError` - 85 edges
3. `StageName` - 65 edges
4. `UnitOfWork` - 64 edges
5. `Platform` - 50 edges
6. `ContentType` - 44 edges
7. `SentimentLabel` - 44 edges
8. `TrackingStatus` - 44 edges
9. `Language` - 44 edges
10. `RunStatus` - 44 edges

## Surprising Connections (you probably didn't know these)
- `YAML-backed :class:`TaxonomyCatalog` implementation.  Loads ``config/taxonomy.` --uses--> `TaxonomyCatalog`  [INFERRED]
  src\vidscope\adapters\config\yaml_taxonomy.py → src\vidscope\ports\taxonomy_catalog.py
- `Concrete :class:`TaxonomyCatalog` reading a YAML file.      The file must be a` --uses--> `TaxonomyCatalog`  [INFERRED]
  src\vidscope\adapters\config\yaml_taxonomy.py → src\vidscope\ports\taxonomy_catalog.py
- `SQLite implementation of :class:`CollectionRepository` (M011/S02/R057).  Colle` --uses--> `StorageError`  [INFERRED]
  src\vidscope\adapters\sqlite\collection_repository.py → src\vidscope\domain\errors.py
- `Repository for :class:`Collection` + collection_items backed by SQLite.` --uses--> `StorageError`  [INFERRED]
  src\vidscope\adapters\sqlite\collection_repository.py → src\vidscope\domain\errors.py
- `ListTrendingUseCase — rank videos by views_velocity_24h on a time window.  Sca` --uses--> `Clock`  [INFERRED]
  src\vidscope\application\list_trending.py → src\vidscope\ports\clock.py

## Hyperedges (group relationships)
- **Pipeline Stage Service Protocols** — ports_pipeline_Stage, ports_pipeline_Downloader, ports_pipeline_Transcriber, ports_pipeline_FrameExtractor, ports_pipeline_Analyzer, ports_pipeline_SearchIndex [EXTRACTED 1.00]
- **Video Aggregate Root (Video + related entities)** — entities_Video, entities_Transcript, entities_Frame, entities_Analysis, entities_VideoStats, entities_VideoTracking, entities_Hashtag, entities_Mention, entities_Link, entities_FrameText [INFERRED 0.90]
- **UnitOfWork Repository Bundle** — ports_uow_UnitOfWork, ports_repositories_VideoRepository, ports_repositories_TranscriptRepository, ports_repositories_FrameRepository, ports_repositories_AnalysisRepository, ports_repositories_PipelineRunRepository, ports_repositories_WatchAccountRepository, ports_repositories_WatchRefreshRepository, ports_repositories_VideoStatsRepository, ports_repositories_VideoTrackingRepository, ports_repositories_TagRepository, ports_repositories_CollectionRepository [EXTRACTED 1.00]
- **Supported Platform Values** — values_Platform, entities_Video, entities_Creator, entities_WatchedAccount, entities_Mention [EXTRACTED 1.00]
- **Domain Error Hierarchy** — errors_DomainError, errors_IngestError, errors_CookieAuthError, errors_TranscriptionError, errors_FrameExtractionError, errors_AnalysisError, errors_IndexingError, errors_StorageError, errors_ConfigError, errors_StageCrashError [EXTRACTED 1.00]
- **Pipeline Stage Execution Order** — values_StageName, entities_PipelineRun, ports_pipeline_Stage, ports_pipeline_PipelineContext [EXTRACTED 0.95]
- **Content Classification Enums** — values_ContentType, values_ContentShape, values_SentimentLabel, entities_Analysis [EXTRACTED 1.00]
- **Ingest / Download Contract** — ports_pipeline_Downloader, ports_pipeline_IngestOutcome, ports_pipeline_ChannelEntry, ports_pipeline_ProbeResult, ports_pipeline_ProbeStatus, errors_IngestError [EXTRACTED 1.00]
- **Default Pipeline Stage Sequence** — ingest_IngestStage, transcribe_TranscribeStage, frames_FramesStage, analyze_AnalyzeStage, visual_intelligence_VisualIntelligenceStage, metadata_extract_MetadataExtractStage, index_IndexStage [EXTRACTED 1.00]
- **PipelineContext data flow across stages** — ingest_PipelineContext, ingest_IngestStage, transcribe_TranscribeStage, frames_FramesStage, analyze_AnalyzeStage, visual_intelligence_VisualIntelligenceStage, metadata_extract_MetadataExtractStage, index_IndexStage [EXTRACTED 1.00]
- **MediaStorage port shared across stages** — ingest_MediaStorage, ingest_IngestStage, transcribe_TranscribeStage, frames_FramesStage, visual_intelligence_VisualIntelligenceStage [EXTRACTED 1.00]
- **Resume-from-failure pattern via is_satisfied** — runner_resume_from_failure, transcribe_TranscribeStage, frames_FramesStage, analyze_AnalyzeStage, visual_intelligence_VisualIntelligenceStage, metadata_extract_MetadataExtractStage [EXTRACTED 1.00]
- **Link extraction from three sources (description, transcript, ocr)** — metadata_extract_Link, metadata_extract_MetadataExtractStage, visual_intelligence_VisualIntelligenceStage, metadata_extract_LinkExtractor, visual_intelligence_LinkExtractor [EXTRACTED 1.00]
- **VisualIntelligenceStage triple output (OCR+thumbnail+content_shape)** — visual_intelligence_VisualIntelligenceStage, visual_intelligence_FrameText, visual_intelligence_thumbnail_key, visual_intelligence_ContentShape [EXTRACTED 1.00]
- **StatsStage out-of-band standalone invocation pattern** — stats_stage_StatsStage, stats_stage_standalone_pattern, stats_stage_StatsProbe [EXTRACTED 1.00]
- **Adapter Layer â€” all secondary adapters** — downloader_YtdlpDownloader, ytdlp_stats_probe_YtdlpStatsProbe, frame_extractor_FfmpegFrameExtractor, rapidocr_RapidOcrEngine, haarcascade_HaarcascadeFaceCounter, transcriber_FasterWhisperTranscriber, local_media_storage_LocalMediaStorage, regex_link_extractor_RegexLinkExtractor, url_normalizer_normalize_url [EXTRACTED 0.95]
- **No content-type / media-type guard at adapter boundary** — frame_extractor_no_image_guard, transcriber_no_audio_guard, downloader_no_carousel_handling [EXTRACTED 0.93]
- **Optional-library graceful-degrade pattern** — rapidocr_graceful_degrade, haarcascade_graceful_degrade, rapidocr_lazy_load, haarcascade_lazy_load [EXTRACTED 0.95]
- **Lazy heavy-model load pattern** — transcriber_lazy_model_load, rapidocr_lazy_load, haarcascade_lazy_load [INFERRED 0.88]
- **requested_downloads[0] first-only â€” no sidecar/carousel iteration** — downloader_resolve_media_path, downloader_requested_downloads_first, downloader_no_carousel_handling [EXTRACTED 0.95]
- **All SQLite Repositories Share Single Connection via UnitOfWork** — sqlite_unit_of_work, video_repository_sqlite, transcript_repository_sqlite, frame_repository_sqlite, analysis_repository_sqlite, pipeline_run_repository_sqlite, search_index_sqlite, watch_account_repository_sqlite, video_stats_repository_sqlite, collection_repository_sqlite, creator_repository_sqlite, hashtag_repository_sqlite, link_repository_sqlite, tag_repository_sqlite, frame_text_repository_sqlite [EXTRACTED 1.00]
- **videos Table Columns: id, platform(String), platform_id, url, author, title, duration(Float nullable), upload_date, view_count, media_key, creator_id(FK), created_at** — schema_videos_table, schema_platform_string_column, schema_duration_nullable_float, schema_creators_table [EXTRACTED 1.00]
- **Gaps for Carousel/Multi-Image Support: no media_type, no post_type, no is_carousel, no parent_id, duration nullable already suits images** — schema_no_media_type_column, carousel_gap_videos_table, carousel_gap_frames_fk, schema_duration_nullable_float, schema_frames_table, schema_videos_table [INFERRED 0.92]
- **FTS5 Search Infrastructure: search_index + frame_texts_fts virtual tables** — schema_search_index_fts5, schema_frame_texts_fts, search_index_sqlite, frame_text_repository_sqlite [EXTRACTED 1.00]
- **Tables with video_id FK (children of videos)** — schema_transcripts_table, schema_frames_table, schema_analyses_table, schema_pipeline_runs_table, schema_video_tracking_table, schema_video_stats_table, schema_tag_assignments_table, schema_collection_items_table, schema_frame_texts_table, schema_hashtags_table, schema_links_table, schema_mentions_table [EXTRACTED 1.00]

## Communities

### Community 0 - "Ports / Interfaces"
Cohesion: 0.01
Nodes (188): Clock, Clock port.  Every place in the codebase that needs the current time goes throug, Abstracts "what time is it now" so tests can inject a fixed clock.      Implemen, Return the current time as a timezone-aware ``datetime`` in UTC., Config, build_container(), Container, Composition root for VidScope.  This module is the single place in the codebas (+180 more)

### Community 1 - "SQLite Repositories"
Cohesion: 0.02
Nodes (130): _analysis_to_row(), AnalysisRepositorySQLite, _ensure_utc(), SQLite implementation of :class:`AnalysisRepository`., Repository for :class:`Analysis` backed by SQLite., Return video ids whose most-recent analysis matches the given filters., _row_to_analysis(), _creator_to_row() (+122 more)

### Community 2 - "LLM Analyzers"
Cohesion: 0.04
Nodes (72): build_analyzer(), _build_anthropic(), _build_groq(), _build_heuristic_v2(), _build_nvidia(), _build_openai(), _build_openrouter(), Analyzer registry — picks an Analyzer implementation by name.  Implements R010 (+64 more)

### Community 3 - "Domain Entities AST"
Cohesion: 0.1
Nodes (72): Analysis, Collection, Creator, Frame, FrameText, Hashtag, Link, Mention (+64 more)

### Community 4 - "Creator Management"
Cohesion: 0.04
Nodes (62): creator_videos(), list_creators(), _parse_platform(), `vidscope creator` sub-commands — show, list, videos., List creators in the library., List videos ingested from a specific creator., Show the full profile for a creator identified by handle., show_creator() (+54 more)

### Community 5 - "Domain Entities Semantic"
Cohesion: 0.04
Nodes (85): Analysis Entity, Collection Entity, Creator Entity, Frame Entity, FrameText Entity, Hashtag Entity, Link Entity, Mention Entity (+77 more)

### Community 6 - "Stats Refresh"
Cohesion: 0.05
Nodes (59): RefreshStatsUseCase — orchestrate StatsStage for one or many videos.  The use, Refresh stats for up to ``limit`` videos. Per-video error isolation., Outcome of refresh-stats-for-watchlist (M009/S03).      Counts how many accoun, Refresh video_stats for every video of every watched account.      For each Wa, Iterate watched accounts and refresh stats for all their videos.          Open, Outcome of a single refresh-stats invocation., Outcome of a batch refresh-stats invocation., Refresh video_stats for a single video or a batch.      Dependencies injected (+51 more)

### Community 7 - "Collection Use Cases"
Cohesion: 0.06
Nodes (42): AddToCollectionUseCase, CollectionSummary, CreateCollectionUseCase, ListCollectionsUseCase, Collection use cases (M011/S02/R057).  4 use cases operating on the collection, Row used by `vidscope collection list`.      ``video_count`` is the exact coun, Create a new named collection. Raises on duplicate name., Add a video to a collection (by collection name). (+34 more)

### Community 8 - "DB Schema + Carousel Gaps"
Cohesion: 0.05
Nodes (59): AnalysisRepositorySQLite, Gap: frames.video_id FK would need carousel_item_id extension for per-slide frames, Gap: videos table lacks media_type/is_carousel/parent_id for carousel support, CollectionRepositorySQLite, CreatorRepositorySQLite, FrameRepositorySQLite, FrameTextRepositorySQLite, HashtagRepositorySQLite (+51 more)

### Community 9 - "Downloader + Platform"
Cohesion: 0.07
Nodes (43): CookieAuthError domain error, IngestError domain error, Platform enum, YtdlpDownloader, _bool_or_none(), _build_creator_info(), YtdlpDownloader.download(), entries[] channel listing (list_channel_videos) (+35 more)

### Community 10 - "Cookie Auth"
Cohesion: 0.1
Nodes (36): clear(), ClearCookiesResult, ClearCookiesUseCase, CookiesProbeResult, CookiesProbeUseCase, CookiesStatus, _default_cookies_path(), GetCookiesStatusUseCase (+28 more)

### Community 11 - "Pipeline Stages"
Cohesion: 0.08
Nodes (41): Analysis domain entity, AnalyzeStage, Analyzer port, Frame domain entity, FrameExtractor port, FramesStage, IndexStage, Downloader port (+33 more)

### Community 12 - "OCR + Vision"
Cohesion: 0.09
Nodes (22): FaceCounter, OcrEngine, OcrLine, OCR + face-count ports (M008/R047, R049).  Both Protocols are pure — implement, One line of OCR-extracted text.      ``text`` is the raw string as reported by, OCR engine port. Default implementation:     :class:`~vidscope.adapters.vision., Return OCR lines above ``min_confidence`` found in         the image at ``image, Face-count port. Default implementation:     :class:`~vidscope.adapters.vision. (+14 more)

### Community 13 - "Content Type Heuristics"
Cohesion: 0.1
Nodes (18): _actionability_score(), _build_reasoning(), _detect_content_type(), _estimate_duration(), HeuristicAnalyzerV2, _information_density(), _novelty_score(), _production_quality() (+10 more)

### Community 14 - "Frame / Transcript Errors"
Cohesion: 0.08
Nodes (27): Frame domain entity, FrameExtractionError domain error, Transcript domain entity, TranscriptionError domain error, FfmpegFrameExtractor, FfmpegFrameExtractor.extract_frames(), Default FPS=0.2 (1 frame per 5s), Output template frame_%04d.jpg (+19 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (25): _backoff_seconds(), build_messages(), call_with_retry(), make_analysis(), _parse_bool_flag(), _parse_content_type(), parse_llm_json(), _parse_reasoning() (+17 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (16): LinkExtractor, LinkExtractor port.  Extracts URLs from arbitrary text (video description, tra, One URL extracted from text.      ``url`` is the raw string as captured (case, Pure URL extractor — no I/O.      The default implementation in :mod:`vidscope, Extract URLs from ``text``. Returns empty list when none.          ``source``, RawLink, MetadataExtractStage, MetadataExtractStage — fifth stage of the pipeline (M007/S03).  Extracts URLs (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.14
Nodes (12): _deduplicate(), _pack_into_budget(), YamlVocabularySource — construit l'initial_prompt Whisper depuis vocabulary.yaml, Lit et parse vocabulary.yaml. Retourne None si absent ou invalide., Requêtes légères en lecture seule sur la bibliothèque DB., Déduplique en préservant l'ordre (clé = lowercase)., Assemble les termes séparés par ', ' jusqu'à ``max_chars``., Construit un initial_prompt Whisper depuis YAML + DB.      Parameters     ------ (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.18
Nodes (15): ListTrendingUseCase, ListTrendingUseCase — rank videos by views_velocity_24h on a time window.  Sca, One row in the vidscope trending output., Rank videos by views_velocity_24h on the given time window.      Scalability (, Return up to ``limit`` trending videos ranked by views_velocity_24h., TrendingEntry, _parse_platform(), _parse_window() (+7 more)

### Community 19 - "Community 19"
Cohesion: 0.15
Nodes (11): PipelineRunner, Generic pipeline runner.  Takes a list of :class:`Stage` implementations and run, Execute every stage in order against ``ctx``.          Returns a :class:`RunResu, Execute a single stage inside its own transactional UoW., Translate a stage's string name to a :class:`StageName` enum.      Stages declar, Outcome of one stage execution as seen by the runner., Aggregate result of running a pipeline over a context.      ``success`` is ``Tru, Runs a sequence of stages against a shared pipeline context.      Construction t (+3 more)

### Community 20 - "Community 20"
Cohesion: 0.15
Nodes (14): _build_summary(), _compute_score(), HeuristicAnalyzer, _is_meaningful_word(), HeuristicAnalyzer — pure-Python zero-cost default analyzer.  Implements the :cla, Split ``text`` into lowercase word tokens., Return True for tokens worth counting as keyword candidates.      Excludes stopw, Return the ``n`` most frequent tokens, ties broken by first     appearance order (+6 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (13): `vidscope suggest <id>` — propose related videos by keyword overlap., Suggest related videos from the library using keyword overlap.      Ranks candid, _jaccard(), SuggestRelatedUseCase — keyword-overlap-based related-video suggestion.  Given a, Return (Jaccard score, sorted matched keywords) for two sets.      Jaccard = |a, One related-video entry returned by SuggestRelatedUseCase., Result of a suggest_related call.      ``source_video_id`` is the requested vide, Return the top N videos related to a source video by keyword overlap. (+5 more)

### Community 22 - "Community 22"
Cohesion: 0.19
Nodes (13): `vidscope show <id>` — show the full record for a video id., Render on-screen text section (M008)., D-05: display latest stats snapshot + computed velocity., Show the full domain record for one video id., _render_frame_texts(), _render_stats(), show_command(), Return the full record of one video — powers ``vidscope show <id>``. (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.17
Nodes (12): ExplainAnalysisResult, ExplainAnalysisUseCase, ExplainAnalysisUseCase -- returns video + latest analysis for `vidscope explain`, Result of :meth:`ExplainAnalysisUseCase.execute`.      ``found`` is ``False``, Return the latest analysis for ``video_id`` -- powers `vidscope explain`., explain_command(), _fmt_bool(), _fmt_enum() (+4 more)

### Community 24 - "Community 24"
Cohesion: 0.2
Nodes (11): add_command(), `vidscope add <url>` — ingest a video from a public URL., Run the full ingest pipeline for a single URL.      In S02 this downloads the me, Pretty-print an :class:`IngestResult` as a rich :class:`Panel`.      Shared betw, _render_result_panel(), IngestResult, IngestVideoUseCase, Ingest a video from a URL.  The primary user-facing operation. In S02 this is a (+3 more)

### Community 25 - "Community 25"
Cohesion: 0.18
Nodes (4): CollectionRepositorySQLite, SQLite implementation of :class:`CollectionRepository` (M011/S02/R057).  Colle, Repository for :class:`Collection` + collection_items backed by SQLite., _row_to_collection()

### Community 26 - "Community 26"
Cohesion: 0.16
Nodes (9): _entity_to_row(), SQLite implementation of :class:`VideoStatsRepository`.  Append-only: rows are, Return all raw rows for ``video_id`` ordered by captured_at asc., Translate a :class:`VideoStats` entity to a DB row dict., Translate a raw DB row dict to a :class:`VideoStats` entity.      ``None`` cou, Insert ``stats`` and return it with ``id`` populated.          If a row with t, Return up to ``limit`` snapshots for ``video_id``, oldest first.          Orde, Return the most recent snapshot for ``video_id``, or ``None``. (+1 more)

### Community 27 - "Community 27"
Cohesion: 0.18
Nodes (10): _parse_status(), `vidscope review <video_id> --status X [--star/--unstar] [--note TEXT] [--clear-, Set workflow overlay (status, starred, notes) on a video., review_command(), SetVideoTrackingUseCase — M011/S01/R056.  Writes a user workflow overlay for a, Outcome of :class:`SetVideoTrackingUseCase.execute`., Upsert the workflow overlay for a single video., Set or update the tracking row for ``video_id``.          Parameters (+2 more)

### Community 28 - "Community 28"
Cohesion: 0.19
Nodes (8): _apply_corrections(), FasterWhisperTranscriber, _map_language(), FasterWhisperTranscriber — faster-whisper implementation of Transcriber.  Wraps, Transcribe ``media_path`` and return a domain Transcript.          The model is, Load the WhisperModel on first call, return the cached         instance on subse, Map a faster-whisper language code to our :class:`Language` enum.      Anything, Transcriber port implementation backed by faster-whisper.      Parameters     --

### Community 29 - "Community 29"
Cohesion: 0.17
Nodes (10): VideoStats domain entity, YtdlpStatsProbe, _int_or_none(), probe-never-raises contract (T-PROBE-01), YtdlpStatsProbe.probe_stats(), YtdlpStatsProbe — yt-dlp implementation of the StatsProbe port.  Wraps ``yt_dl, Return ``value`` cast to ``int``, or ``None`` if not safely castable.      Acc, StatsProbe port implementation backed by yt-dlp.      Parameters     -------- (+2 more)

### Community 30 - "Community 30"
Cohesion: 0.18
Nodes (9): links_command(), `vidscope links <id>` — list extracted URLs for a video., List every URL extracted from a video's description + transcript., ListLinksResult, ListLinksUseCase, List extracted links for a video — powers ``vidscope links <id>``., Outcome of :meth:`ListLinksUseCase.execute`.      ``found`` is ``False`` when, Return every :class:`Link` for a video, optionally filtered by source. (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (9): list_command(), `vidscope list` — list recently ingested videos., List the most recently ingested videos., ListVideosResult, ListVideosUseCase, List recently ingested videos — powers ``vidscope list``., Result of :meth:`ListVideosUseCase.execute`.      ``videos`` is ordered newest-f, Return the most recently ingested videos and the total count. (+1 more)

### Community 32 - "Community 32"
Cohesion: 0.18
Nodes (9): GetStatusResult, GetStatusUseCase, Return the last N pipeline runs — powers ``vidscope status``.  The status comman, List of the most recent pipeline runs.      ``runs`` is ordered newest-first. An, Return the most recent pipeline runs and quick aggregate counts., Return the ``limit`` most recent pipeline runs newest-first.          ``limit``, `vidscope status` — show the last N pipeline runs., Show the last N pipeline runs and quick aggregate counts. (+1 more)

### Community 33 - "Community 33"
Cohesion: 0.18
Nodes (9): _build_media_key(), _correct(), IngestStage, IngestStage — first stage of the pipeline.  Orchestrates three ports to turn a, Download the video, store the media file, and upsert the         videos row. Mu, Return the stable :class:`MediaStorage` key for a downloaded file.      Layout, First stage of the pipeline — download + persist metadata + media., Construct the stage.          Parameters         ----------         download (+1 more)

### Community 34 - "Community 34"
Cohesion: 0.24
Nodes (6): IndexingError, Raised when FTS5 insertion fails.      Not retryable by default: an FTS5 write f, SQLite implementation of :class:`SearchIndex` over FTS5.  Wraps the ``search_ind, FTS5-backed implementation of :class:`SearchIndex`., _row_to_result(), SearchIndexSQLite

### Community 35 - "Community 35"
Cohesion: 0.2
Nodes (9): acquire_container(), fail_system(), fail_user(), handle_domain_errors(), Shared helpers for CLI commands.  Keeps every ``commands/*.py`` file tiny and fo, Build the :class:`Container` once per CLI invocation.      This is the only func, Print a red error message and return a :class:`typer.Exit`.      Callers do ``ra, Same as :func:`fail_user` but uses exit code 2 (system error). (+1 more)

### Community 36 - "Community 36"
Cohesion: 0.2
Nodes (9): RawLink port type, RegexLinkExtractor, Pass 2: bare-domain regex (restricted TLD list), RegexLinkExtractor.extract() two-pass, Pass 1: scheme-explicit URL regex, normalize_url(), Pure-Python URL normalization — stdlib only.  Used by :class:`RegexLinkExtract, Return the canonical normalized form of ``url``.      See module docstring for (+1 more)

### Community 37 - "Community 37"
Cohesion: 0.25
Nodes (4): _load_and_validate(), YAML-backed :class:`TaxonomyCatalog` implementation.  Loads ``config/taxonomy., Concrete :class:`TaxonomyCatalog` reading a YAML file.      The file must be a, YamlTaxonomy

### Community 38 - "Community 38"
Cohesion: 0.25
Nodes (5): HaarcascadeFaceCounter, OpenCV Haarcascade-based FaceCounter adapter (M008/R049).  Wraps ``cv2.Cascade, FaceCounter implementation backed by OpenCV haarcascade., Return (cv2 module, cascade instance) or ``None``., Return the number of frontal faces in the image, or         ``0`` when any step

### Community 39 - "Community 39"
Cohesion: 0.22
Nodes (5): AnalyzeStage, AnalyzeStage — fourth stage of the pipeline.  Reads the transcript produced by t, Fourth stage of the pipeline — produce a structured analysis., Return True if any analysis already exists for the video., Read the transcript, analyze it, persist the result.          Mutates ``ctx.anal

### Community 40 - "Community 40"
Cohesion: 0.22
Nodes (5): FramesStage, FramesStage — third stage of the pipeline.  Reads ``videos.media_key`` from the, Third stage of the pipeline — extract frames from media., Return True if frames already exist for the video., Extract frames and persist them with stable storage keys.          Mutates ``ctx

### Community 41 - "Community 41"
Cohesion: 0.22
Nodes (5): TranscribeStage — second stage of the pipeline.  Reads ``videos.media_key`` from, Second stage of the pipeline — produce a transcript from media., Return True if a transcript already exists for the video.          Cheap DB quer, Transcribe the video's media file and persist the transcript.          Mutates `, TranscribeStage

### Community 42 - "Community 42"
Cohesion: 0.25
Nodes (5): IndexStage, IndexStage — fifth and final stage of the pipeline.  Writes the transcript and a, Fifth stage of the pipeline — populate the FTS5 search index., Always False: re-indexing is cheap and idempotent., Index the latest transcript and analysis summary for the video.          Raises

### Community 43 - "Community 43"
Cohesion: 0.29
Nodes (4): FfmpegFrameExtractor, FfmpegFrameExtractor — ffmpeg implementation of FrameExtractor.  Wraps the ``ffm, FrameExtractor port implementation backed by the ffmpeg CLI.      Parameters, Extract up to ``max_frames`` frames from ``media_path`` and         return Frame

### Community 44 - "Community 44"
Cohesion: 0.33
Nodes (3): StubAnalyzer — minimal second analyzer to prove the pluggable seam.  Returns a p, Placeholder Analyzer that returns an empty analysis.      Exists solely to prove, StubAnalyzer

### Community 45 - "Community 45"
Cohesion: 0.4
Nodes (3): CsvExporter, CSV library exporter (M011/S04/R059).  Flat CSV via stdlib ``csv.DictWriter``., Write export records as a flat CSV with ``|`` multi-value separator.

### Community 46 - "Community 46"
Cohesion: 0.4
Nodes (3): JsonExporter, JSON library exporter (M011/S04/R059).  Serialises ``list[ExportRecord]`` to a, Write export records as a pretty JSON array.

### Community 47 - "Community 47"
Cohesion: 0.4
Nodes (3): MarkdownExporter, Markdown library exporter (M011/S04/R059).  Each record becomes a Markdown blo, Write export records as one concatenated Markdown stream.

### Community 48 - "Community 48"
Cohesion: 0.4
Nodes (3): main(), Typer entry point for ``vidscope``.  Builds the root :class:`typer.Typer` app,, Root callback — accepts global options like ``--version``.

### Community 49 - "Community 49"
Cohesion: 0.5
Nodes (3): doctor_command(), `vidscope doctor` — run startup checks and print a report., Run every startup check and print a rich table.      Exit codes     ----------

### Community 50 - "Community 50"
Cohesion: 0.5
Nodes (3): `vidscope mcp ...` subcommands.  Currently exposes only ``vidscope mcp serve`` w, Start the vidscope MCP server on stdio.      Exposes every vidscope use case as, serve()

### Community 51 - "Community 51"
Cohesion: 0.5
Nodes (3): build_engine(), SQLAlchemy Engine factory for SQLite.  This module is the single place in the co, Return a SQLAlchemy Engine bound to ``db_path``.      The engine attaches a ``co

### Community 52 - "Community 52"
Cohesion: 0.5
Nodes (4): StorageError domain error, LocalMediaStorage, LocalMediaStorage.store() atomic copy, Path traversal guard (_resolve_safe)

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Stopword lists for the heuristic analyzer.  Minimal French + English stopword se

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (2): LinkExtractor Protocol, RawLink TypedDict

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Public read-only accessor for the configured model name.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): TagName NewType

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): CollectionName NewType

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): IngestOutcome (fields: platform, platform_id, url, media_path, title, author, duration, upload_date, view_count, creator_info, description, hashtags, mentions, music_track, music_artist)

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): CookieAuthError translation

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): watch_refreshes Table

## Knowledge Gaps
- **435 isolated node(s):** `YamlVocabularySource — construit l'initial_prompt Whisper depuis vocabulary.yaml`, `Construit un initial_prompt Whisper depuis YAML + DB.      Parameters     ------`, `Retourne les hotwords sous forme de chaîne pour faster-whisper.          Les hot`, `Retourne la liste (wrong, right) depuis la section ``corrections``.          Uti`, `Retourne une chaîne de termes séparés par des virgules, ou None.          Priori` (+430 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 53`** (2 nodes): `stopwords.py`, `Stopword lists for the heuristic analyzer.  Minimal French + English stopword se`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (2 nodes): `LinkExtractor Protocol`, `RawLink TypedDict`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Public read-only accessor for the configured model name.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `TagName NewType`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `CollectionName NewType`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `IngestOutcome (fields: platform, platform_id, url, media_path, title, author, duration, upload_date, view_count, creator_info, description, hashtags, mentions, music_track, music_artist)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `CookieAuthError translation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `watch_refreshes Table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `VidScope ports layer.  Protocol-only interfaces describing everything the appl` connect `Ports / Interfaces` to `SQLite Repositories`, `LLM Analyzers`, `Domain Entities AST`, `Creator Management`, `Stats Refresh`, `Collection Use Cases`, `Downloader + Platform`, `OCR + Vision`, `Content Type Heuristics`, `Community 16`, `Community 17`, `Community 18`, `Community 19`, `Community 20`, `Community 21`, `Community 22`, `Community 23`, `Community 24`, `Community 28`, `Community 29`, `Community 31`, `Community 32`, `Community 33`, `Community 34`, `Community 37`, `Community 38`, `Community 39`, `Community 40`, `Community 41`, `Community 42`, `Community 43`, `Community 44`, `Community 45`, `Community 46`, `Community 47`?**
  _High betweenness centrality (0.634) - this node is a cross-community bridge._
- **Why does `StorageError` connect `SQLite Repositories` to `Ports / Interfaces`, `Community 25`, `Domain Entities AST`, `Collection Use Cases`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `DomainError` connect `Collection Use Cases` to `Ports / Interfaces`, `SQLite Repositories`, `LLM Analyzers`, `Community 34`, `Domain Entities AST`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 152 inferred relationships involving `VidScope ports layer.  Protocol-only interfaces describing everything the appl` (e.g. with `YamlTaxonomy` and `YamlVocabularySource`) actually correct?**
  _`VidScope ports layer.  Protocol-only interfaces describing everything the appl` has 152 INFERRED edges - model-reasoned connections that need verification._
- **Are the 82 inferred relationships involving `StorageError` (e.g. with `LocalMediaStorage` and `Filesystem-backed :class:`MediaStorage`.  Keys are slash-separated strings (e.g.`) actually correct?**
  _`StorageError` has 82 INFERRED edges - model-reasoned connections that need verification._
- **Are the 62 inferred relationships involving `StageName` (e.g. with `Video` and `TranscriptSegment`) actually correct?**
  _`StageName` has 62 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `UnitOfWork` (e.g. with `SystemClock` and `Container`) actually correct?**
  _`UnitOfWork` has 59 INFERRED edges - model-reasoned connections that need verification._