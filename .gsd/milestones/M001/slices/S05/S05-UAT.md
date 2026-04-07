# S05: Heuristic analyzer with pluggable provider interface — UAT

**Milestone:** M001
**Written:** 2026-04-07T16:01:57.067Z

## S05 UAT — Heuristic analyzer

### Manual checks
1. `bash scripts/verify-s05.sh --skip-integration` → 7/7 green
2. With ffmpeg: `bash scripts/verify-s05.sh` → all green incl 4-stage live tests
3. `vidscope add <youtube-shorts-url>` → ingest + transcript + frames + analysis in DB
4. `vidscope status` → 4 pipeline_runs per video

### Quality gates
- [x] 331 unit + 3 architecture + 3 integration
- [x] ruff, mypy strict, lint-imports clean
- [x] R004 validated end-to-end
- [x] R010 validated (2 registered providers, swappable via env var)

