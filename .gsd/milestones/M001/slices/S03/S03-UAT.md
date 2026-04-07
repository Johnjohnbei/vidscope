# S03: Transcription brick (faster-whisper) — UAT

**Milestone:** M001
**Written:** 2026-04-07T15:41:14.598Z

## S03 UAT — Transcription brick

### Manual checks
1. `bash scripts/verify-s03.sh --skip-integration` → 7/7 green
2. `bash scripts/verify-s03.sh` (full, downloads ~150MB whisper model first run) → 9 steps green incl. live transcription
3. `python -m uv run vidscope add "https://www.youtube.com/shorts/<id>"` → ingest OK panel, then real transcript in DB
4. `python -m uv run vidscope status` → shows 2 pipeline_runs per video (ingest + transcribe)

### Quality gates
- [x] 284 unit + 3 architecture + 3 integration tests
- [x] ruff, mypy strict, lint-imports all clean
- [x] R002 validated for English content
- [x] R007 (multi-stage pipeline) advanced

