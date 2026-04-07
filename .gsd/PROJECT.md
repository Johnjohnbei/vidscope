# VidScope

## What This Is

VidScope is a personal video-intelligence tool. Given a URL to a public video on Instagram, TikTok, or YouTube, it downloads the media locally, transcribes the audio, extracts representative frames, produces a structured analysis of the content, and stores everything in a searchable local database. It exposes both a CLI (`vidscope add <url>`, `vidscope search <query>`) and — in later milestones — an MCP server so an AI agent can query and enrich the library during conversation.

The current focus is M001: the single-URL end-to-end pipeline. Account-monitoring, cron-based refresh, and related-video suggestion arrive in later milestones.

## Core Value

A single command turns a video URL into a searchable, analyzable record on the local machine — no paid API, no cloud dependency, no manual copy-pasting. If every other feature is cut, this one must work: `vidscope add <url>` → transcript + frames + analysis + searchable DB entry.

## Current State

Project bootstrapped. Git repo initialized and pushed to `github.com/Johnjohnbei/vidscope` (private). Python packaging skeleton in place (`pyproject.toml`, src layout planned). No runtime code yet — M001/S01 will land the socle, build toolchain, and CLI skeleton.

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

- [ ] M001: Pipeline ponctuel end-to-end — one command ingests a URL and produces a searchable, analyzed record locally
- [ ] M002: MCP wrapper and related-video suggestions — agent can query, search, and propose related videos in chat
- [ ] M003: Account monitoring and scheduled refresh — declare public accounts, refresh via manual command or cron, batch-process new videos
- [ ] M004: Pluggable analyzer providers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic) — opt-in richer analysis beyond local heuristics
- [ ] M005: Cookies/auth for private or story content — support gated content via exported browser cookies
