---
id: S01
parent: M004
milestone: M004
provides:
  - Shared LLM helper layer (_base.py) — ready for nvidia/openrouter/openai/anthropic adapters in S02
  - Registry pattern for adding env-driven LLM provider factories
  - 9th import-linter contract enforcing llm package isolation
requires:
  []
affects:
  - S02: 4 more providers will reuse _base unchanged
  - S03: doctor + docs + verify-m004.sh
key_files:
  - src/vidscope/adapters/llm/__init__.py
  - src/vidscope/adapters/llm/_base.py
  - src/vidscope/adapters/llm/groq.py
  - src/vidscope/infrastructure/analyzer_registry.py
  - .importlinter
  - tests/unit/adapters/llm/__init__.py
  - tests/unit/adapters/llm/test_base.py
  - tests/unit/adapters/llm/test_groq.py
  - tests/unit/infrastructure/test_analyzer_registry.py
key_decisions:
  - Shared _base.py with build_messages + parse_llm_json + call_with_retry + make_analysis — every concrete provider stays under ~80 lines
  - Three-stage JSON fallback parser — handles bare JSON, markdown fenced, and first-{...} substring
  - Injectable sleep parameter on call_with_retry — retry tests run in microseconds
  - Injectable httpx.Client on every concrete adapter — tests use MockTransport, prod uses real client
  - API key read at factory invocation, not at module import — importing registry never crashes
  - 9th import-linter contract: llm-never-imports-other-adapters — structurally enforces one-provider-per-file
  - httpx + mcp added to domain/ports forbidden list — guards against regression
  - Anthropic adapter (S02) will use native /v1/messages, not OpenAI-compat layer — compat layer is not production-ready per Anthropic docs
patterns_established:
  - Concrete LLM provider shape: _base helpers + provider-specific URL/auth/model + try/finally client lifecycle
  - Registry factory pattern: read env at invocation time, wrap construction errors in ConfigError with actionable message
  - httpx.MockTransport for adapter tests — zero network, full code path coverage
  - Adapter isolation enforced via dedicated import-linter contract per adapter package
observability_surfaces:
  - Logging in _base.call_with_retry: each retry attempt logs status code + attempt number
  - GroqAnalyzer constructor surfaces missing api_key as AnalysisError immediately at container build
  - Registry _build_groq surfaces missing env var as ConfigError with signup URL
drill_down_paths:
  - .gsd/milestones/M004/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T18:19:48.061Z
blocker_discovered: false
---

# S01: LLM adapter foundation: shared base + first concrete provider (Groq)

**Built the LLM adapter foundation: shared `_base.py` (prompt/parse/retry/make_analysis), first concrete provider Groq, registry wiring, 9th import-linter contract for llm isolation. 58 new LLM tests, all 4 gates green.**

## What Happened

S01 was the architecture-validating slice for M004. The point was to prove the design before scaling to 5 providers — write the shared toolkit + one concrete provider + the structural enforcement, then verify that adding the next 4 is just "another file under llm/".

**Three tasks, all delivered straight through, no replans.**

T01 built the shared foundation:
- `build_messages(transcript)` — system + user message tuple, identical across providers
- `parse_llm_json(raw)` — three-stage fallback: bare JSON → markdown-fenced → first `{...}` substring
- `call_with_retry(client, ctx, sleep)` — exponential backoff, retries 429/5xx/timeout, fails fast on other 4xx, injectable sleep for instant tests
- `make_analysis(parsed, transcript, *, provider)` — defensive conversion to domain `Analysis`, clamps score, caps keywords/topics, prefers Whisper's language over LLM's
- `LlmCallContext` typed dataclass

34 unit tests covering every fallback + retry path via `httpx.MockTransport`.

T02 built `GroqAnalyzer`. Constructor validates non-empty `api_key` immediately. `analyze()` builds messages → builds request body → calls `call_with_retry` → parses `choices[0].message.content` → runs through `parse_llm_json` + `make_analysis`. Injectable `httpx.Client` for tests, owns the client when not injected (closes via try/finally).

17 unit tests: 5 construction, 5 happy path, 7 error paths (401 fail-fast, 429 retry, missing choices, non-JSON body, missing content, malformed content JSON, timeout retry).

T03 wired Groq into the registry and added the structural enforcement:
- `_build_groq()` factory reads `VIDSCOPE_GROQ_API_KEY` + `VIDSCOPE_GROQ_MODEL` at invocation time (not import time)
- Registry now has 3 names: heuristic, stub, groq
- New 9th import-linter contract `llm-never-imports-other-adapters` forbids any cross-adapter coupling
- `httpx` + `mcp` added to domain/ports forbidden lists
- All 4 of {pipeline, application, mcp} forbidden lists now explicitly include `vidscope.adapters.llm`
- 7 new registry tests including `monkeypatch.setenv`/`delenv` for the env-driven factory

**Pre-flight provider research (during S01 execution).** Before writing the Groq code I verified all 5 future providers are still operational in 2026 via web search. Findings:
- Groq: free tier intact, 30 RPM/14400 RPD on Llama 3.1 8B, OpenAI-compatible, `Authorization: Bearer`. Default model `llama-3.1-8b-instant` confirmed.
- NVIDIA Build: free tier with 1000 inference credits at signup, `nvapi-` keys, `https://integrate.api.nvidia.com/v1/chat/completions`, OpenAI-compatible.
- OpenRouter: 50 free requests/day without credits / 1000 with ≥10 credits, 29 `:free` models, `https://openrouter.ai/api/v1/chat/completions`, OpenAI-compatible, `response_format` supported.
- OpenAI: $5-18 free credits historically then pay-per-use. Endpoint stable.
- Anthropic: native API at `/v1/messages`, OpenAI compatibility layer at `https://api.anthropic.com/v1/chat/completions` documented as not for production. Decision recorded for S02: write the Anthropic adapter against `/v1/messages` natively to avoid the compat-layer caveat.

**Final state.** 9 import-linter contracts kept. 490 unit tests green (was 432, +58). mypy strict on 77 source files. ruff clean. The next 4 providers in S02 are pure replication: copy `groq.py`, change URL + auth header + model name, add a factory in the registry, add tests. No `_base.py` changes anticipated.

## Verification

All 4 quality gates green in parallel: ruff clean, mypy 77 files, pytest 490 passed in 6.42s, lint-imports 9 contracts kept. Slice tests: 58 new LLM unit tests (34 base + 17 groq + 7 registry) all green.

## Requirements Advanced

- R024 — Foundation built: shared base + 1 of 5 providers shipped, registry wiring + import-linter enforcement. Status will move to validated after S02+S03.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

- No live HTTP test against real Groq API yet — covered by stubbed httpx.MockTransport. A live smoke test against the real Groq endpoint with a real API key is planned for S03 verify-m004.sh (optional, gated behind --live flag). 
- Anthropic compat-layer caveat noted: S02 will write the Anthropic adapter against /v1/messages natively, not via the OpenAI-compat layer.

## Follow-ups

- S02: replicate the groq.py shape for nvidia_build, openrouter, openai, anthropic. anthropic uses /v1/messages natively (not the compat layer). 
- S03: vidscope doctor analyzer status row, docs/analyzers.md, verify-m004.sh, R024 validation.

## Files Created/Modified

- `src/vidscope/adapters/llm/__init__.py` — New package marker + module docstring listing all 5 future providers
- `src/vidscope/adapters/llm/_base.py` — New shared LLM toolkit: build_messages, parse_llm_json, call_with_retry, make_analysis, LlmCallContext
- `src/vidscope/adapters/llm/groq.py` — New GroqAnalyzer concrete adapter against Groq's OpenAI-compatible API
- `src/vidscope/infrastructure/analyzer_registry.py` — Added _build_groq factory + registered 'groq' name + updated docstring listing all 5 providers
- `.importlinter` — Added httpx+mcp to domain/ports forbidden, added llm to pipeline/application/mcp forbidden, new contract llm-never-imports-other-adapters
- `tests/unit/adapters/llm/__init__.py` — New package marker
- `tests/unit/adapters/llm/test_base.py` — 34 unit tests for shared LLM helpers
- `tests/unit/adapters/llm/test_groq.py` — 17 unit tests for GroqAnalyzer via httpx.MockTransport
- `tests/unit/infrastructure/test_analyzer_registry.py` — 7 new tests for groq factory: missing key, valid key, custom model, signup URL in error message
