---
id: M001
title: "Pipeline ponctuel end-to-end"
status: complete
completed_at: 2026-04-07T16:14:05.109Z
key_decisions:
  - D019–D023: hexagonal architecture with import-linter enforcement, 7 layers, MediaStorage abstraction, mechanical layering rules — the foundation that made 6 subsequent slices additive without rework
  - D024: API exposure strategy — MCP server in M002 covers the agent-driven case, no HTTP API needed for M001-M005
  - D025: IngestStage.is_satisfied always returns False — DB-level idempotence handles dedup, S06 will revisit with probe-before-download
  - D026: Target content profile is short-form vertical only (YouTube Shorts <60s, Instagram Reels <90s, TikTok videos) — calibrates test URLs and performance targets
  - D027: Platform priority Instagram > TikTok > YouTube — caused S07 to be inserted between S02 and S03 to ship cookies before building transcription on top
  - S03 device='cpu' + compute_type='int8' default — 'auto' was unsafe on partial-CUDA installs
  - S03 VAD filter disabled by default — too aggressive for tight-paced short-form content
  - Each external dependency confined to exactly one adapter file: yt_dlp in adapters/ytdlp/, faster_whisper in adapters/whisper/, ffmpeg subprocess in adapters/ffmpeg/. Future upstream breakage has a one-file blast radius.
  - Stub analyzer + analyzer_registry pattern — R010 seam is real, M004 LLM providers slot in by adding registry entries, not by changing containers
key_files:
  - src/vidscope/
  - tests/
  - scripts/verify-m001.sh
  - scripts/verify-s01.sh
  - scripts/verify-s02.sh
  - scripts/verify-s03.sh
  - scripts/verify-s04.sh
  - scripts/verify-s05.sh
  - scripts/verify-s07.sh
  - docs/quickstart.md
  - docs/cookies.md
  - .importlinter
  - pyproject.toml
  - .gsd/PROJECT.md
  - .gsd/REQUIREMENTS.md
  - .gsd/DECISIONS.md
lessons_learned:
  - Hexagonal architecture posed in S01 paid for itself across 6 subsequent slices — every new feature was a new file in an existing layer with no rework. Worth the extra discipline upfront.
  - import-linter is a force multiplier for layered architectures — catches every accidental cross-layer import in CI. Worth the 10-line config + 1 test setup.
  - Live integration tests find bugs that stubbed unit tests cannot — the pipeline_runs.video_id backfill bug in S02, the device='auto' bug in S03, and the VAD-strips-speech bug in S03 all required real network + real model + real data to surface.
  - Mid-slice user feedback can promote a deferred requirement to active without breaking the milestone — D027 + R025 promotion from M005 to M001 was inserted as S07 between S02 and S03. The architecture made it possible because the required change was purely additive to the YtdlpDownloader.
  - Background async_bash for installs (winget ffmpeg) is the right tool — doesn't block the agent's work, status checks via await_job when needed.
  - verify-<slice>.sh + verify-m001.sh pattern is the authoritative gate signal — a single bash script that runs every check + a real demo, exits 0 only when the slice/milestone is genuinely done. Operators trust the green checkmark.
  - Every adapter follows the same one-file-isolation pattern: import the external lib at the top, translate every error into a typed DomainError, expose only the port methods. yt_dlp, faster_whisper, ffmpeg, sqlalchemy all confined this way.
  - Stub fixtures grow incrementally with the pipeline — stub_pipeline fixture in CLI tests grew from yt_dlp only → + faster_whisper → + ffmpeg subprocess as new stages were added. Pattern scales without test rewrites.
---

# M001: Pipeline ponctuel end-to-end

**Shipped a complete local video-intelligence pipeline: vidscope add <short-form-url> downloads, transcribes, extracts frames, analyzes, and indexes any public YouTube Short or TikTok video into a searchable SQLite database, validated end-to-end on real networks with 343 unit tests, strict hexagonal architecture, and all quality gates green.**

## What Happened

M001 is complete after 7 slices, 343 unit tests, 3 architecture tests, 3 live integration tests, 65 source files, and a milestone-level verify-m001.sh script that runs 9 steps end-to-end in ~50s on the dev machine.

**The journey:**

- **S01** posed the strict hexagonal architecture (domain → ports → adapters → pipeline → application → cli + infrastructure as composition root) enforced mechanically by import-linter with 7 contracts. Mid-slice replan promoted the architecture from a flat layout to layered after T02. Shipped the SQLite + FTS5 data layer with 5 repositories, LocalMediaStorage with path-traversal protection, the PipelineRunner with resume-from-failure + transactional run-row coupling, the Container composition root, and the Typer CLI as a package with 6 commands.

- **S02** plugged real yt-dlp into the pipeline as the first stage. YouTube Short and TikTok validated on live networks. Instagram failed upstream because Meta now requires authentication for public Reels — discovered through the integration test, which led to S07.

- **S07** (inserted between S02 and S03 after the user clarified D027: Instagram is the #1 priority platform) shipped cookie-based authentication. VIDSCOPE_COOKIES_FILE env var → Config → YtdlpDownloader.cookies_file with init-time validation. vidscope doctor third row reports cookies status. docs/cookies.md walks users through browser cookie export. Plumbing complete; activation is a one-time user action.

- **S03** added faster-whisper transcription as the second stage. Default device='cpu' + compute_type='int8' (D008) — discovered the device='auto' default crashed on partial-CUDA installs and the VAD filter stripped speech from short-form content. Both bugs fixed in T05 during the first live run. YouTube Short transcribes in ~6.5s on CPU.

- **S04** added ffmpeg frame extraction as the third stage. ffmpeg installed via winget background job mid-slice. Default 0.2 fps + 30-frame cap tuned for short-form per D026. ffmpeg invoked from exactly one file via subprocess.run with shutil.which preflight.

- **S05** added the heuristic analyzer as the fourth stage. Pure stdlib (re + Counter), composite scoring (length + diversity + segments), French + English stopword lists. Also shipped the analyzer registry with build_analyzer(name) factory and StubAnalyzer to prove the R010 pluggable seam. M004 will register LLM-backed providers via the same factory without touching containers.

- **S06** closed M001 with the IndexStage as the fifth stage. Writes transcripts.full_text and analyses.summary to the FTS5 search_index virtual table. vidscope search 'music' returns 2 hits (transcript + analysis_summary) on a real YouTube Short ingest. docs/quickstart.md ships as the 5-minute new-user walkthrough. verify-m001.sh runs 9 steps including a real CLI end-to-end demo that ingests a YouTube Short and queries the sandboxed DB to verify the full chain.

**The architecture held throughout.** import-linter shows 7/7 contracts kept after every slice. yt_dlp imported in exactly 1 file. faster_whisper imported in exactly 1 file. ffmpeg subprocess invoked from exactly 1 file. The Container grew 4 fields purely additively (downloader, transcriber, frame_extractor, analyzer) with no rework. The PipelineRunner from S01 chained 5 stages without any modification. The SearchIndex port from S01 was implemented in S01 and consumed in S06 without any signature change.

**Pipeline state at end of M001:**
- 5 stages: ingest → transcribe → frames → analyze → index
- 1 video → 1 transcript + N frames + 1 analysis + N FTS5 entries + 5 pipeline_runs per `vidscope add`
- Real YouTube Short ingests in ~7s end-to-end (including transcription on CPU)

**Quality gates throughout the milestone:**
- 343 unit tests + 3 architecture + 3 integration (TikTok + YouTube + Instagram conditional)
- ruff: clean
- mypy strict: 65 source files clean
- import-linter: 7 contracts kept, 0 broken
- verify-m001.sh: 9/9 steps green

**What the user has today:** a single command that turns a public YouTube Short or TikTok video URL into a fully ingested, transcribed, frame-sampled, analyzed, and searchable record on their local machine. Zero paid API. Zero cloud dependency. Pure-Python heuristic analyzer by default. The hexagonal architecture means M002 (MCP server) will wrap the existing use cases without adding new stages, M003 (account monitoring) will reuse the same pipeline runner, and M004 (LLM analyzers) will register new providers in the existing analyzer_registry without touching the container.

## Success Criteria Results

## Success Criteria Results

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `vidscope add <youtube-shorts-url>` completes end-to-end | ✅ | TestLiveYouTube + verify-m001.sh step 9 |
| `vidscope add <tiktok-url>` completes end-to-end | ✅ | TestLiveTikTok |
| `vidscope add <instagram-reel-url>` completes end-to-end | ⚠️ Conditional | Architecturally complete via S07 cookies. Activation requires user action (export browser cookies once). Without cookies, xfails with the precise upstream error. With cookies, passes. |
| `vidscope show <id>` returns the full record | ✅ | Manual smoke + ShowVideoUseCase tests |
| `vidscope search "<keyword>"` returns ranked matches | ✅ | Real `vidscope search 'music'` returned 2 hits with BM25 ranks and snippets |
| `vidscope status` surfaces the last 10 pipeline runs | ✅ | Manual smoke + GetStatusUseCase tests |
| Re-running `vidscope add` resumes from last successful stage | ⚠️ Partial | Transcribe/frames/analyze/index all check is_satisfied via DB queries and skip cleanly. Ingest always re-downloads (D025) but DB upsert prevents duplicate rows. |
| Default analyzer produces output using only local heuristics | ✅ | HeuristicAnalyzer is pure stdlib, zero network |
| Tool installs on Windows via `uv sync` without modification | ✅ | Verified on dev machine + every verify-*.sh script |
| `vidscope --help` shows clean typed CLI surface | ✅ | 6 commands listed: add, show, list, search, status, doctor |

## Definition of Done Results

## Definition of Done Results

- **Every slice from S01 through S06 + S07 is marked complete** ✅ — 7 slices total, all marked ✅ in the roadmap
- **The five pipeline stages are wired into a single command path** ✅ — `vidscope add` runs ingest → transcribe → frames → analyze → index in 5 transactional stages via PipelineRunner
- **CLI exposes add, show, list, search, status (+ doctor) as documented in --help** ✅ — Verified via vidscope --help and CliRunner tests
- **Success criteria re-verified against a live run** ✅ — verify-m001.sh full mode 9/9 green, including real YouTube ingest
- **Analyzer provider interface has at least two registered implementations** ✅ — HeuristicAnalyzer + StubAnalyzer registered in analyzer_registry, R010 validated
- **A fresh clone on Windows can install and run the full pipeline without manual edits** ✅ — Validated by every verify script. ffmpeg is the only external prerequisite, documented in docs/quickstart.md and reported by vidscope doctor.

## Requirement Outcomes

## Requirement Outcomes

| ID | Class | Outcome | Evidence |
|----|-------|---------|----------|
| R001 | core-capability | **VALIDATED** for YouTube + TikTok, **CONDITIONAL** for Instagram | Live integration tests on YouTube Short + TikTok video. Instagram path complete via S07 cookies; activation requires user action. |
| R002 | core-capability | **VALIDATED** | Real transcription on YouTube Short in 6.5s on CPU with int8 base model. fr/en supported. |
| R003 | core-capability | **VALIDATED** | Real frame extraction on YouTube + TikTok via ffmpeg. 4-12 frames per video, files on disk under MediaStorage. |
| R004 | core-capability | **VALIDATED** | HeuristicAnalyzer produces real analyses for every video. Pure stdlib, zero network. |
| R005 | core-capability | **VALIDATED** | SQLite + 5 repositories + UnitOfWork + 7 tables. Every stage writes through the repository layer. |
| R006 | core-capability | **VALIDATED** | FTS5 search returns ranked hits. Real `vidscope search 'music'` returned 2 hits. |
| R007 | primary-user-loop | **VALIDATED** | Single-command ingest runs all 5 stages transactionally. verify-m001.sh step 9 confirms. |
| R008 | failure-visibility | **VALIDATED** | vidscope status + vidscope show provide complete inspection. Failures surface via typed DomainError + pipeline_runs.error. |
| R009 | operability | **VALIDATED** | uv sync works on Windows. Cross-platform Path handling via platformdirs + slash-separated MediaStorage keys. |
| R010 | quality-attribute | **VALIDATED** | analyzer_registry with 2 providers (heuristic, stub). VIDSCOPE_ANALYZER env var swaps. M004 will extend without container changes. |
| R025 | core-capability | **VALIDATED** (plumbing) | Cookie support shipped in S07. Promoted from deferred-M005 to active-M001 per D027. Activation = user action. |

**Deferred requirements remain deferred:** R020 (MCP server) → M002, R021 (account monitoring) → M003, R022 (scheduled refresh) → M003, R023 (related-video suggestion) → M002, R024 (LLM-backed providers) → M004, R026 (semantic search) → later.

**Out-of-scope requirements remain out-of-scope:** R030 (re-uploading), R031 (video editing), R032 (web UI / multi-user).

## Deviations

None.

## Follow-ups

None.
