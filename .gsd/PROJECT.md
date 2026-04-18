# VidScope

## What This Is

VidScope is a personal video-intelligence tool. Given a URL to a public video on Instagram, TikTok, or YouTube, it downloads the media locally, transcribes the audio, extracts representative frames, produces a structured analysis of the content, and stores everything in a searchable local database. It exposes both a CLI (`vidscope add <url>`, `vidscope search <query>`) and — in later milestones — an MCP server so an AI agent can query and enrich the library during conversation.

M001–M009 complete. M010 (scoring + taxonomy) and M011 (veille workflow) are scoped and ready.

## Core Value

A single command turns a video URL into a searchable, analyzable record on the local machine — no paid API, no cloud dependency, no manual copy-pasting. If every other feature is cut, this one must work: `vidscope add <url>` → transcript + frames + analysis + searchable DB entry.

## Current State

**M001–M009 complete.** The full single-video pipeline, MCP server, related-video suggestions, account watchlist, 5 pluggable LLM analyzer providers, polished cookies UX, creator-as-entity model, rich metadata (links/hashtags/mentions/music), visual intelligence (OCR/frames), and engagement velocity time-series are all alive.

**Platform priority (D027):** Instagram is the primary target, then TikTok, then YouTube.

**What works today:**
- **`vidscope add <url>`** downloads a YouTube Short, TikTok video, or Instagram Reel (with cookies) via yt-dlp, stores the media under `MediaStorage` at a stable key, transcribes the audio via faster-whisper, extracts ~10 frames via ffmpeg, runs the heuristic analyzer (or any registered analyzer), and indexes the resulting text into FTS5 — five stages, one transactional `pipeline_runs` row each.
- **`vidscope search <query>`** runs FTS5 against transcripts + analysis text.
- **`vidscope show <id>`**, **`vidscope list`**, **`vidscope status`** inspect the library.
- **`vidscope suggest <id>`** returns related videos by Jaccard similarity over keyword sets.
- **`vidscope mcp serve`** starts an MCP stdio server exposing 6 tools (ingest, search, get_video, list_videos, get_status, suggest_related) so agents can drive the library directly.
- **`vidscope watch add/list/remove/refresh`** tracks public accounts and refreshes them on demand. Refresh is idempotent, captures per-account errors without stopping iteration, and reuses the existing 5-stage pipeline for every newly discovered video.
- **`VIDSCOPE_ANALYZER=<provider>`** opts into one of 5 LLM analyzers (groq, nvidia, openrouter, openai, anthropic). Each provider lives in `vidscope/adapters/llm/<name>.py` behind a structurally enforced isolation contract. The default is `heuristic` — pure-Python, zero cost, zero network. Full guide in `docs/analyzers.md`.
- **`vidscope cookies set/status/test/clear`** manages the Netscape cookies file used by yt-dlp for gated platforms (Instagram primarily, age-gated YouTube secondarily). `vidscope cookies test` is the killer command: a metadata-only probe that verifies cookies authenticate without ingesting a real video. Failed `vidscope add` runs against gated platforms surface a typed `CookieAuthError` pointing the user at `vidscope cookies test`. Full guide in `docs/cookies.md`.
- **`vidscope doctor`** reports ffmpeg / yt-dlp / mcp / cookies / analyzer availability.

**Architecture:** strict hexagonal layering enforced by import-linter (9 contracts). 84 source files, mypy-strict-clean, 618 unit tests + 3 architecture tests + 2 MCP subprocess tests + 3 live ingest integration tests. Pipeline stages implement a common `Stage` Protocol; the runner handles resume-from-failure, transactional run-row coupling, and typed error dispatch. The 9th contract (`llm-never-imports-other-adapters`) structurally enforces "one LLM provider per file". M005 also tightened the `application-has-no-adapters` contract to forbid `vidscope.infrastructure` imports — closing a pre-existing architectural hole that allowed application use cases to depend on infrastructure.

**Target content profile (D026):** short-form vertical content only — Instagram Reels (<90s), TikTok videos, YouTube Shorts (<60s).

**Validated requirements:** R001 (TikTok + YouTube without cookies, Instagram with cookies), R002, R003, R004, R005, R006, R007, R008, R009, R010, R020 (MCP server), R021 (watchlist), R022 (scheduled refresh), R023 (related-video suggestion), R024 (LLM analyzers — 5 providers shipped), R025 (cookies UX complete with set/status/test/clear + CookieAuthError).

**Cookies feature:** users export `cookies.txt` from a logged-in browser once, then `vidscope cookies set <path>` installs it after format validation, `vidscope cookies test` verifies it authenticates against Instagram via a metadata-only probe (no real ingest required), and `vidscope add` surfaces a typed `CookieAuthError` with actionable remediation when the session expires. Full guide in `docs/cookies.md`.

**Next:** All 5 planned milestones are complete. Future work would be additive: semantic search (R026), expanded auth scenarios (Instagram stories, TikTok drafts), or a polish pass on the rich CLI output.

## Architecture / Key Patterns

**Language and tooling**
- Python 3.12+ managed via `uv` (fast, reproducible, lockfile-driven)
- src layout: `src/vidscope/` with submodules per concern
- CLI built with Typer (typed, self-documenting)
- Tests with pytest, lint with ruff, types with mypy (strict on our own code)

**Pipeline — five decoupled stages**
Each stage reads and writes via the data layer. Any stage can be invoked independently from the CLI, which makes manual mode, cron mode, and future daemon mode all trivial variations of the same plumbing.

1. **Ingest** — `yt-dlp` downloads the media file and extracts platform metadata into the DB.
2. **Transcribe** — `faster-whisper` produces a transcript (segments + full text) from the audio track.
3. **Frames** — `ffmpeg` extracts keyframes and sampled frames for later visual analysis.
4. **Analyze** — a pluggable provider produces a qualitative scoring (relevance, keywords, language, topics). Default is pure heuristics on the transcript (100% local, zero cost). Optional backends: NVIDIA Build (free tier), Groq (free tier), OpenRouter, OpenAI, Anthropic.
5. **Index** — FTS5 indexing of transcripts and derived text so `search` works without extra dependencies.

**Data layer**
- SQLite with FTS5 for full-text search in M001 (single file, zero setup, suffices for thousands of videos)
- Accessed through a thin repository layer so swapping to Postgres + pgvector later requires only one module change
- Schemas are versioned via migrations (no hand-edited DB files)

**Configuration and secrets**
- Runtime config in a single `~/.config/vidscope/config.toml` or project-local `.env`
- Analyzer provider selected by environment variable (`VIDSCOPE_ANALYZER`)
- API keys, when needed, never logged or printed

**Observability by default**
- Every pipeline stage writes a structured record of its run (phase, started_at, finished_at, result, error, retry_count) so a future agent can inspect state without re-running the pipeline
- CLI has a `status` subcommand that surfaces the last N runs and their outcome

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Pipeline ponctuel end-to-end — one command ingests a URL and produces a searchable, analyzed record locally
- [x] M002: MCP wrapper and related-video suggestions — agent can query, search, and propose related videos in chat
- [x] M003: Account monitoring and scheduled refresh — declare public accounts, refresh via manual command or cron, batch-process new videos
- [x] M004: Pluggable analyzer providers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic) — opt-in richer analysis beyond local heuristics
- [x] M005: Cookies UX polish — vidscope cookies set/status/test/clear, CookieAuthError remediation, browser walkthrough docs
