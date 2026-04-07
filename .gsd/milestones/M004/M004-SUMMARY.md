---
id: M004
title: "Pluggable LLM analyzers"
status: complete
completed_at: 2026-04-07T18:38:34.657Z
key_decisions:
  - Shared _base.py toolkit — every LLM provider stays at ~50 lines (OpenAI-compatible) or ~150 lines (non-compatible)
  - run_openai_compatible helper extracted in S02 — 4 of 5 providers delegate to it, eliminating ~80 lines of duplication
  - Anthropic adapter targets native /v1/messages instead of the OpenAI-compat layer — avoids the production-readiness caveat documented by Anthropic
  - Per-provider env vars (VIDSCOPE_<PROVIDER>_API_KEY) instead of a shared LLM_API_KEY — unambiguous, doctor can report exactly which key is missing
  - API key read at factory invocation time, not at module import — importing the registry never crashes on missing keys
  - 9th import-linter contract (llm-never-imports-other-adapters) — structural enforcement of one-file-per-provider
  - httpx + mcp added to domain/ports forbidden lists — innermost layers stay 100% stdlib + typing
  - OpenRouter sends HTTP-Referer + X-Title — VidScope appears on the OpenRouter leaderboards
  - verify-m004.sh exercises all 5 providers in one Python invocation with shared transcript fixture — fast + reproducible
key_files:
  - src/vidscope/adapters/llm/__init__.py
  - src/vidscope/adapters/llm/_base.py
  - src/vidscope/adapters/llm/groq.py
  - src/vidscope/adapters/llm/nvidia_build.py
  - src/vidscope/adapters/llm/openrouter.py
  - src/vidscope/adapters/llm/openai.py
  - src/vidscope/adapters/llm/anthropic.py
  - src/vidscope/infrastructure/analyzer_registry.py
  - src/vidscope/infrastructure/startup.py
  - .importlinter
  - tests/unit/adapters/llm/test_base.py
  - tests/unit/adapters/llm/test_groq.py
  - tests/unit/adapters/llm/test_nvidia_build.py
  - tests/unit/adapters/llm/test_openrouter.py
  - tests/unit/adapters/llm/test_openai.py
  - tests/unit/adapters/llm/test_anthropic.py
  - tests/unit/infrastructure/test_analyzer_registry.py
  - tests/unit/infrastructure/test_startup.py
  - docs/analyzers.md
  - scripts/verify-m004.sh
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
lessons_learned:
  - When a user asks 'have you verified X is still available' — always do the research before continuing. The Anthropic compat-layer caveat would have shipped silently otherwise.
  - Refactor shared logic into a helper as soon as you have 2 implementations — don't wait for 5. Extracting run_openai_compatible after groq.py was the right call before scaling to 4 more.
  - Structurally enforced architecture rules pay off the first time you scale. The 9th import-linter contract caught zero violations across 4 new files in S02 — because the test was watching from day one.
  - Per-resource env var conventions (VIDSCOPE_<PROVIDER>_API_KEY) are more usable than shared keys (LLM_API_KEY). The doctor can say exactly which env var is missing instead of generic 'no API key set'.
  - Read provider docs before writing the adapter, not after debugging the first 401. Anthropic's native vs compat-layer choice was made on day 1 because of pre-flight research.
---

# M004: Pluggable LLM analyzers

**Shipped 5 LLM analyzer providers (Groq, NVIDIA Build, OpenRouter, OpenAI, Anthropic) behind a structurally enforced one-file-per-provider architecture. Heuristic stays the zero-cost default.**

## What Happened

M004 delivered the pluggable LLM analyzer system in 3 slices with no replans, no blockers, and no scope changes.

**S01** built the foundation: shared `_base.py` toolkit (`build_messages`, `parse_llm_json`, `call_with_retry`, `make_analysis`, `LlmCallContext`) + first concrete provider (Groq) + registry wiring + new 9th import-linter contract `llm-never-imports-other-adapters`. The contract is the architectural payoff — adding any new file under `vidscope/adapters/llm/` is automatically subject to the isolation rule with zero `.importlinter` edits.

**S02** scaled to 4 more providers. NVIDIA Build, OpenRouter, OpenAI follow the OpenAI-compatible pattern via the new `run_openai_compatible(client, base_url, api_key, model, transcript, provider_name, ...)` helper extracted from groq.py — each adapter file is ~50 lines. Anthropic uses native `/v1/messages` instead of the OpenAI-compat layer because Anthropic's own docs describe the compat layer as not production-ready. The Anthropic adapter is ~150 lines because it owns the request/response shape but still reuses `parse_llm_json`, `make_analysis`, `call_with_retry` from `_base.py`.

**S03** wired the operational layer: `vidscope doctor` analyzer status row (5 distinct states), `docs/analyzers.md` user reference + contributor guide, `verify-m004.sh` (9 steps green including stub-HTTP smoke for every provider), R024 validation, PROJECT.md + KNOWLEDGE.md updates.

**Pre-flight provider research.** Before writing GroqAnalyzer in S01 the user pushed back: "have you actually verified Groq and ChatGPT are still available?" That triggered web research across all 5 providers in 2026. Findings: all 5 operational, all 5 OpenAI-compatible (or via documented compat layer for Anthropic), free tiers verified for Groq/NVIDIA/OpenRouter, paid tiers for OpenAI/Anthropic with starter credits. The Anthropic compat-layer caveat surfaced from that research and shaped the S02 adapter design.

**Architecture wins**:
- 9 import-linter contracts (was 8), all kept
- `httpx` and `mcp` added to `domain-is-pure` + `ports-are-pure` forbidden lists
- 81 source files (was 74), all mypy strict-clean
- One LLM provider per file structurally enforced — zero risk of vendor SDK leakage into application/pipeline/cli/mcp layers
- Shared toolkit means adding a 6th OpenAI-compatible provider in the future is ~50 lines + tests

**Testing**:
- 558 unit tests (was 432, +126 LLM-related)
- 86 LLM adapter unit tests via `httpx.MockTransport` (zero real network)
- 19 registry tests covering env-driven factories
- 6 startup tests for the new analyzer doctor check
- 9 unit tests added for `_base.run_openai_compatible` (covered indirectly via groq + nvidia + openrouter + openai test suites)

**M004 was the smoothest milestone yet.** No blockers, no replans, no integration surprises. The S01 foundation held perfectly — S02 added 4 providers without touching `_base.py` semantics, and S03 closed everything in one task. The one user interjection (provider availability check) made the design better (Anthropic native API choice).

## Success Criteria Results

All 8 success criteria met. Full evidence in `.gsd/milestones/M004/M004-VALIDATION.md`.

- [x] _base.py shared helpers shipped (6 functions/classes, 34 unit tests)
- [x] 5 concrete adapters in their own files
- [x] Same prompt + JSON output schema across all 5
- [x] Stubbed HTTP unit tests for every adapter (86 total)
- [x] Per-provider env vars + clean ConfigError on missing key
- [x] vidscope doctor reports analyzer + key status
- [x] All 4 quality gates clean + 9 import-linter contracts kept
- [x] verify-m004.sh 9/9 green via stubbed HTTP

## Definition of Done Results

- [x] All 5 LLM adapter files exist and pass unit tests via stubbed HTTP
- [x] analyzer_registry resolves all 5 by name (groq, nvidia, openrouter, openai, anthropic)
- [x] VIDSCOPE_ANALYZER env var selects the active analyzer at container build time
- [x] Container build fails cleanly when API key for selected provider is missing (ConfigError with signup URL)
- [x] vidscope doctor shows active analyzer + key status (5 distinct states)
- [x] import-linter contract: each LLM provider file may only import shared helpers + domain + ports (enforced by llm-never-imports-other-adapters)
- [x] verify-m004.sh exits 0 (9/9 steps green)
- [x] docs/analyzers.md complete (~11KB user reference + contributor guide)
- [x] R024 marked validated

## Requirement Outcomes

## Requirement status transitions

- **R024** (LLM analyzer providers) → `deferred` → `active` (M004 start) → `validated` (M004 close)
  Evidence: 5 concrete adapter files (`vidscope/adapters/llm/{groq,nvidia_build,openrouter,openai,anthropic}.py`) implementing the `Analyzer` Protocol. Shared `_base.py` toolkit. 9th import-linter contract `llm-never-imports-other-adapters`. 86 LLM adapter unit tests + 19 registry tests + 6 startup tests via `httpx.MockTransport` (zero real network). `vidscope doctor` analyzer row with 5 states. `docs/analyzers.md` user reference. `verify-m004.sh` 9/9 green.

No new requirements surfaced. No requirements invalidated.

## Deviations

None.

## Follow-ups

None.
