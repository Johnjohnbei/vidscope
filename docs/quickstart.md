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

That's it. No API keys, no cloud accounts, no server setup.

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

You should see all three checks green:

```
              vidscope doctor               
+------------------------------------------+
| check   | status | detail                |
|---------+--------+-----------------------|
| ffmpeg  | ok     | ffmpeg version 8.1    |
| yt-dlp  | ok     | 2026.03.17            |
| cookies | ok     | not configured (...)  |
+------------------------------------------+
```

If `ffmpeg` shows `fail`, install it and re-run doctor.

The `cookies` row showing **not configured (optional)** is fine —
cookies are only needed for Instagram (see `docs/cookies.md`).

## Ingest your first video

Pick any public YouTube Short or TikTok video URL. For TikTok, the
official `@tiktok` account works without auth. Run:

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
- `analyze` — produced a heuristic analysis (language, keywords, summary)
- `index` — wrote the transcript and analysis into the FTS5 search index

Each row shows the status, the elapsed time, and any error message.

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
- `cookies.txt` — optional cookies file (see `docs/cookies.md`)

To use a different location, set `VIDSCOPE_DATA_DIR` to an absolute
path.

## Adding Instagram

Instagram public Reels currently require authentication. Follow
`docs/cookies.md` to export your browser cookies once, then:

```bash
export VIDSCOPE_COOKIES_FILE=~/cookies.txt
uv run vidscope add "https://www.instagram.com/reel/<id>/"
```

## Choosing a different whisper model

```bash
VIDSCOPE_WHISPER_MODEL=small uv run vidscope add "<url>"
```

Supported: `tiny`, `tiny.en`, `base` (default), `base.en`, `small`,
`small.en`, `medium`, `medium.en`, `large-v3`, `distil-large-v3`.
Bigger = slower + more accurate.

## What's next

- The MCP server in M002 lets an AI agent drive your library in
  conversation.
- Account monitoring in M003 ingests new videos from watched
  accounts on a schedule.
- LLM-backed analyzers in M004 (NVIDIA, Groq, OpenAI, Anthropic)
  give richer analyses than the default heuristic.
