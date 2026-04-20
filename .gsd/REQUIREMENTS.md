# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R001 — Given a public video URL from Instagram (Reel or post), TikTok, or YouTube (video or Short), the tool downloads the media file to a local cache and records the canonical metadata (platform, author, title, duration, upload date, view count when available).
- Class: core-capability
- Status: active
- Description: Given a public video URL from Instagram (Reel or post), TikTok, or YouTube (video or Short), the tool downloads the media file to a local cache and records the canonical metadata (platform, author, title, duration, upload date, view count when available).
- Why it matters: Without reliable ingestion, no other capability works. This is the riskiest brick because yt-dlp occasionally breaks when platforms change, and Instagram is the most fragile of the three.
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: S02 shipped YtdlpDownloader + IngestStage + container wiring + integration tests. Validated on real networks for YouTube Shorts (19s short downloaded, metadata extracted, row persisted, media file on disk) and TikTok videos (same full round-trip). Instagram is XFAIL'd because Meta now requires authentication even for public Reels — see R025 which is deferred to M005 for cookie-based ingestion. Short-form target profile (D026) means YouTube Shorts / Instagram Reels / TikTok videos are the validated content shape, not long-form YouTube.
- Notes: S02 validated R001 on 2/3 target platforms (YouTube, TikTok). Instagram is blocked upstream by platform auth requirements which R025/M005 will unblock. The ingest stage itself handles all three extractors correctly.

### R002 — For every ingested video, produce a full-text transcript and timestamped segments in the video's spoken language. Must handle at least French and English reliably on CPU.
- Class: core-capability
- Status: active
- Description: For every ingested video, produce a full-text transcript and timestamped segments in the video's spoken language. Must handle at least French and English reliably on CPU.
- Why it matters: The transcript is what makes videos searchable and analyzable without watching them. It is the atomic unit the rest of the pipeline consumes.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: none
- Validation: S03 shipped: FasterWhisperTranscriber adapter + TranscribeStage + container wiring + integration tests. Validated on live YouTube Short (transcription completes in ~6.5s on CPU with int8 quantization, model 'base'). TikTok also ingests + transcribes successfully (instrumental video → empty transcript is a legitimate outcome). Instagram path conditional on R025 cookies. Default device='cpu' / compute_type='int8' matches D008.
- Notes: Validated for English content (fr testing pending a real French short URL). VAD filter disabled by default because it strips speech from short-form content. Two real bugs surfaced and fixed during T05's first live run: (1) device='auto' was unsafe on partial-CUDA installs, (2) VAD too aggressive for tight-paced short videos.

### R003 — Produce a small set of frames per video (keyframes plus a fixed-rate sample) stored as images on disk with their timestamps recorded in the DB, so a multimodal agent or a human can inspect the visual content without loading the full video.
- Class: core-capability
- Status: active
- Description: Produce a small set of frames per video (keyframes plus a fixed-rate sample) stored as images on disk with their timestamps recorded in the DB, so a multimodal agent or a human can inspect the visual content without loading the full video.
- Why it matters: The transcript captures audio but not visuals. Frames are the cheap substitute for "watching" the video that keeps the system multimodal-ready.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: none
- Validation: S04 shipped: FfmpegFrameExtractor adapter + FramesStage + container wiring + integration tests. Validated on live YouTube Short and TikTok video: frame extraction completes in ~1s per video, frames are stored under MediaStorage at canonical keys (videos/{platform}/{platform_id}/frames/{index:04d}.jpg), and the frames table has rows linked to the video. Default 0.2 fps (1 frame per 5 seconds), capped at 30 frames per video (D016/R003 notes).
- Notes: Sampling strategy is a tunable parameter; the default is ~1 frame per 5 seconds plus all keyframes, capped at 30 frames per video.

### R004 — For every video, produce a structured analysis record containing at least: detected language, top keywords, dominant topics, a relevance/quality score (0–100), and a short summary. The analysis must be producible with zero paid API calls using only local heuristics on the transcript.
- Class: core-capability
- Status: active
- Description: For every video, produce a structured analysis record containing at least: detected language, top keywords, dominant topics, a relevance/quality score (0–100), and a short summary. The analysis must be producible with zero paid API calls using only local heuristics on the transcript.
- Why it matters: Raw transcripts don't scale — the user needs a digestible signal per video. Keeping the default analyzer heuristic-only guarantees the system stays usable at zero cost.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: none
- Validation: S05 shipped: HeuristicAnalyzer + AnalyzeStage + container wiring. Validated on live YouTube + TikTok: every video produces an analyses row with provider='heuristic', detected language, top keywords (frequency-based, stopwords excluded), top topics, score in [0, 100], summary truncated to ~200 chars. Pure-Python implementation, zero network calls, zero paid API. Empty transcripts produce score=0 and summary='no speech detected' so the row exists for the FTS5 index in S06.
- Notes: Richer LLM-backed analyzers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic) are a pluggable extension deferred to M004.

### R005 — Videos, metadata, transcripts, frames, analyses, and pipeline run records must live in a single SQLite database with a schema versioned by migrations. Every row must be addressable by a stable ID and linked to its parent video.
- Class: core-capability
- Status: active
- Description: Videos, metadata, transcripts, frames, analyses, and pipeline run records must live in a single SQLite database with a schema versioned by migrations. Every row must be addressable by a stable ID and linked to its parent video.
- Why it matters: A pipeline without persistent output is just a pile of temp files. The DB is the durable surface the CLI and the future MCP server both read from.
- Source: inferred
- Primary owning slice: M001/S01
- Supporting slices: M001/S02, M001/S03, M001/S04, M001/S05, M001/S06
- Validation: Schema + repository layer implemented and tested in S01 (185 tests including 52 adapter-level tests, 29 infrastructure tests). Every row is addressable by stable id, FKs are enforced via PRAGMA, FTS5 virtual table is live. Full validation pending S02-S06 which write real rows through the pipeline.
- Notes: S01 advanced this requirement: SQLAlchemy Core + SQLite + FTS5 data layer complete, 5 repositories implementing ports, UnitOfWork for transactional writes. The data layer is accessed exclusively through the repository layer so a future Postgres + pgvector migration touches only src/vidscope/adapters/sqlite/.

### R006 — `vidscope search "<query>"` returns ranked matches from transcripts, titles, and analysis summaries using SQLite FTS5.
- Class: core-capability
- Status: active
- Description: `vidscope search "<query>"` returns ranked matches from transcripts, titles, and analysis summaries using SQLite FTS5.
- Why it matters: Search is the primary retrieval surface before the MCP layer ships. Without it, the DB is write-only.
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S01
- Validation: S06 shipped: IndexStage as 5th pipeline stage writes transcripts and analysis summaries to FTS5 search_index virtual table. vidscope search "<query>" returns ranked hits with snippets. Validated end-to-end on live YouTube Short: ingest → transcribe → frames → analyze → index → search('music') returns 2 hits (one transcript, one analysis_summary). CLI command vidscope search wired to SearchLibraryUseCase which queries the SearchIndex port.
- Notes: Semantic search via embeddings is deferred — FTS5 is sufficient for v1.

### R007 — `vidscope add <url>` performs ingest → transcribe → frames → analyze → index in one invocation and reports a structured summary on exit. Failures at any stage are surfaced with enough context to diagnose (which stage, what error, what was persisted before the failure).
- Class: primary-user-loop
- Status: active
- Description: `vidscope add <url>` performs ingest → transcribe → frames → analyze → index in one invocation and reports a structured summary on exit. Failures at any stage are surfaced with enough context to diagnose (which stage, what error, what was persisted before the failure).
- Why it matters: This is the single command that justifies the project's existence. Every other CLI command is a support surface around this one loop.
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S02, M001/S03, M001/S04, M001/S05
- Validation: S06 closes R007 end-to-end: vidscope add <url> performs ingest → transcribe → frames → analyze → index in one invocation, reports a structured summary on exit, partial success leaves consistent DB state because every stage commits transactionally with its pipeline_runs row. Validated via verify-m001.sh on live YouTube Short. Failures at any stage are surfaced via the typed DomainError + pipeline_runs.error column, visible in vidscope status.
- Notes: Partial success must leave the DB in a consistent state — no half-written rows.

### R008 — `vidscope status` and `vidscope show <id>` surface the current state of the pipeline: last N runs, their stage outcomes, any persistent errors, and the full record of a given video including transcript, frames list, and analysis. Errors are recoverable — re-running `add` on a video that previously failed resumes from the last successful stage.
- Class: failure-visibility
- Status: active
- Description: `vidscope status` and `vidscope show <id>` surface the current state of the pipeline: last N runs, their stage outcomes, any persistent errors, and the full record of a given video including transcript, frames list, and analysis. Errors are recoverable — re-running `add` on a video that previously failed resumes from the last successful stage.
- Why it matters: When something breaks at 3am or after a yt-dlp upstream change, the tool must tell the operator what it did, where it stopped, and why — without requiring a log dive or a manual DB inspection.
- Source: inferred
- Primary owning slice: M001/S06
- Supporting slices: M001/S01
- Validation: S06 closes R008: vidscope status shows the last N pipeline_runs with phase, status, video, started, duration, error (truncated). vidscope show <id> displays full record (video metadata + transcript info + frames count + analysis info). Re-running vidscope add on a previously ingested video resumes from the last incomplete stage thanks to is_satisfied checks on transcribe/frames/analyze (D025 documents that ingest currently always re-downloads but the videos row is upserted idempotently).
- Notes: Structured run records are written by every stage from S01 onwards.

### R009 — The tool installs and runs on Windows (current dev machine), macOS, and Linux with a single command (`uv tool install` or `pipx install`). System dependencies (`ffmpeg`, `yt-dlp` binary when not bundled) are documented and checked at startup with an actionable error when missing.
- Class: operability
- Status: active
- Description: The tool installs and runs on Windows (current dev machine), macOS, and Linux with a single command (`uv tool install` or `pipx install`). System dependencies (`ffmpeg`, `yt-dlp` binary when not bundled) are documented and checked at startup with an actionable error when missing.
- Why it matters: This is a personal tool but cross-platform discipline prevents Windows-specific shortcuts that would bite later.
- Source: inferred
- Primary owning slice: M001/S01
- Supporting slices: M001/S02
- Validation: S01 verified: package installs via `uv sync` on Windows from a fresh clone, runs without modification, uses platformdirs for cross-platform paths, MediaStorage uses slash-separated string keys so the domain is OS-agnostic. Startup checks detect missing ffmpeg/yt-dlp with platform-specific remediation (Windows winget, macOS brew, Linux apt). Full cross-OS validation (macOS, Linux) pending — currently only Windows 10/11 is exercised.
- Notes: Python 3.12+ is the minimum because of typing features and stdlib improvements used throughout.

### R010 — The analyzer is a provider interface with at least two implementations wired in M001 (heuristics, and a stub for a future LLM backend) so that adding NVIDIA, Groq, OpenRouter, OpenAI, or Anthropic later requires only implementing the interface and registering the provider — not changing any caller.
- Class: quality-attribute
- Status: active
- Description: The analyzer is a provider interface with at least two implementations wired in M001 (heuristics, and a stub for a future LLM backend) so that adding NVIDIA, Groq, OpenRouter, OpenAI, or Anthropic later requires only implementing the interface and registering the provider — not changing any caller.
- Why it matters: The user explicitly wants to stay cost-free by default but keep the door open for richer analysis via free-tier LLM APIs (NVIDIA Build, Groq, Cerebras) or paid APIs on demand. This requirement is about the seam, not the implementations.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: none
- Validation: S05 shipped the pluggable analyzer seam: build_analyzer(name) registry in vidscope.infrastructure.analyzer_registry maps provider names to Analyzer instances. Two providers registered (HeuristicAnalyzer, StubAnalyzer) to prove the seam works with multiple implementations. M004 will add LLM-backed providers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic) by extending _FACTORIES; container wiring code will not change. Analyzer selected via VIDSCOPE_ANALYZER env var (default 'heuristic').
- Notes: Concrete non-heuristic providers ship in M004.

### R020 — A Python MCP server exposes at least `vidscope_ingest`, `vidscope_search`, `vidscope_get_video`, `vidscope_suggest_related`, and `vidscope_watch_list` so an AI agent can drive the library in conversation and propose related videos to enrich a topic.
- Class: integration
- Status: active
- Description: A Python MCP server exposes at least `vidscope_ingest`, `vidscope_search`, `vidscope_get_video`, `vidscope_suggest_related`, and `vidscope_watch_list` so an AI agent can drive the library in conversation and propose related videos to enrich a topic.
- Why it matters: This is the other half of the user-facing value: being able to hand an agent a URL and have it both ingest and suggest adjacent content. It's deferred only to keep M001 focused on the pipeline itself.
- Source: user
- Primary owning slice: M002
- Supporting slices: none
- Validation: unmapped
- Notes: Promoted from deferred to active at M002 start. Target: ship a Python MCP server via `mcp` SDK that exposes vidscope_ingest, vidscope_search, vidscope_get_video, vidscope_list_videos, vidscope_get_status, vidscope_suggest_related tools. The server wraps the existing use cases from M001 without adding any new business logic.

### R023 — Given a video ID or a freshly ingested URL, propose N related videos already in the library and optionally N external URLs worth ingesting, using topic overlap, creator overlap, and transcript similarity.
- Class: differentiator
- Status: active
- Description: Given a video ID or a freshly ingested URL, propose N related videos already in the library and optionally N external URLs worth ingesting, using topic overlap, creator overlap, and transcript similarity.
- Why it matters: This is what turns a passive archive into an active research tool. It's only useful once the library has enough content, so it ships after M001.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: none
- Validation: S02 shipped: SuggestRelatedUseCase with Jaccard keyword overlap (pure Python, zero deps) + `vidscope suggest <id>` CLI + `vidscope_suggest_related` MCP tool. Validated by 11 unit tests covering happy path + 6 edge cases + score ordering, 3 MCP tool unit tests, 2 subprocess integration tests. Score = |source_kw ∩ candidate_kw| / |source_kw ∪ candidate_kw|. Semantic embeddings (R026) remain deferred.
- Notes: Promoted from deferred to active at M002 start. First version uses keyword overlap from the heuristic analyzer (R010) — no embeddings yet (R026 remains deferred). Exposed via both CLI (vidscope suggest) and MCP tool.

## Validated

### R021 — Declare a public Instagram / TikTok / YouTube account as "watched"; on demand (`vidscope watch refresh`) or via cron, the tool detects new videos from watched accounts and pushes them through the ingestion pipeline automatically.
- Class: primary-user-loop
- Status: validated
- Description: Declare a public Instagram / TikTok / YouTube account as "watched"; on demand (`vidscope watch refresh`) or via cron, the tool detects new videos from watched accounts and pushes them through the ingestion pipeline automatically.
- Why it matters: The user wants a veille loop that keeps a library fresh without manual URL-by-URL work. Deferred to keep M001 scoped to single-URL ingestion.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: M003/S02 + S03. WatchAccountRepository CRUD validated by 14 unit tests, 4 watchlist use cases by 23 unit tests, vidscope watch sub-application by 11 CLI tests, full E2E flow by verify-m003.sh demo.
- Notes: Promoted from deferred to active at M003 start. Declare a public account as watched; on demand (`vidscope watch refresh`) the tool detects new videos from watched accounts and pushes them through the ingestion pipeline automatically. yt-dlp supports channel/account URL listing which makes this implementable without new adapters.

### R022 — Provide a documented way to run the refresh loop on a schedule (cron on Linux/macOS, Task Scheduler on Windows) and a long-lived daemon mode with health surface.
- Class: operability
- Status: validated
- Description: Provide a documented way to run the refresh loop on a schedule (cron on Linux/macOS, Task Scheduler on Windows) and a long-lived daemon mode with health surface.
- Why it matters: Turns VidScope from "a tool I invoke" into "a service that keeps my library fresh". Deferred until monitoring itself works.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: M003/S02 + S03. RefreshWatchlistUseCase iterates accounts, dedupes against existing videos, runs new URLs through PipelineRunner, persists WatchRefresh row. Idempotence validated by verify-m003.sh (second refresh = 0 new). Per-account error capture validated by unit tests. Scheduling delegated to OS cron/launchd/Task Scheduler — documented in docs/watchlist.md.
- Notes: Promoted from deferred to active at M003 start. Provide a documented way to run the refresh loop on a schedule. Manual `vidscope watch refresh` is the baseline; scheduled execution via cron / Task Scheduler must reuse the same code path.

### R024 — Concrete implementations of the analyzer provider interface for NVIDIA Build, Groq, OpenRouter, OpenAI, and Anthropic, with rate-limit handling, retry, and cost-aware invocation (never run automatically unless explicitly enabled).
- Class: quality-attribute
- Status: validated
- Description: Concrete implementations of the analyzer provider interface for NVIDIA Build, Groq, OpenRouter, OpenAI, and Anthropic, with rate-limit handling, retry, and cost-aware invocation (never run automatically unless explicitly enabled).
- Why it matters: Heuristics cover the baseline; LLM providers are the upgrade path for videos the user specifically flags. Deferred so the default stays zero-cost.
- Source: user
- Primary owning slice: M004
- Supporting slices: M004/S01, M004/S02, M004/S03
- Validation: M004 shipped 5 concrete LLM provider adapters (Groq, NVIDIA Build, OpenRouter, OpenAI, Anthropic) under vidscope.adapters.llm. Each provider is a single file ~50 lines (OpenAI-compatible) or ~150 lines (Anthropic native /v1/messages). Shared _base.py provides build_messages, parse_llm_json, call_with_retry, make_analysis, run_openai_compatible. Registry exposes 7 names (heuristic, stub, groq, nvidia, openrouter, openai, anthropic). Each provider reads its API key from VIDSCOPE_<PROVIDER>_API_KEY at factory invocation time. New 9th import-linter contract (llm-never-imports-other-adapters) structurally enforces the one-file-per-provider rule. 120 new LLM-related unit tests (34 base + 17 groq + 9 nvidia + 9 openrouter + 10 openai + 21 anthropic + 19 registry + 6 startup) all via httpx.MockTransport — zero real network. vidscope doctor reports the active analyzer + key status. docs/analyzers.md documents every provider with cost/quotas/signup URLs. verify-m004.sh runs 9 steps including all 4 quality gates + per-provider stub HTTP smoke + doctor check, exits 0.
- Notes: Target milestone is M004. The interface itself (R010) ships in M001.

### R025 — Support an exported browser cookie file (cookies.txt) so yt-dlp can fetch Instagram stories, age-gated YouTube videos, and private posts the user has access to.
- Class: core-capability
- Status: validated
- Description: Support an exported browser cookie file (cookies.txt) so yt-dlp can fetch Instagram stories, age-gated YouTube videos, and private posts the user has access to.
- Why it matters: Expands coverage beyond public content. Deferred because public content is the 80% case and cookie handling has its own friction.
- Source: user
- Primary owning slice: M005
- Supporting slices: M001/S07, M005/S01, M005/S02, M005/S03
- Validation: Cookies UX completed in M005. Plumbing shipped in M001/S07 (VIDSCOPE_COOKIES_FILE env var, doctor cookies row, ytdlp downloader cookies_file param). M005/S01 added validate_cookies_file pure-Python helper + 3 use cases (Set/GetStatus/Clear) + vidscope cookies sub-application with set/status/clear subcommands. M005/S02 added vidscope cookies test (probe via stubbed-network Downloader.probe Protocol method on the YtdlpDownloader) + CookieAuthError typed domain error subclassing IngestError + auth-marker detection in ytdlp adapter (10-element marker tuple) so vidscope add error remediation points at vidscope cookies test. M005/S03 rewrote docs/cookies.md as a 5-minute walkthrough using the new subcommands + shipped verify-m005.sh (10/10 steps green via stubbed yt_dlp). Architectural improvement: tightened application-has-no-adapters contract to forbid vidscope.infrastructure imports. 60 new cookies-related unit tests (15 validator + 21 use case + 15 CLI + 9 ytdlp probe/auth detection). All 4 quality gates clean throughout. Instagram Reels are now usable in 4 commands: export from browser, vidscope cookies set <path>, vidscope cookies test, vidscope add <url>.
- Notes: PROMOTED FROM DEFERRED (M005) TO ACTIVE (M001/S07) on 2026-04-07 per D027 (Instagram is platform priority #1). S07 closed the gap by shipping the cookies feature. Activation requires the user to export their browser cookies once \u2014 see docs/cookies.md.

## Deferred

### R026 — In addition to FTS5, store embeddings per transcript and offer `vidscope search --semantic` that uses cosine similarity over a local embedding model (sentence-transformers or equivalent).
- Class: quality-attribute
- Status: deferred
- Description: In addition to FTS5, store embeddings per transcript and offer `vidscope search --semantic` that uses cosine similarity over a local embedding model (sentence-transformers or equivalent).
- Why it matters: Makes "find videos about X" work even when X is not a literal keyword in the transcript. Deferred because FTS5 is enough for v1.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Implied by user's note on scalability. Lands alongside a potential Postgres + pgvector migration.

## Out of Scope

### R030 — VidScope does not republish, repost, or redistribute any ingested media. Downloaded files stay on the local machine for personal analysis only.
- Class: anti-feature
- Status: out-of-scope
- Description: VidScope does not republish, repost, or redistribute any ingested media. Downloaded files stay on the local machine for personal analysis only.
- Why it matters: Prevents scope creep into content-generation territory and keeps the tool aligned with its veille purpose.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The `data/` folder is gitignored and the tool never uploads anywhere.

### R031 — VidScope does not cut, edit, re-encode beyond what is needed for frame extraction, or produce new video files from ingested content.
- Class: anti-feature
- Status: out-of-scope
- Description: VidScope does not cut, edit, re-encode beyond what is needed for frame extraction, or produce new video files from ingested content.
- Why it matters: ffmpeg can do all of this but it's a different product. VidScope is a reader, not an editor.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Frame extraction is the only ffmpeg operation in scope.

### R032 — VidScope is a single-user local tool. No web UI, no authentication layer, no multi-tenant considerations, no cloud deployment target.
- Class: constraint
- Status: out-of-scope
- Description: VidScope is a single-user local tool. No web UI, no authentication layer, no multi-tenant considerations, no cloud deployment target.
- Why it matters: Keeps the surface small and the architecture honest — no spurious HTTP layers, no accidentally-public data.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The MCP server in M002 is a local stdio integration, not an HTTP service.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | active | M001/S02 | none | S02 shipped YtdlpDownloader + IngestStage + container wiring + integration tests. Validated on real networks for YouTube Shorts (19s short downloaded, metadata extracted, row persisted, media file on disk) and TikTok videos (same full round-trip). Instagram is XFAIL'd because Meta now requires authentication even for public Reels — see R025 which is deferred to M005 for cookie-based ingestion. Short-form target profile (D026) means YouTube Shorts / Instagram Reels / TikTok videos are the validated content shape, not long-form YouTube. |
| R002 | core-capability | active | M001/S03 | none | S03 shipped: FasterWhisperTranscriber adapter + TranscribeStage + container wiring + integration tests. Validated on live YouTube Short (transcription completes in ~6.5s on CPU with int8 quantization, model 'base'). TikTok also ingests + transcribes successfully (instrumental video → empty transcript is a legitimate outcome). Instagram path conditional on R025 cookies. Default device='cpu' / compute_type='int8' matches D008. |
| R003 | core-capability | active | M001/S04 | none | S04 shipped: FfmpegFrameExtractor adapter + FramesStage + container wiring + integration tests. Validated on live YouTube Short and TikTok video: frame extraction completes in ~1s per video, frames are stored under MediaStorage at canonical keys (videos/{platform}/{platform_id}/frames/{index:04d}.jpg), and the frames table has rows linked to the video. Default 0.2 fps (1 frame per 5 seconds), capped at 30 frames per video (D016/R003 notes). |
| R004 | core-capability | active | M001/S05 | none | S05 shipped: HeuristicAnalyzer + AnalyzeStage + container wiring. Validated on live YouTube + TikTok: every video produces an analyses row with provider='heuristic', detected language, top keywords (frequency-based, stopwords excluded), top topics, score in [0, 100], summary truncated to ~200 chars. Pure-Python implementation, zero network calls, zero paid API. Empty transcripts produce score=0 and summary='no speech detected' so the row exists for the FTS5 index in S06. |
| R005 | core-capability | active | M001/S01 | M001/S02, M001/S03, M001/S04, M001/S05, M001/S06 | Schema + repository layer implemented and tested in S01 (185 tests including 52 adapter-level tests, 29 infrastructure tests). Every row is addressable by stable id, FKs are enforced via PRAGMA, FTS5 virtual table is live. Full validation pending S02-S06 which write real rows through the pipeline. |
| R006 | core-capability | active | M001/S06 | M001/S01 | S06 shipped: IndexStage as 5th pipeline stage writes transcripts and analysis summaries to FTS5 search_index virtual table. vidscope search "<query>" returns ranked hits with snippets. Validated end-to-end on live YouTube Short: ingest → transcribe → frames → analyze → index → search('music') returns 2 hits (one transcript, one analysis_summary). CLI command vidscope search wired to SearchLibraryUseCase which queries the SearchIndex port. |
| R007 | primary-user-loop | active | M001/S06 | M001/S02, M001/S03, M001/S04, M001/S05 | S06 closes R007 end-to-end: vidscope add <url> performs ingest → transcribe → frames → analyze → index in one invocation, reports a structured summary on exit, partial success leaves consistent DB state because every stage commits transactionally with its pipeline_runs row. Validated via verify-m001.sh on live YouTube Short. Failures at any stage are surfaced via the typed DomainError + pipeline_runs.error column, visible in vidscope status. |
| R008 | failure-visibility | active | M001/S06 | M001/S01 | S06 closes R008: vidscope status shows the last N pipeline_runs with phase, status, video, started, duration, error (truncated). vidscope show <id> displays full record (video metadata + transcript info + frames count + analysis info). Re-running vidscope add on a previously ingested video resumes from the last incomplete stage thanks to is_satisfied checks on transcribe/frames/analyze (D025 documents that ingest currently always re-downloads but the videos row is upserted idempotently). |
| R009 | operability | active | M001/S01 | M001/S02 | S01 verified: package installs via `uv sync` on Windows from a fresh clone, runs without modification, uses platformdirs for cross-platform paths, MediaStorage uses slash-separated string keys so the domain is OS-agnostic. Startup checks detect missing ffmpeg/yt-dlp with platform-specific remediation (Windows winget, macOS brew, Linux apt). Full cross-OS validation (macOS, Linux) pending — currently only Windows 10/11 is exercised. |
| R010 | quality-attribute | active | M001/S05 | none | S05 shipped the pluggable analyzer seam: build_analyzer(name) registry in vidscope.infrastructure.analyzer_registry maps provider names to Analyzer instances. Two providers registered (HeuristicAnalyzer, StubAnalyzer) to prove the seam works with multiple implementations. M004 will add LLM-backed providers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic) by extending _FACTORIES; container wiring code will not change. Analyzer selected via VIDSCOPE_ANALYZER env var (default 'heuristic'). |
| R020 | integration | active | M002 | none | unmapped |
| R021 | primary-user-loop | validated | M003 | none | M003/S02 + S03. WatchAccountRepository CRUD validated by 14 unit tests, 4 watchlist use cases by 23 unit tests, vidscope watch sub-application by 11 CLI tests, full E2E flow by verify-m003.sh demo. |
| R022 | operability | validated | M003 | none | M003/S02 + S03. RefreshWatchlistUseCase iterates accounts, dedupes against existing videos, runs new URLs through PipelineRunner, persists WatchRefresh row. Idempotence validated by verify-m003.sh (second refresh = 0 new). Per-account error capture validated by unit tests. Scheduling delegated to OS cron/launchd/Task Scheduler — documented in docs/watchlist.md. |
| R023 | differentiator | active | M002/S02 | none | S02 shipped: SuggestRelatedUseCase with Jaccard keyword overlap (pure Python, zero deps) + `vidscope suggest <id>` CLI + `vidscope_suggest_related` MCP tool. Validated by 11 unit tests covering happy path + 6 edge cases + score ordering, 3 MCP tool unit tests, 2 subprocess integration tests. Score = |source_kw ∩ candidate_kw| / |source_kw ∪ candidate_kw|. Semantic embeddings (R026) remain deferred. |
| R024 | quality-attribute | validated | M004 | M004/S01, M004/S02, M004/S03 | M004 shipped 5 concrete LLM provider adapters (Groq, NVIDIA Build, OpenRouter, OpenAI, Anthropic) under vidscope.adapters.llm. Each provider is a single file ~50 lines (OpenAI-compatible) or ~150 lines (Anthropic native /v1/messages). Shared _base.py provides build_messages, parse_llm_json, call_with_retry, make_analysis, run_openai_compatible. Registry exposes 7 names (heuristic, stub, groq, nvidia, openrouter, openai, anthropic). Each provider reads its API key from VIDSCOPE_<PROVIDER>_API_KEY at factory invocation time. New 9th import-linter contract (llm-never-imports-other-adapters) structurally enforces the one-file-per-provider rule. 120 new LLM-related unit tests (34 base + 17 groq + 9 nvidia + 9 openrouter + 10 openai + 21 anthropic + 19 registry + 6 startup) all via httpx.MockTransport — zero real network. vidscope doctor reports the active analyzer + key status. docs/analyzers.md documents every provider with cost/quotas/signup URLs. verify-m004.sh runs 9 steps including all 4 quality gates + per-provider stub HTTP smoke + doctor check, exits 0. |
| R025 | core-capability | validated | M005 | M001/S07, M005/S01, M005/S02, M005/S03 | Cookies UX completed in M005. Plumbing shipped in M001/S07 (VIDSCOPE_COOKIES_FILE env var, doctor cookies row, ytdlp downloader cookies_file param). M005/S01 added validate_cookies_file pure-Python helper + 3 use cases (Set/GetStatus/Clear) + vidscope cookies sub-application with set/status/clear subcommands. M005/S02 added vidscope cookies test (probe via stubbed-network Downloader.probe Protocol method on the YtdlpDownloader) + CookieAuthError typed domain error subclassing IngestError + auth-marker detection in ytdlp adapter (10-element marker tuple) so vidscope add error remediation points at vidscope cookies test. M005/S03 rewrote docs/cookies.md as a 5-minute walkthrough using the new subcommands + shipped verify-m005.sh (10/10 steps green via stubbed yt_dlp). Architectural improvement: tightened application-has-no-adapters contract to forbid vidscope.infrastructure imports. 60 new cookies-related unit tests (15 validator + 21 use case + 15 CLI + 9 ytdlp probe/auth detection). All 4 quality gates clean throughout. Instagram Reels are now usable in 4 commands: export from browser, vidscope cookies set <path>, vidscope cookies test, vidscope add <url>. |
| R026 | quality-attribute | deferred | none | none | unmapped |
| R030 | anti-feature | out-of-scope | none | none | n/a |
| R031 | anti-feature | out-of-scope | none | none | n/a |
| R032 | constraint | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 12
- Mapped to slices: 12
- Validated: 4 (R021, R022, R024, R025)
- Unmapped active requirements: 0

---

## M012 — Content Intelligence (v1.12)

### R060 — Pour tout contenu ingéré (carousel, image, reel, vidéo), la description/caption du post est capturée et stockée dans `videos.description` au moment de l'ingestion.
- Class: core-capability
- Status: active
- Description: InstaLoaderDownloader mappe `post.caption` → `description`. YtdlpDownloader mappe `info["description"]` → `description` quand disponible. Le champ existe en DB mais reste null aujourd'hui pour les deux types.
- Why it matters: La caption contient hashtags, mentions, liens, contexte éditorial — c'est la donnée primaire que le créateur a choisie. Sans elle, un carousel est muet pour un agent.
- Source: user
- Primary owning slice: M012/S01
- Supporting slices: none

### R061 — L'engagement initial (like_count, comment_count) est peuplé à l'ingestion depuis le downloader quand la plateforme le fournit, créant un enregistrement video_stats sans nécessiter `vidscope refresh-stats`.
- Class: core-capability
- Status: active
- Description: InstaLoaderDownloader : `post.likes` → `like_count`, `post.comments` → `comment_count`. YtdlpDownloader : `info.get("like_count")`, `info.get("comment_count")`. Crée une ligne video_stats si au moins une valeur non-null.
- Why it matters: Aujourd'hui `vidscope show` affiche "Aucune stat capturée" pour tout contenu fraîchement ingéré. L'engagement est disponible à l'ingestion mais ignoré.
- Source: user
- Primary owning slice: M012/S01
- Supporting slices: none

### R062 — Pour les contenus image/carousel (sans audio), l'AnalyzeStage produit une analyse en utilisant le texte OCR (frame_texts) comme substitut du transcript.
- Class: core-capability
- Status: active
- Description: Quand `transcript is None` ET `frame_texts` existent, l'AnalyzeStage concatène les textes OCR et les passe à l'analyzer. Le résultat analysis inclut provider, keywords, topics, score, summary basés sur l'OCR. `analysis: null` ne doit plus apparaître pour un carousel ayant du texte extracté.
- Why it matters: Le carousel "Claude skills for Architects!" a 848 blocs OCR et `analysis: null`. Un agent interrogeant get_video voit un contenu opaque alors que toute l'intelligence est là, en DB, non utilisée.
- Source: user
- Primary owning slice: M012/S02
- Supporting slices: none

### R063 — L'analyse heuristique filtre les stopwords français et anglais des keywords et topics (listes d'au moins 100 mots chacune).
- Class: quality-attribute
- Status: active
- Description: Les topics actuels ("c'est", "chemins", "veux") sont des mots grammaticaux sans valeur sémantique. Un filtre stopwords FR+EN doit les exclure avant le tri fréquentiel. Résultat attendu : topics = termes significatifs du domaine (ex. "terminal", "claude", "agent").
- Why it matters: L'analyzer heuristique est le provider par défaut (zero cost). Des topics vides de sens dégradent search + suggest_related + MCP analysis.
- Source: user
- Primary owning slice: M012/S02
- Supporting slices: none

### R064 — `vidscope_get_video` inclut `description` et `latest_engagement` (like_count, comment_count depuis video_stats) dans sa réponse MCP.
- Class: integration
- Status: active
- Description: Le dict de réponse actuel de vidscope_get_video n'inclut pas `description` ni les compteurs d'engagement. Ajouter ces champs (null si absents) pour que l'agent ait un portrait complet en un appel.
- Why it matters: Un agent doit aujourd'hui faire 2-3 appels (get_video + trending/stats) pour avoir le portrait complet. Réduire la friction agent est le but du MCP.
- Source: user
- Primary owning slice: M012/S03
- Supporting slices: none

### R065 — Pour les carousels, `vidscope_get_video` inclut un champ `ocr_preview` (les 5 premiers blocs OCR concaténés) et signale que `vidscope_get_frame_texts` expose le contenu complet.
- Class: integration
- Status: active
- Description: Un agent recevant un carousel voit aujourd'hui transcript=null, analysis=null. Après R062, analysis sera peuplée. En complément, ocr_preview donne un aperçu textuel immédiat sans 2e appel.
- Why it matters: Cohérence de l'expérience agent : carousel et reel doivent offrir un niveau de lisibilité comparable en un seul appel MCP.
- Source: user
- Primary owning slice: M012/S03
- Supporting slices: none

### R066 — Audit et suppression du dead code entre InstaLoaderDownloader, YtdlpDownloader, FallbackDownloader et le pipeline : incohérences dans les champs IngestOutcome mappés, logique dupliquée, simplifications identifiées appliquées.
- Class: quality-attribute
- Status: active
- Description: L'ajout de InstaLoader + FallbackDownloader en M011-session a introduit des chemins non couverts (probe non implémenté, list_channel_videos raise immédiat). Un audit cross-adapter identifie les champs manquants, les chemins morts, et les patterns à unifier.
- Why it matters: Le code hérité d'un sprint rapide accumule de la dette silencieuse. L'audit garantit que les nouveaux adapters sont aussi solides que les anciens.
- Source: user
- Primary owning slice: M012/S04
- Supporting slices: none
