# S02: Related-video suggestion engine + suggest tool + CLI suggest — UAT

**Milestone:** M002
**Written:** 2026-04-07T17:28:26.183Z

## S02 UAT — Suggestion engine

### Manual checks
1. `python -m uv run vidscope suggest --help` → shows video_id arg + --limit option
2. After ingesting 2+ videos with overlapping content: `vidscope suggest <id>` → rich table of related videos
3. `python -m uv run pytest tests/unit/application/test_suggest_related.py -q` → 11 tests pass

### Quality gates
- [x] 370 unit tests + 3 architecture + 2 MCP subprocess
- [x] ruff, mypy strict (70 files), lint-imports (8 contracts) all clean
- [x] R023 validated across 3 layers (use case, CLI, MCP)
- [x] 6 MCP tools registered and callable via subprocess JSON-RPC

