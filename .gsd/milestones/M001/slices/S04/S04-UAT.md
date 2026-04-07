# S04: Frame extraction brick (ffmpeg) — UAT

**Milestone:** M001
**Written:** 2026-04-07T15:52:20.401Z

## S04 UAT — Frame extraction

### Manual checks
1. `bash scripts/verify-s04.sh --skip-integration` → 7/7 green
2. With ffmpeg installed: `bash scripts/verify-s04.sh` → 8 steps green incl frames
3. `vidscope add <youtube-shorts-url>` → ingest OK + transcript + N frames in DB
4. `vidscope status` → 3 pipeline_runs per video (ingest + transcribe + frames)
5. Without ffmpeg: same `vidscope add` succeeds for ingest + transcribe but frames stage shows FAILED with install instructions in error column

### Quality gates
- [x] 300 unit + 3 architecture + 3 integration tests
- [x] ruff, mypy strict, lint-imports all clean
- [x] R003 validated end-to-end
- [x] ffmpeg invoked from exactly one file
- [x] R009 cross-platform install preserved (container builds without ffmpeg)

