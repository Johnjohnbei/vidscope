# M001: Pipeline ponctuel end-to-end

**Vision:** A single command (`vidscope add <url>`) turns a public Instagram, TikTok, or YouTube video URL into a fully ingested, transcribed, frame-sampled, analyzed, and searchable record on the local machine — with zero paid API calls and zero cloud dependency.

## Success Criteria

- `vidscope add <instagram-reel-url>` completes end-to-end on a public Reel and leaves a consistent DB row with metadata, transcript, at least one frame, and an analysis record
- Same command succeeds on a public TikTok URL and a public YouTube video URL
- `vidscope show <id>` returns the full record (metadata, transcript segments, frames list, analysis) for a previously ingested video
- `vidscope search "<keyword>"` returns ranked matches from the stored transcripts and summaries via FTS5
- `vidscope status` surfaces the last 10 pipeline runs, their stage outcomes, and any errors — without requiring a log dive
- Re-running `vidscope add <url>` on a video that previously failed mid-pipeline resumes from the last successful stage instead of restarting from scratch
- The default analyzer produces its output using only local heuristics — no network calls, no API keys required
- The tool installs on Windows via `uv tool install .` (from a cloned repo) and runs without modification; cross-platform Python APIs are used throughout
- `vidscope --help` shows a clean, typed CLI surface with at least `add`, `show`, `list`, `search`, and `status` subcommands

## Key Risks / Unknowns

- yt-dlp support for Instagram is the single most fragile brick — Instagram changes its API occasionally and yt-dlp typically patches within 1–2 days, but during that window ingestion can fail. We need a clean surfacing of that failure mode.
- faster-whisper performance on CPU is acceptable for short Reels (30s–2min) but can become painful for YouTube videos above 10 minutes. We need to measure on a real sample and decide whether to cap duration or accept slow runs.
- Windows path handling with ffmpeg and yt-dlp has historical footguns (spaces in paths, CRLF in stdin, unicode filenames). We need to prove the pipeline works on Windows from day one — not just Linux in CI.
- SQLite FTS5 on transcripts is straightforward, but the indexing step must stay consistent with the normal insert path. A bug here silently breaks search without breaking ingestion.

## Proof Strategy

- yt-dlp / Instagram fragility → retire in S02 by proving ingestion of a real public Reel URL from a live run, with the error path exercised by feeding a deliberately invalid URL and confirming a clean structured error
- faster-whisper CPU throughput → retire in S03 by transcribing both a 30s Reel and a 3–5 minute video on the actual dev machine and recording the wall-clock time in the slice summary
- Windows path and binary handling → retire across S02 and S04 by running the real subprocess calls on Windows with a path that contains a space and confirming no quoting errors
- FTS5 / insert consistency → retire in S06 by indexing a known transcript, searching for a term that exists, and confirming the row is returned with a rank > 0

## Verification Classes

- Contract verification: pytest unit tests for the repository layer, the analyzer heuristics, and the CLI command dispatch; ruff and mypy clean on all source files
- Integration verification: real end-to-end run of `vidscope add` on one live public URL per platform (Instagram, TikTok, YouTube), writing to an ephemeral DB, with assertions on the resulting rows
- Operational verification: resume-from-failure behavior exercised by forcing a stage failure and re-running `add` to confirm partial state is reused; `vidscope status` reflects the failure correctly
- UAT / human verification: manual confirmation by the user that `vidscope add <their-chosen-reel>` produces a record they find useful — transcript reads correctly in French, analysis captures the right keywords, frames look representative

## Milestone Definition of Done

This milestone is complete only when all are true:

- Every slice from S01 through S06 is marked complete with its own summary
- The five pipeline stages (ingest, transcribe, frames, analyze, index) are wired together in a single command path (`vidscope add`) that writes to the same DB
- The CLI exposes `add`, `show`, `list`, `search`, and `status` as documented in `--help`
- Success criteria above are re-verified against a live run, not just against unit tests
- The analyzer provider interface has at least two registered implementations (heuristics + a stub placeholder) to prove the seam works
- A fresh clone of the repo on Windows can install and run the full pipeline on a public URL without manual edits

## Requirement Coverage

- Covers: R001, R002, R003, R004, R005, R006, R007, R008, R009, R010
- Partially covers: none
- Leaves for later: R020 (MCP), R021 (account monitoring), R022 (scheduled), R023 (related-video), R024 (LLM providers), R025 (cookies), R026 (semantic search)
- Orphan risks: none

## Slices

- [ ] **S01: Project socle, data layer and CLI skeleton** `risk:medium` `depends:[]`
  > After this: a fresh clone installs via `uv tool install .`, `vidscope --help` lists all planned subcommands as stubs, the SQLite DB is created with the full schema on first run, and `vidscope status` returns an empty-but-valid report.
- [ ] **S02: Ingestion brick (yt-dlp) for Instagram, TikTok and YouTube** `risk:high` `depends:[S01]`
  > After this: `vidscope add <url>` downloads the media file for a public URL on each of the three platforms, writes a `videos` row with metadata, writes a `pipeline_runs` row with the ingest stage result, and surfaces a clean error on an invalid URL.
- [ ] **S03: Transcription brick (faster-whisper)** `risk:medium` `depends:[S02]`
  > After this: `vidscope add <url>` on a public Reel produces a full transcript and timestamped segments stored in the DB, with wall-clock timing recorded in the pipeline run; French and English both verified.
- [ ] **S04: Frame extraction brick (ffmpeg)** `risk:low` `depends:[S02]`
  > After this: `vidscope add <url>` extracts keyframes plus a fixed-rate sample from the downloaded media, stores the image files on disk, and records their paths and timestamps in the `frames` table.
- [ ] **S05: Heuristic analyzer with pluggable provider interface** `risk:medium` `depends:[S03]`
  > After this: `vidscope add <url>` produces a complete analysis record (language, keywords, topics, relevance score, short summary) via the default heuristic provider, and a second stub provider is registered to prove the seam works.
- [ ] **S06: End-to-end wiring, FTS5 index, search and status commands** `risk:medium` `depends:[S01,S02,S03,S04,S05]`
  > After this: `vidscope add`, `show`, `list`, `search`, and `status` all work end-to-end on a live public URL for each of the three platforms, FTS5 returns ranked matches, resume-from-failure is demonstrated, and the full milestone definition of done is verified.

## Horizontal Checklist

- [ ] Every active R### re-read against new code — still fully satisfied?
- [ ] Graceful shutdown / cleanup on termination verified (pipeline doesn't leave partial rows on Ctrl-C)
- [ ] Auth boundary documented — what's protected vs public (public URLs only in M001; cookies deferred to M005)
- [ ] Shared resource budget confirmed — whisper model cache, download cache, frame cache directories respected
- [ ] Reconnection / retry strategy verified for every external dependency (yt-dlp, ffmpeg, whisper model download)

## Boundary Map

### S01 → S02

Produces:
- `src/vidscope/db/` module exposing a repository layer with at minimum `Videos`, `Transcripts`, `Frames`, `Analyses`, `PipelineRuns` tables and their CRUD functions
- `src/vidscope/cli.py` Typer application with stub subcommands (`add`, `show`, `list`, `search`, `status`) that parse args and return a typed placeholder
- A config surface (`src/vidscope/config.py`) that resolves the data directory, cache directory, and default model per platform
- A startup check that verifies `ffmpeg` and `yt-dlp` are available and emits a clean error otherwise

Consumes:
- nothing (first slice)

### S01 → S03 (via S02)

Produces (additionally via S02):
- A downloaded media file path persisted in the `videos` row
- A `videos.platform_id` stable unique key used to detect duplicates on re-runs

Consumes:
- nothing beyond S01 at this hop

### S01 → S04 (via S02)

Produces (additionally via S02):
- Same as S03: the media file path, reachable from the `videos` row

Consumes:
- nothing beyond S01 at this hop

### S02 → S03

Produces:
- For each ingested video, a `videos.media_path` pointing to a decoded audio-capable file that faster-whisper can open
- A `pipeline_runs` row with stage=`ingest` and result=`ok` that S03 checks before attempting transcription

Consumes:
- `src/vidscope/db/` from S01

### S02 → S04

Produces:
- Same `videos.media_path` usable by ffmpeg for frame extraction

Consumes:
- `src/vidscope/db/` from S01

### S03 → S05

Produces:
- `transcripts.full_text` and `transcripts.segments` populated for the target video
- A stable transcript ID referenced from the analyzer input

Consumes:
- `videos.media_path` from S02, `src/vidscope/db/` from S01

### S04 → S06

Produces:
- `frames` rows with image paths on disk that `vidscope show` displays

Consumes:
- `videos.media_path` from S02

### S05 → S06

Produces:
- `analyses` rows with language, keywords, topics, score, and summary, populated by a registered analyzer provider
- The analyzer provider registry (`src/vidscope/analyzer/providers.py`) listing all available providers so `vidscope status --providers` can show them

Consumes:
- `transcripts.full_text` from S03, `videos` metadata from S02

### S06 → (milestone integration)

Produces:
- The full `vidscope add` pipeline invocation chaining S02 → S03 → S04 → S05 → index
- The FTS5 virtual table and its triggers keeping it consistent with `transcripts` and `analyses`
- The `search`, `show`, `list`, and `status` commands reading exclusively through the repository layer

Consumes:
- Everything above
