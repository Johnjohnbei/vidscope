# S01: MCP server foundation with 5 read-only tools — UAT

**Milestone:** M002
**Written:** 2026-04-07T17:20:06.634Z

## S01 UAT — MCP server foundation

### Manual checks
1. `python -m uv run vidscope doctor` → 4 rows green (ffmpeg + yt-dlp + mcp + cookies)
2. `python -m uv run vidscope mcp --help` → shows `serve` subcommand
3. `python -m uv run vidscope mcp serve` starts the server on stdio (Ctrl-C to stop)
4. `python -m uv run pytest tests/unit/mcp -q` → 14 unit tests pass
5. `python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v` → 2 subprocess tests pass

### Quality gates
- [x] 353 unit tests + 3 architecture + 2 MCP subprocess integration tests
- [x] ruff, mypy strict (68 files), lint-imports (8 contracts) all clean
- [x] MCP server responds to JSON-RPC over stdio
- [x] 5 tools registered: ingest, search, get_video, list_videos, get_status
- [x] Tool handlers tested directly (unit) + via subprocess (integration)
- [x] mcp.server never imports adapters directly (forbidden contract enforced)

