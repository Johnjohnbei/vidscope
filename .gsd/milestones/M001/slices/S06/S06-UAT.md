# S06: End-to-end wiring, FTS5 index, search and status commands — UAT

**Milestone:** M001
**Written:** 2026-04-07T16:11:25.910Z

## S06 UAT — End-to-end wiring + FTS5 search

### Manual checks
1. `bash scripts/verify-m001.sh --skip-integration` → 7/7 green
2. With ffmpeg: `bash scripts/verify-m001.sh` → 9/9 green incl real CLI demo
3. `vidscope add <url>` → ingest OK + 5 stages
4. `vidscope status` → 5 pipeline_runs per video
5. `vidscope list` → table of recent videos
6. `vidscope show <id>` → full record (metadata + transcript info + frames + analysis)
7. `vidscope search "<keyword>"` → ranked FTS5 hits with snippets

### Quality gates
- [x] 343 unit + 3 architecture + 3 integration tests
- [x] ruff, mypy strict, lint-imports clean
- [x] R006, R007, R008 validated end-to-end
- [x] Pipeline = 5 stages
- [x] Real YouTube ingest produces working search hits

