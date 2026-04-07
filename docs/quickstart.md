# VidScope quickstart

A 5-minute walkthrough that takes you from zero to a searchable
local video library.

## Prerequisites

- **Python 3.12+** installed
- **uv** (the Python package manager) — `pip install uv` if you don't have it
- **ffmpeg** on your PATH (required for frame extraction):
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg` or your distro's equivalent

That's it. No paid API keys required by default — VidScope ships
with a zero-cost heuristic analyzer that runs entirely locally.

## Install

Clone the repo and sync dependencies:

```bash
git clone https://github.com/Johnjohnbei/vidscope.git
cd vidscope
uv sync
```

## Verify your environment

```bash
uv run vidscope doctor
```

You should see all five checks green:

```
                   vidscope doctor                    
+----------------------------------------------------+
| check    | status | detail                         |
|----------+--------+--------------------------------|
| ffmpeg   | ok     | ffmpeg version 8.1             |
| yt-dlp   | ok     | 2026.03.17                     |
| mcp      | ok     | 1.27.0                         |
| cookies  | ok     | not configured (optional)      |
| analyzer | ok     | heuristic (default, zero cost) |
+----------------------------------------------------+
```

If `ffmpeg` shows `fail`, install it and re-run doctor. The
`cookies` row showing **not configured (optional)** is fine — cookies
are only needed for Instagram (see [docs/cookies.md](cookies.md)).

## Ingest your first video

Pick any public YouTube Short or TikTok video URL. Run:

```bash
uv run vidscope add "https://www.youtube.com/shorts/<id>"
```

You'll see a rich panel showing the ingest result:

```
+----------- ingest OK -----------+
| video id: 1                     |
| platform: youtube/<id>          |
| title:    <video title>         |
| author:   <channel>             |
| duration: 19.0s                 |
| url:      https://...           |
| run id:   1                     |
+---------------------------------+
```

The first run downloads the faster-whisper `base` transcription
model (~150MB) into your data directory. Subsequent runs reuse the
cached model.

## See what just happened

```bash
uv run vidscope status
```

Shows the last 5 pipeline runs (one per stage):

- `ingest` — downloaded the media via yt-dlp
- `transcribe` — transcribed the audio via faster-whisper
- `frames` — extracted frames via ffmpeg
- `analyze` — produced an analysis (language, keywords, summary)
- `index` — wrote the transcript and analysis into the FTS5 search index

Each row shows the status, the elapsed time, and any error message.
Re-running `vidscope add` on a partially-failed video resumes from
the last incomplete stage.

## List your library

```bash
uv run vidscope list
```

A table of every ingested video with id, platform, title, duration.

## Inspect one video

```bash
uv run vidscope show 1
```

Full record: metadata, transcript stats, frames count, analysis.

## Search

```bash
uv run vidscope search "<keyword>"
```

Runs a SQLite FTS5 query against transcripts and analysis summaries,
returns ranked hits with highlighted snippets.

## Find related videos

Once you have a few videos in the library, ask for related content
by keyword overlap:

```bash
uv run vidscope suggest 1
```

Returns up to 5 videos that share keywords with video 1, scored by
Jaccard similarity. Useful for discovering thematic clusters.

## Track public accounts

Declare an account you want to follow, then refresh on demand to
ingest any new videos automatically:

```bash
uv run vidscope watch add https://www.youtube.com/@SomeChannel
uv run vidscope watch refresh
```

The refresh is idempotent — running it twice in a row ingests new
videos on the first run and zero on the second. Schedule it via
cron / launchd / Task Scheduler for hands-free monitoring. Full
guide in [docs/watchlist.md](watchlist.md).

## Where is my data?

VidScope writes everything under your platform's user data dir:

- **Windows**: `%LOCALAPPDATA%\vidscope\`
- **macOS**: `~/Library/Application Support/vidscope/`
- **Linux**: `~/.local/share/vidscope/`

Inside that dir:

- `vidscope.db` — SQLite database with all rows
- `videos/<platform>/<id>/media.<ext>` — downloaded media files
- `videos/<platform>/<id>/frames/<NNNN>.jpg` — extracted frames
- `models/` — cached faster-whisper model weights
- `cookies.txt` — optional cookies file (managed via `vidscope cookies set`)

To use a different location, set `VIDSCOPE_DATA_DIR` to an absolute
path.

## Adding Instagram

Instagram public Reels currently require authentication. The
3-command setup:

```bash
# 1. Export cookies.txt from your browser (see docs/cookies.md)
uv run vidscope cookies set ~/Downloads/cookies.txt

# 2. Verify the cookies authenticate
uv run vidscope cookies test

# 3. Ingest a Reel
uv run vidscope add "https://www.instagram.com/reel/<id>/"
```

If `vidscope cookies test` reports `auth_required`, your browser
session has likely expired — re-export and re-run `vidscope cookies
set`. Full walkthrough in [docs/cookies.md](cookies.md).

## Choosing a different whisper model

```bash
VIDSCOPE_WHISPER_MODEL=small uv run vidscope add "<url>"
```

Supported: `tiny`, `tiny.en`, `base` (default), `base.en`, `small`,
`small.en`, `medium`, `medium.en`, `large-v3`, `distil-large-v3`.
Bigger = slower + more accurate.

## Opting into LLM analyzers

The default heuristic analyzer is pure-Python and zero-cost. To
upgrade to an LLM-backed analysis, set `VIDSCOPE_ANALYZER` to one of
the 5 supported providers and provide the matching API key:

```bash
# Example: Groq (free tier, no credit card required)
export VIDSCOPE_GROQ_API_KEY=gsk_...
export VIDSCOPE_ANALYZER=groq
uv run vidscope add "<url>"
```

Supported providers: `groq`, `nvidia`, `openrouter`, `openai`,
`anthropic`. Full reference with cost/quota table in
[docs/analyzers.md](analyzers.md).

## Driving VidScope from an AI agent

VidScope ships an MCP server that exposes every use case as a tool
an AI agent can call. Start it with:

```bash
uv run vidscope mcp serve
```

Then point your MCP client (Claude Desktop, Cline, any stdio MCP
client) at it. Full setup including Claude Desktop config in
[docs/mcp.md](mcp.md).

## Where to go next

| You want to... | Read |
|---|---|
| Set up Instagram cookies properly | [docs/cookies.md](cookies.md) |
| Track multiple accounts on a schedule | [docs/watchlist.md](watchlist.md) |
| Use a paid LLM analyzer | [docs/analyzers.md](analyzers.md) |
| Drive VidScope from Claude or another agent | [docs/mcp.md](mcp.md) |
| Understand the architecture | [README.md](../README.md) |
