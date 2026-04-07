# VidScope

> Local video intelligence for Instagram, TikTok, and YouTube. Download, transcribe, analyze, and search public short-form videos from the command line — no cloud, no paid API by default.

VidScope is a personal video-intelligence tool. Given a URL to a public video on Instagram, TikTok, or YouTube, it downloads the media locally, transcribes the audio with faster-whisper, extracts representative frames with ffmpeg, runs a structured analysis on the transcript, and indexes everything into a searchable SQLite + FTS5 database.

It exposes both a **CLI** (`vidscope add <url>`, `vidscope search <query>`) and an **MCP server** so an AI agent can drive the library in conversation.

## Status

✅ **All 5 planned milestones complete.** 618 unit tests passing, 84 source files mypy strict-clean, 9 import-linter contracts enforcing the hexagonal architecture, ruff clean.

## What you get

```bash
# Ingest a video — all 5 stages in one command
vidscope add https://www.youtube.com/shorts/<id>

# Search across transcripts and analyses
vidscope search "machine learning"

# Inspect a video's full record
vidscope show <video-id>

# Suggest related videos in the library by keyword overlap
vidscope suggest <video-id>

# Track public accounts and refresh on demand
vidscope watch add https://www.youtube.com/@SomeChannel
vidscope watch refresh

# Manage cookies for gated content (Instagram primarily)
vidscope cookies set ~/Downloads/cookies.txt
vidscope cookies test
vidscope add https://www.instagram.com/reel/<id>/

# Opt into LLM analyzers (Groq, NVIDIA, OpenRouter, OpenAI, Anthropic)
export VIDSCOPE_GROQ_API_KEY=gsk_...
export VIDSCOPE_ANALYZER=groq
vidscope add <url>

# Expose everything to an AI agent via the Model Context Protocol
vidscope mcp serve
```

## The pipeline

`vidscope add <url>` runs five decoupled stages, each transactionally coupled to a `pipeline_runs` row:

1. **Ingest** — yt-dlp downloads the media file and extracts metadata
2. **Transcribe** — faster-whisper produces segmented + full text on CPU (int8 quantization)
3. **Frames** — ffmpeg extracts ~10 representative frames per video
4. **Analyze** — pluggable provider produces keywords, topics, score, summary
5. **Index** — FTS5 indexes transcripts and analyses for full-text search

Re-running `vidscope add` on a video that previously failed resumes from the last incomplete stage. Every stage commits transactionally with its `pipeline_runs` row.

## Architecture

VidScope uses a **strict hexagonal architecture** enforced by [import-linter](https://import-linter.readthedocs.io/) at 9 contracts. The layers, innermost first:

- `vidscope.domain` — entities, value objects, typed errors. **Zero project imports, zero third-party runtime deps** (stdlib + typing only).
- `vidscope.ports` — Protocol interfaces. Imports only `domain`.
- `vidscope.adapters.*` — concrete implementations (sqlite, ytdlp, whisper, ffmpeg, heuristic, fs, llm). Each adapter is isolated; **adapters never import each other**.
- `vidscope.pipeline` — stages and PipelineRunner. Imports `domain` + `ports`. **Never imports a concrete adapter.**
- `vidscope.application` — use cases. Imports `domain` + `ports` + `pipeline`. Never touches I/O directly.
- `vidscope.cli` and `vidscope.mcp` — thin dispatch to use cases.
- `vidscope.infrastructure` — composition root. Builds the config, wires adapters to ports, instantiates use cases.

The 9 contracts are enforced via `python -m uv run lint-imports` and run on every quality gate.

## Stack

- **Language**: Python 3.12+
- **Package manager**: uv
- **CLI**: Typer
- **DB**: SQLite + FTS5 (via SQLAlchemy)
- **Download**: yt-dlp
- **Transcription**: faster-whisper
- **Frames**: ffmpeg
- **HTTP** (LLM adapters): httpx
- **MCP**: official Python SDK

## Supported platforms

- **YouTube** Shorts (no auth required)
- **TikTok** videos (no auth required)
- **Instagram** Reels (cookies required since 2026-04 — see [docs/cookies.md](docs/cookies.md))
- **YouTube** age-gated (cookies optional)

Short-form vertical content is the validated target profile (Reels < 90s, Shorts < 60s, TikTok videos).

## Pluggable analyzers

VidScope ships with two zero-cost defaults and five LLM providers. Switch via `VIDSCOPE_ANALYZER`:

| Name | Cost | Env var | Default model |
|---|---|---|---|
| `heuristic` *(default)* | free | _(none)_ | _stdlib_ |
| `groq` | free tier | `VIDSCOPE_GROQ_API_KEY` | `llama-3.1-8b-instant` |
| `nvidia` | free tier | `VIDSCOPE_NVIDIA_API_KEY` | `meta/llama-3.1-8b-instruct` |
| `openrouter` | free tier | `VIDSCOPE_OPENROUTER_API_KEY` | `meta-llama/llama-3.3-70b-instruct:free` |
| `openai` | starter credits | `VIDSCOPE_OPENAI_API_KEY` | `gpt-4o-mini` |
| `anthropic` | starter credits | `VIDSCOPE_ANTHROPIC_API_KEY` | `claude-haiku-4-5` |

Each provider lives in `src/vidscope/adapters/llm/<name>.py` behind the `llm-never-imports-other-adapters` import-linter contract — adding a new one is one file + one factory + one test file. Full guide in [docs/analyzers.md](docs/analyzers.md).

## Documentation

| Doc | What |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Install, first ingest, basic commands |
| [docs/cookies.md](docs/cookies.md) | 5-minute cookies setup, browser walkthroughs, troubleshooting |
| [docs/watchlist.md](docs/watchlist.md) | Account monitoring, scheduled refresh, OS scheduler integration |
| [docs/analyzers.md](docs/analyzers.md) | LLM provider reference, cost/quota table, contributor guide |
| [docs/mcp.md](docs/mcp.md) | MCP server, exposed tools, agent integration |

## Quality gates

Every change must pass four gates:

```bash
python -m uv run ruff check .                         # lint
python -m uv run mypy src                             # type check (strict mode)
python -m uv run pytest -q                            # 618 unit tests
python -m uv run lint-imports                         # 9 architecture contracts
```

Plus the per-milestone verification scripts:

```bash
bash scripts/verify-m001.sh        # 9 steps — pipeline end-to-end
bash scripts/verify-m002.sh        # 10 steps — MCP server + suggest_related
bash scripts/verify-m003.sh        # 9 steps — watchlist + refresh
bash scripts/verify-m004.sh        # 9 steps — 5 LLM analyzers via stub HTTP
bash scripts/verify-m005.sh        # 10 steps — cookies UX with stub yt_dlp
```

All five exit 0. The verify scripts use stubbed networks for reproducibility — manual live validation against real providers is documented in each milestone's UAT.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Johnjohnbei/vidscope.git
cd vidscope
uv sync
uv run vidscope doctor   # check ffmpeg / yt-dlp / mcp / cookies / analyzer
```

You also need `ffmpeg` on PATH. On Windows: `winget install Gyan.FFmpeg`. On macOS: `brew install ffmpeg`. On Linux: `sudo apt install ffmpeg` or your distro equivalent.

## Project layout

```
src/vidscope/
  domain/           # entities, value objects, typed errors
  ports/            # Protocol interfaces
  adapters/         # concrete implementations
    sqlite/         # DB layer + FTS5 search
    ytdlp/          # downloader
    whisper/        # transcriber
    ffmpeg/         # frame extractor
    heuristic/      # zero-cost analyzer
    llm/            # 5 LLM provider analyzers (M004)
    fs/             # local media storage
  pipeline/         # 5-stage runner
  application/      # use cases (one per CLI / MCP entry point)
  cli/              # Typer CLI + sub-applications (mcp, watch, cookies)
  mcp/              # MCP server exposing 6 tools
  infrastructure/   # composition root + config + analyzer registry
docs/               # user-facing documentation
scripts/            # verify-mNNN.sh + utility scripts
tests/
  unit/             # 618 unit tests, sandboxed via tmp_path
  integration/      # 5 integration tests (live ingest + MCP subprocess)
  architecture/     # import-linter assertion test
.gsd/               # GSD project artifacts (decisions, requirements, milestones)
```

## Anti-features (out of scope)

VidScope deliberately doesn't:

- **Republish or redistribute** ingested media (R030) — downloads stay local for personal analysis
- **Edit or re-encode video** beyond ffmpeg frame extraction (R031) — VidScope is a reader, not an editor
- **Multi-tenant or web UI** (R032) — single-user local tool, MCP is local stdio only

## Privacy

- **Heuristic analyzer**: nothing leaves your machine
- **LLM analyzers**: each transcript is sent to the chosen provider's servers — see [docs/analyzers.md](docs/analyzers.md) privacy section
- **Cookies**: treated as credentials, never logged, gitignored (`cookies.txt`, `*.cookies`)
- **No telemetry**: VidScope makes zero outbound calls except the explicit ones you trigger

## License

MIT — see [LICENSE](LICENSE).
