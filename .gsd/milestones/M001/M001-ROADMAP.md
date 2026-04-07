# M001: M001: Pipeline ponctuel end-to-end

## Vision
A single command (`vidscope add <url>`) turns a public Instagram, TikTok, or YouTube video URL into a fully ingested, transcribed, frame-sampled, analyzed, and searchable record on the local machine — with zero paid API calls and zero cloud dependency.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Project socle, data layer and CLI skeleton | medium | — | ✅ | a fresh clone installs via `uv tool install .`, `vidscope --help` lists all planned subcommands as stubs, the SQLite DB is created with the full schema on first run, and `vidscope status` returns an empty-but-valid report. |
| S02 | Ingestion brick (yt-dlp) for Instagram, TikTok and YouTube | high | S01 | ✅ | `vidscope add <url>` downloads the media file for a public URL on each of the three platforms, writes a `videos` row with metadata, writes a `pipeline_runs` row with the ingest stage result, and surfaces a clean error on an invalid URL. |
| S03 | Transcription brick (faster-whisper) | medium | S02 | ✅ | `vidscope add <url>` on a public Reel produces a full transcript and timestamped segments stored in the DB, with wall-clock timing recorded in the pipeline run; French and English both verified. |
| S04 | Frame extraction brick (ffmpeg) | low | S02 | ✅ | `vidscope add <url>` extracts keyframes plus a fixed-rate sample from the downloaded media, stores the image files on disk, and records their paths and timestamps in the `frames` table. |
| S05 | Heuristic analyzer with pluggable provider interface | medium | S03 | ✅ | `vidscope add <url>` produces a complete analysis record (language, keywords, topics, relevance score, short summary) via the default heuristic provider, and a second stub provider is registered to prove the seam works. |
| S06 | End-to-end wiring, FTS5 index, search and status commands | medium | S01, S02, S03, S04, S05 | ✅ | `vidscope add`, `show`, `list`, `search`, and `status` all work end-to-end on a live public URL for each of the three platforms, FTS5 returns ranked matches, resume-from-failure is demonstrated, and the full milestone definition of done is verified. |
| S07 | Cookie-based authentication for Instagram (and other gated content) | medium | S02 | ✅ | `vidscope add <instagram-reel-url>` succeeds end-to-end on a public Reel after the user supplies a `cookies.txt` file (or sets `VIDSCOPE_COOKIES_FILE`); R025 promoted from deferred to validated; the integration test for Instagram flips from xfail to passing. |
