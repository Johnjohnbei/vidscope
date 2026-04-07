---
id: S03
parent: M004
milestone: M004
provides:
  - vidscope doctor analyzer row
  - docs/analyzers.md user reference + contributor guide
  - verify-m004.sh as the M004 closure signal
  - KNOWLEDGE.md M004 entries documenting the adapter pattern for future agents
requires:
  - slice: S01
    provides: shared _base.py + analyzer_registry pattern + llm-never-imports-other-adapters import-linter contract
  - slice: S02
    provides: 4 remaining provider adapters + run_openai_compatible refactor
affects:
  - M005 will use the same verify-mNNN.sh + docs/<topic>.md + KNOWLEDGE.md update pattern
key_files:
  - src/vidscope/infrastructure/startup.py
  - tests/unit/infrastructure/test_startup.py
  - docs/analyzers.md
  - scripts/verify-m004.sh
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - check_analyzer() lives in startup.py alongside the existing 4 checks — same dataclass return shape, same remediation pattern
  - verify-m004.sh demos all 5 providers in ONE Python invocation with shared transcript fixture — fast + reproducible
  - docs/analyzers.md includes a complete 'adding a new provider' walkthrough — the file IS the contributor guide for new LLM integrations
  - KNOWLEDGE.md captures the LLM adapter pattern as a non-negotiable rule — next agent reads it at unit start
patterns_established:
  - System check shape: read config -> attempt construction -> catch ConfigError -> return CheckResult with actionable remediation
  - Per-milestone verify-mNNN.sh script structure: quality gates + name registry smoke + missing-key validation + stub HTTP demos + doctor row check
  - Append to KNOWLEDGE.md when establishing a reusable adapter pattern, not when shipping a one-off feature
observability_surfaces:
  - vidscope doctor: new 'analyzer' row reporting active provider + key status with 5 distinct states
  - ConfigError messages from registry factories include the exact env var name + signup URL
  - Each LLM provider's analyze() method logs retry attempts via _base.call_with_retry
drill_down_paths:
  - .gsd/milestones/M004/slices/S03/tasks/T01-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T18:37:00.339Z
blocker_discovered: false
---

# S03: Doctor integration, docs, verify-m004.sh, milestone closure

**Closed M004: vidscope doctor analyzer row, docs/analyzers.md, verify-m004.sh (9/9 green), R024 validated, PROJECT.md + KNOWLEDGE.md updated.**

## What Happened

S03 was the operational closure slice for M004. One task delivered everything: doctor wiring, docs, verify script, knowledge entries, requirement validation, milestone closeout artifacts.

**The doctor integration** added a 5th system check (`check_analyzer`) following the exact shape of the existing `check_ffmpeg`/`check_ytdlp`/`check_mcp_sdk`/`check_cookies` checks. It reads `config.analyzer_name`, then for LLM providers calls `build_analyzer(name)` and catches `ConfigError` to detect missing keys. The result row in `vidscope doctor` shows the active provider name + key status. 6 new unit tests cover the 5 possible states (heuristic, stub, unknown, LLM-with-key, LLM-without-key, anthropic-with-key).

**`docs/analyzers.md`** is the new user-facing reference. ~11KB, ~250 lines. Quick-reference table for all 7 names, per-provider sections with usage examples + free tier limits + signup URLs, "adding a new provider" how-to that documents the structural pattern enforced by the import-linter contract, cost/quota comparison table, privacy notes (heuristic stays local, LLM providers send transcripts to vendor servers).

**`verify-m004.sh`** runs 9 steps and exits 0:
1. `uv sync`
2. `ruff check`
3. `mypy strict`
4. `lint-imports` (9 contracts)
5. `pytest -q` (558 passed)
6. Registry exposes 7 expected names
7. Each LLM provider raises `ConfigError` with the correct env var when its key is missing
8. Each LLM provider produces a valid `Analysis` via `httpx.MockTransport`
9. `vidscope doctor` output contains the analyzer row

The script supports `--skip-integration` for skipping the MCP subprocess tests in CI. All 5 LLM providers are exercised via stubbed HTTP in step 8 — zero real network calls, fully reproducible.

**R024 validated**: full evidence recorded in the requirement validation field — 5 providers shipped, shared `_base.py` toolkit, 9th import-linter contract, 120 new LLM unit tests, doctor integration, docs, verify script.

**PROJECT.md updated**: M004 marked complete in the "Current State" + "Milestone Sequence" sections, R024 added to validated list, test count 432 → 558, source file count 74 → 81, contract count 8 → 9. Added the new bullet for `VIDSCOPE_ANALYZER` and the doctor's analyzer row mention.

**KNOWLEDGE.md updated** with two new sections that future agents will read at the start of any unit:
1. **LLM analyzer adapter pattern** — 7-step recipe for adding a new provider with the OpenAI-compatible vs non-compatible distinction
2. **httpx + mcp forbidden in domain/ports** — documents the M004 additions to the `domain-is-pure` and `ports-are-pure` import-linter contracts

**Pre-existing condition surfaced** (not a M004 issue): `vidscope doctor` reports ffmpeg as missing in the dev shell because winget-installed binaries need a fresh shell session to refresh PATH. Documented in T01 known issues. Will resolve next shell restart. Doesn't affect M004 closure — the verify script greps for the analyzer row regardless of the doctor's overall exit code.

## Verification

All 4 quality gates clean + verify-m004.sh full run (9/9 steps green) + per-provider stub HTTP demos confirm all 5 LLM providers produce valid Analysis instances + doctor reports the analyzer row correctly.

## Requirements Advanced

None.

## Requirements Validated

- R024 — 5 LLM provider adapters shipped (Groq, NVIDIA Build, OpenRouter, OpenAI, Anthropic) under vidscope.adapters.llm with structurally enforced isolation via the 9th import-linter contract. 120 new unit tests covering construction, happy path, error paths, retry, and registry wiring — all via httpx.MockTransport (zero real network). vidscope doctor reports the active analyzer + key status. docs/analyzers.md is the user-facing reference. verify-m004.sh runs 9 steps green including stub-HTTP smoke for every provider. Per-provider env vars: VIDSCOPE_GROQ_API_KEY, VIDSCOPE_NVIDIA_API_KEY, VIDSCOPE_OPENROUTER_API_KEY, VIDSCOPE_OPENAI_API_KEY, VIDSCOPE_ANTHROPIC_API_KEY.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

- vidscope doctor reports ffmpeg as missing in the current dev shell. Pre-existing PATH refresh issue from winget install, unrelated to M004. Will clear next shell restart.
- No live HTTP integration test against real provider endpoints in the verify script. Manual live validation documented in docs/analyzers.md.

## Follow-ups

- M005: cookies UX improvements (browser-extension-based capture) — last remaining milestone.
- Possible future M006: per-video re-analysis with a different provider (e.g. `vidscope reanalyze <id> --provider anthropic`).

## Files Created/Modified

- `src/vidscope/infrastructure/startup.py` — Added check_analyzer() + _ANALYZER_REMEDIATION + registered in run_all_checks
- `tests/unit/infrastructure/test_startup.py` — Added TestCheckAnalyzer class with 6 tests + updated TestRunAllChecks to expect 5 checks
- `docs/analyzers.md` — New user-facing reference for all 7 analyzer names with cost/quota table, per-provider sections, contributor guide, privacy notes
- `scripts/verify-m004.sh` — New 9-step milestone verification script with stub HTTP demos for all 5 LLM providers
- `.gsd/PROJECT.md` — Marked M004 complete in Current State + Milestone Sequence, updated test/source/contract counts, added VIDSCOPE_ANALYZER bullet, R024 validated
- `.gsd/KNOWLEDGE.md` — Added 'LLM analyzer adapter pattern' + 'httpx+mcp forbidden in domain/ports' sections
- `.gsd/REQUIREMENTS.md` — R024 status: deferred -> validated
