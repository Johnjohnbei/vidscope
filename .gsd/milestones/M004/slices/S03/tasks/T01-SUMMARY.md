---
id: T01
parent: S03
milestone: M004
key_files:
  - src/vidscope/infrastructure/startup.py
  - tests/unit/infrastructure/test_startup.py
  - docs/analyzers.md
  - scripts/verify-m004.sh
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - check_analyzer() lives in startup.py alongside the other system checks — same shape as check_ffmpeg/check_ytdlp/check_mcp_sdk/check_cookies
  - verify-m004.sh demos all 5 providers in ONE Python invocation — keeps the script fast
  - docs/analyzers.md documents the 'adding a new provider' workflow — future contributors don't need to grep the codebase to understand the pattern
  - KNOWLEDGE.md captures the LLM adapter pattern as a reusable rule — next agent reads it at unit start
duration: 
verification_result: passed
completed_at: 2026-04-07T18:35:49.379Z
blocker_discovered: false
---

# T01: Wired analyzer status into vidscope doctor, wrote docs/analyzers.md, shipped verify-m004.sh (9 steps green), validated R024, updated PROJECT.md + KNOWLEDGE.md.

**Wired analyzer status into vidscope doctor, wrote docs/analyzers.md, shipped verify-m004.sh (9 steps green), validated R024, updated PROJECT.md + KNOWLEDGE.md.**

## What Happened

**`vidscope doctor` analyzer row.** Added `check_analyzer()` to `vidscope.infrastructure.startup` and registered it in `run_all_checks()`. The check has 5 states:

1. **Default heuristic** → `ok=True`, `"heuristic (default, zero cost)"`
2. **Stub** → `ok=True`, `"stub (test placeholder)"`
3. **LLM provider configured + key present** → `ok=True`, `"<provider> (LLM key present)"`
4. **LLM provider configured + key missing** → `ok=False`, names the missing env var
5. **Unknown analyzer name** → `ok=False`, lists the known names

The check works by reading `config.analyzer_name`, then for LLM providers calling `build_analyzer(name)` and catching `ConfigError` (which the registry factory raises with the actionable env var + signup URL). 6 new unit tests in `tests/unit/infrastructure/test_startup.py` covering all 5 states + the 5-row `run_all_checks()` shape.

**`docs/analyzers.md`** — new ~11KB user guide with:
- Quick reference table for all 7 names (env var, default model, signup URL, free/paid)
- How analyzers fit into the pipeline (one stage, swappable, no migration)
- Per-provider section for heuristic + 5 LLM providers with usage example, free tier limits, model override env var, and provider-specific notes (Groq's LPU speed, OpenRouter's `:free` suffix, Anthropic's native `/v1/messages` choice with the production-readiness rationale)
- "Adding a new provider" section documenting the one-file pattern + the import-linter contract that enforces it
- Cost/quota comparison table
- Privacy notes (heuristic stays local, LLM providers send transcripts to vendor servers, free-tier providers may use prompts for training)

**`verify-m004.sh`** — new ~10KB script with 9 steps:
1. `uv sync`
2. `ruff check src tests`
3. `mypy strict on src`
4. `lint-imports` (9 contracts)
5. `pytest -q` (full suite)
6. Registry exposes 7 expected names
7. Each LLM provider raises `ConfigError` with the correct env var name when its key is missing
8. Each LLM provider produces a valid `Analysis` via `httpx.MockTransport` (5 stub HTTP demos in one Python invocation)
9. `vidscope doctor` output contains an `analyzer` row

Step 8 is the key M004 demo: it constructs all 5 LLM analyzers with stubbed HTTP clients (one OpenAI-compatible response handler shared across Groq/NVIDIA/OpenRouter/OpenAI, one Anthropic-shaped response handler for the native /v1/messages adapter), runs `analyzer.analyze(transcript)`, and asserts each result has the right `provider` field, score, and keywords. Zero real network. Reproducible in CI. The script supports `--skip-integration` for the MCP subprocess tests.

Verified locally: `bash scripts/verify-m004.sh --skip-integration` → 9 steps, 0 failed, exits 0.

**R024 validated** via `gsd_requirement_update`. Validation note records the full evidence: 5 providers shipped, shared `_base.py` toolkit, 9th import-linter contract, 120 new LLM unit tests, doctor integration, docs, verify script.

**PROJECT.md** updated to reflect M004 complete: M001+M002+M003+M004 done, M005 remains. Test count 432 → 558. Source file count 74 → 81. Contract count 8 → 9. Added the new bullet for `VIDSCOPE_ANALYZER`. Added R024 to the validated list. Updated milestone checkboxes.

**KNOWLEDGE.md** updated with two new sections:
1. **LLM analyzer adapter pattern (M004)** — 7-step recipe for adding a new provider, distinguishing OpenAI-compatible (use `run_openai_compatible`) from non-compatible (reuse `_base` helpers individually). Documents the constructor validation rule, the injectable client lifecycle pattern, the registry factory shape, the test conventions, and the structural contract enforcement.
2. **httpx + mcp are forbidden in domain/ports (M004)** — documents the new entries in the `domain-is-pure` and `ports-are-pure` import-linter contracts so future agents know the innermost layers stay 100% stdlib.

**Final quality gates after T03**:
- ✅ pytest: **558 passed** in 14.68s (was 552, +6 startup tests)
- ✅ mypy strict: **81 source files** OK (unchanged from S02)
- ✅ ruff: clean
- ✅ lint-imports: **9 contracts kept**, 0 broken
- ✅ verify-m004.sh: **9 steps, 0 failures**, exits 0

Note: `vidscope doctor` reports `ffmpeg | fail | not found on PATH` in this shell, but that's a pre-existing condition unrelated to M004 — winget installed ffmpeg requires a fresh shell session for the PATH to refresh. The M004-specific row (`analyzer | ok | heuristic (default, zero cost)`) is correctly displayed and verified by the script.

## Verification

All 4 quality gates clean in parallel + verify-m004.sh full run with --skip-integration: 9 steps green. pytest 558 passed in 14.68s, mypy 81 source files OK, ruff clean, lint-imports 9 contracts kept.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ 558 passed | 14680ms |
| 2 | `python -m uv run mypy src` | 0 | ✅ 81 source files OK | 2100ms |
| 3 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept | 2100ms |
| 4 | `python -m uv run ruff check .` | 0 | ✅ all checks passed | 800ms |
| 5 | `bash scripts/verify-m004.sh --skip-integration` | 0 | ✅ 9/9 steps green | 30000ms |

## Deviations

None.

## Known Issues

vidscope doctor reports ffmpeg as missing in this dev shell because winget-installed binaries don't refresh PATH until a new session. Pre-existing, unrelated to M004. Will be cleared next time the shell restarts.

## Files Created/Modified

- `src/vidscope/infrastructure/startup.py`
- `tests/unit/infrastructure/test_startup.py`
- `docs/analyzers.md`
- `scripts/verify-m004.sh`
- `.gsd/PROJECT.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/REQUIREMENTS.md`
