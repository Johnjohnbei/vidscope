---
id: S02
parent: M004
milestone: M004
provides:
  - 5 concrete LLM analyzer adapters ready for use
  - Shared run_openai_compatible helper for any future OpenAI-compatible provider
  - Pattern for non-compatible providers (use Anthropic's adapter as template)
requires:
  - slice: S01
    provides: _base.py shared helpers + analyzer_registry pattern + llm-never-imports-other-adapters import-linter contract
affects:
  - S03: doctor + docs + verify-m004.sh now have all 5 providers to display + document
key_files:
  - src/vidscope/adapters/llm/_base.py
  - src/vidscope/adapters/llm/groq.py
  - src/vidscope/adapters/llm/nvidia_build.py
  - src/vidscope/adapters/llm/openrouter.py
  - src/vidscope/adapters/llm/openai.py
  - src/vidscope/adapters/llm/anthropic.py
  - src/vidscope/infrastructure/analyzer_registry.py
  - tests/unit/adapters/llm/test_nvidia_build.py
  - tests/unit/adapters/llm/test_openrouter.py
  - tests/unit/adapters/llm/test_openai.py
  - tests/unit/adapters/llm/test_anthropic.py
  - tests/unit/infrastructure/test_analyzer_registry.py
key_decisions:
  - Factored run_openai_compatible into _base.py to keep concrete adapters at ~50 lines each
  - Anthropic adapter targets native /v1/messages instead of the OpenAI-compat layer — avoids the production caveat documented by Anthropic
  - OpenRouter sends HTTP-Referer + X-Title headers — VidScope appears on the OpenRouter leaderboards
  - Each provider has its own per-name VIDSCOPE_<NAME>_API_KEY + VIDSCOPE_<NAME>_MODEL convention — no shared LLM_API_KEY ambiguity
patterns_established:
  - For OpenAI-compatible providers: ~50-line adapter file delegating to run_openai_compatible(...)
  - For non-OpenAI-compatible providers (Anthropic): ~150-line adapter file reusing _base parse_llm_json + make_analysis + call_with_retry but with provider-specific request/response shape
  - Registry factory shape: read env, validate, wrap construction errors in ConfigError with actionable signup URL
observability_surfaces:
  - Each LLM provider's call_with_retry logs every retry attempt with status code
  - Each registry factory raises ConfigError with provider-specific signup URL on missing key
drill_down_paths:
  - .gsd/milestones/M004/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S02/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T18:28:58.603Z
blocker_discovered: false
---

# S02: Remaining 4 LLM providers (NVIDIA Build, OpenRouter, OpenAI, Anthropic)

**Shipped 4 more LLM providers (3 OpenAI-compatible + Anthropic native) and refactored shared logic into run_openai_compatible. All 5 LLM providers now register under their canonical names. 552 tests, 9 contracts, 81 source files mypy strict.**

## What Happened

S02 was the scaling slice for M004 — proving that the foundation built in S01 actually delivers on "adding a provider is one new file."

**Two tasks, both delivered straight through.**

T01 added the 3 OpenAI-compatible providers (NVIDIA Build, OpenRouter, OpenAI). The big realization here was that copying GroqAnalyzer 3 times would have generated ~80 lines of duplication. So the first step was extracting `run_openai_compatible(client, base_url, api_key, model, transcript, provider_name, ...)` as a shared helper in `_base.py`. Then `groq.py` was refactored to delegate to it (its 17 tests still pass unchanged), and the 3 new providers became ~50 lines each.

T02 added AnthropicAnalyzer using the **native `/v1/messages` format**, NOT the OpenAI-compatibility layer. The decision was based on Anthropic's own docs which describe the compat layer as "primarily intended to test and compare model capabilities, and is not considered a long-term or production-ready solution." The adapter handles the four shape differences (top-level system field, required max_tokens, no response_format, content array vs choices), uses x-api-key (not Bearer), and reuses parse_llm_json + make_analysis + call_with_retry from _base.

**Final registry**: 7 names. heuristic + stub (zero-cost defaults) + groq + nvidia + openrouter + openai + anthropic (5 LLM providers). Each LLM provider has its own VIDSCOPE_<NAME>_API_KEY env var, its own VIDSCOPE_<NAME>_MODEL override, and a clear ConfigError with a signup URL when the key is missing.

**Architectural enforcement validated**: the `llm-never-imports-other-adapters` contract from S01 correctly caught zero violations across the 4 new files. None of the 5 LLM providers imports any other adapter — each only touches `_base` + domain. The contract pays for itself the first time someone tries to add a provider that takes a shortcut.

**Test count progression**: 432 (M003) → 490 (S01: +58) → 552 (S02: +62). 120 new LLM-related tests across base, registry, and 5 provider files.

**No deviations, no replans, no blockers.** The foundation in S01 was correct. S02 is essentially a bigger version of S01's refactor task: write the file, write the tests, register the factory, run the gates. S03 (doctor + docs + verify-m004.sh + R024 closure) is next.

## Verification

All 4 quality gates clean in parallel: pytest 552 passed in 14.59s, mypy 81 source files OK, ruff clean, lint-imports 9 contracts kept. Per-task gates also confirmed: 105 tests for the LLM adapters + analyzer registry combined.

## Requirements Advanced

- R024 — All 5 concrete LLM providers shipped with construction validation + per-provider env conventions + structural import-linter enforcement. Status will move to validated after S03 closes the milestone.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Refactored shared logic into `run_openai_compatible` helper instead of leaving groq.py as the canonical example with copy-paste in the new files. This is a positive deviation — eliminates ~80 lines of duplication.

## Known Limitations

- No live HTTP test against real provider endpoints yet — covered by stubbed httpx.MockTransport. S03 verify-m004.sh ships with --live flag for optional real-API smoke testing.
- AnthropicAnalyzer uses native /v1/messages so cannot be swapped through Anthropic's own compat layer if a user wants that. Documented in module docstring.

## Follow-ups

- S03: vidscope doctor analyzer status row (showing active analyzer name + key configured), docs/analyzers.md (per-provider env vars + signup URLs + cost/limit notes), verify-m004.sh (4 quality gates + 7 registry names smoke + per-provider stub-HTTP demo), R024 → validated.

## Files Created/Modified

- `src/vidscope/adapters/llm/_base.py` — Added run_openai_compatible shared helper
- `src/vidscope/adapters/llm/groq.py` — Refactored to delegate to run_openai_compatible
- `src/vidscope/adapters/llm/nvidia_build.py` — New NvidiaBuildAnalyzer (OpenAI-compatible)
- `src/vidscope/adapters/llm/openrouter.py` — New OpenRouterAnalyzer with X-Title + HTTP-Referer headers
- `src/vidscope/adapters/llm/openai.py` — New OpenAIAnalyzer (canonical OpenAI-compatible shape)
- `src/vidscope/adapters/llm/anthropic.py` — New AnthropicAnalyzer using native /v1/messages format
- `src/vidscope/infrastructure/analyzer_registry.py` — Added _build_nvidia/openrouter/openai/anthropic factories + 4 env var conventions
- `tests/unit/adapters/llm/test_nvidia_build.py` — 9 unit tests for NvidiaBuildAnalyzer
- `tests/unit/adapters/llm/test_openrouter.py` — 9 unit tests for OpenRouterAnalyzer including identification headers
- `tests/unit/adapters/llm/test_openai.py` — 10 unit tests for OpenAIAnalyzer including 503 retry
- `tests/unit/adapters/llm/test_anthropic.py` — 21 unit tests for AnthropicAnalyzer including native /v1/messages shape, x-api-key header, multi-block content joining
- `tests/unit/infrastructure/test_analyzer_registry.py` — Added TestBuildNvidia/OpenRouter/OpenAI/AnthropicAnalyzer classes (12 new tests)
