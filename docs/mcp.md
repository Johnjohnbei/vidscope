# VidScope MCP server

An AI agent can drive your VidScope library in conversation via the
Model Context Protocol (MCP). VidScope ships an MCP server that
exposes every use case as a tool: ingest URLs, search transcripts,
inspect videos, list recent entries, check pipeline status, and
suggest related videos.

## What is MCP?

MCP is an open protocol for connecting AI applications to tools and
data sources. An MCP client (Claude Desktop, Cline, any stdio MCP
client) spawns a server as a subprocess and exchanges JSON-RPC
messages over stdin/stdout. Tools are functions the agent can call
with typed arguments; the server returns structured results.

See https://modelcontextprotocol.io for the protocol spec.

## Start the server

```bash
uv run vidscope mcp serve
```

The server reads JSON-RPC from stdin and writes responses to stdout.
All logs and errors go to stderr so they don't interfere with the
protocol. Press Ctrl-C to stop.

To verify the `mcp` SDK is installed:

```bash
uv run vidscope doctor
```

You should see a `mcp` row in green showing the installed version.

## Registered tools

The server exposes 6 tools. Every tool returns a JSON-serializable
dict; the MCP client handles serialization.

### `vidscope_ingest(url: str)`

Ingest a public video URL through the full 5-stage pipeline:
download → transcribe → extract frames → analyze → index.

**Returns:**

```json
{
  "status": "ok" | "failed" | "pending",
  "message": "ingested youtube/abc123 — Video Title",
  "url": "https://www.youtube.com/shorts/abc123",
  "run_id": 1,
  "video_id": 1,
  "platform": "youtube",
  "platform_id": "abc123",
  "title": "Video Title",
  "author": "Channel Name",
  "duration": 19.0,
  "media_type": "video" | "image" | "carousel"
}
```

### `vidscope_search(query: str, limit: int = 20)`

Full-text search across transcripts and analysis summaries using
SQLite FTS5 with BM25 ranking.

**Returns:**

```json
{
  "query": "cooking",
  "hits": [
    {
      "video_id": 1,
      "source": "transcript",
      "snippet": "...[cooking] pasta...",
      "rank": -1.23
    }
  ]
}
```

Lower rank = better match (BM25 convention).

### `vidscope_get_video(video_id: int)`

Return the full record for a video: metadata, transcript summary,
frame count, analysis.

**Returns:**

```json
{
  "found": true,
  "video": { "id": 1, "platform": "youtube", "title": "...", "media_type": "video", ... },
  "transcript": { "language": "en", "full_text": "...", "segment_count": 12 },
  "frame_count": 6,
  "analysis": {
    "provider": "heuristic",
    "keywords": ["python", "cooking"],
    "topics": ["python"],
    "score": 75.5,
    "summary": "..."
  }
}
```

When the video doesn't exist: `{"found": false, "video_id": <id>}`.

**Note:** For IMAGE and CAROUSEL media types, `transcript` will be `null` in the response — these types have no audio to transcribe.

### `vidscope_list_videos(limit: int = 20)`

List recently ingested videos newest-first.

**Returns:**

```json
{
  "total": 3,
  "videos": [
    { "id": 1, "platform": "youtube", "title": "...", "media_type": "video", ... },
    { "id": 2, "platform": "instagram", "title": "...", "media_type": "image", ... },
    { "id": 3, "platform": "instagram", "title": "...", "media_type": "carousel", ... }
  ]
}
```

### `vidscope_get_status(limit: int = 10)`

Return the last N pipeline runs across all videos.

**Returns:**

```json
{
  "total_runs": 15,
  "total_videos": 3,
  "runs": [
    {
      "id": 15,
      "phase": "index",
      "status": "ok",
      "video_id": 3,
      "started_at": "2026-04-07T12:00:00+00:00",
      "finished_at": "2026-04-07T12:00:01+00:00",
      "error": null,
      "retry_count": 0
    }
  ]
}
```

### `vidscope_suggest_related(video_id: int, limit: int = 5)`

Suggest related videos from the library by keyword overlap (Jaccard
similarity on analysis keywords).

**Returns:**

```json
{
  "source_video_id": 1,
  "source_found": true,
  "source_title": "Python cooking tips",
  "source_keywords": ["python", "cooking", "recipe", "tips"],
  "reason": "found 2 related videos",
  "suggestions": [
    {
      "video_id": 2,
      "title": "Python recipe book",
      "platform": "youtube",
      "score": 0.6,
      "matched_keywords": ["python", "recipe", "tips"]
    }
  ]
}
```

Empty `suggestions` with a `reason` explaining why when the source
has no analysis keywords, the source doesn't exist, or no
candidates share keywords.

## Claude Desktop configuration

Add this to your `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "vidscope": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/vidscope",
        "run",
        "vidscope",
        "mcp",
        "serve"
      ]
    }
  }
}
```

Replace `/absolute/path/to/vidscope` with the absolute path to your
cloned repository. Restart Claude Desktop after editing. The
vidscope server will appear in the tools menu.

## Cline configuration

Cline (VSCode extension) reads MCP server config from its settings.
Add:

```json
{
  "cline.mcpServers": {
    "vidscope": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/vidscope",
        "run",
        "vidscope",
        "mcp",
        "serve"
      ]
    }
  }
}
```

## Example agent session

Here's a realistic sequence an agent might execute:

```
User: "Find me videos about Python cooking and suggest similar content."

Agent calls:
  vidscope_search(query="python cooking", limit=5)
  → { "hits": [{"video_id": 1, "source": "transcript", ...}] }

Agent calls:
  vidscope_get_video(video_id=1)
  → { "video": {...}, "analysis": {"keywords": ["python", "cooking", ...]} }

Agent calls:
  vidscope_suggest_related(video_id=1, limit=5)
  → { "suggestions": [{"video_id": 2, "score": 0.6, ...}] }

Agent summarizes to the user with rich context.
```

## Troubleshooting

**The server doesn't start.** Run `uv run vidscope doctor`. The
`mcp` row should show green with the installed SDK version. If it
says `fail`, run `uv sync` to reinstall dependencies.

**The MCP client can't connect.** The server communicates via
stdin/stdout — any `print()` or log line on stdout will corrupt the
JSON-RPC protocol. VidScope tools never print to stdout directly;
all log output goes to stderr. If you see protocol errors, check
that nothing in your Python path is patching sys.stdout.

**Tool calls time out.** The `vidscope_ingest` tool can take
30+ seconds on first run (model download for faster-whisper) and
5-10 seconds on subsequent runs. Increase your MCP client's
timeout if it's set below 60 seconds.

**Tools return empty results.** Check `vidscope_get_status` to see
if any pipeline runs have been recorded. Run `vidscope add <url>`
via the CLI to populate the library manually, then retry the MCP
tools.

**Instagram tools fail.** Instagram Reels require cookies. See
`docs/cookies.md` for setup. Once `VIDSCOPE_COOKIES_FILE` is
configured in the shell where `vidscope mcp serve` runs, Instagram
ingestion works transparently.

## Security notes

The MCP server runs as a local subprocess with full access to your
VidScope library and anything the user running the MCP client can
do. It does not expose a network port. If you share your MCP client
config, you're sharing access to your library — treat it
accordingly.
