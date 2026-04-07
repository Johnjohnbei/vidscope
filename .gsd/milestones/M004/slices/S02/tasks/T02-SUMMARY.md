---
id: T02
parent: S02
milestone: M004
key_files:
  - src/vidscope/adapters/llm/anthropic.py
  - src/vidscope/infrastructure/analyzer_registry.py
  - tests/unit/adapters/llm/test_anthropic.py
  - tests/unit/infrastructure/test_analyzer_registry.py
key_decisions:
  - Anthropic adapter targets native /v1/messages instead of the OpenAI-compat layer — avoids the production caveat documented by Anthropic
  - Reuses _base.parse_llm_json + _base.make_analysis + _base.call_with_retry but NOT run_openai_compatible — request/response shapes too different
  - x-api-key header (Anthropic native convention) instead of Authorization: Bearer
  - Multi-block content array handled defensively — joins text blocks, skips tool_use/image types
  - Default model claude-haiku-4-5 — cheapest production Claude model
duration: 
verification_result: passed
completed_at: 2026-04-07T18:27:55.589Z
blocker_discovered: false
---

# T02: Shipped AnthropicAnalyzer using the native /v1/messages format (not the OpenAI-compat layer). All 5 LLM providers now register. 552 tests, 9 contracts, 81 source files mypy strict.

**Shipped AnthropicAnalyzer using the native /v1/messages format (not the OpenAI-compat layer). All 5 LLM providers now register. 552 tests, 9 contracts, 81 source files mypy strict.**

## What Happened

**The native /v1/messages adapter.** Anthropic's API has a different shape from OpenAI's chat-completion endpoint, and their own docs explicitly state the OpenAI-compatibility layer is "primarily intended to test and compare model capabilities, and is not considered a long-term or production-ready solution." So the AnthropicAnalyzer goes straight at `/v1/messages` to avoid carrying production debt.

**Shape differences from the OpenAI-compatible providers:**

1. **Top-level `system` field** instead of a `role: system` message in the messages array. The adapter takes `_base.build_messages(transcript)` (which produces the standard messages) and splits the system message back out into the top-level field.
2. **`max_tokens` is REQUIRED** (Anthropic 400s without it). Set to 512 to match the other providers.
3. **No `response_format` parameter** — Anthropic doesn't support JSON mode at the API level. JSON output is achieved by asking for JSON in the prompt and running the result through `_base.parse_llm_json` (which handles all the fallback strategies, so this works fine in practice).
4. **Response shape**: `content: [{type: 'text', text: '...'}]` instead of `choices: [{message: {content: '...'}}]`. The adapter walks the content array, picks the text-typed blocks, joins them, and feeds the joined string into `parse_llm_json`. Other block types (`tool_use`, `image`) are skipped silently.
5. **Auth via `x-api-key` header** (Anthropic's native convention) — NOT `Authorization: Bearer`. The test confirms `authorization` header is absent in the actual request.
6. **Required `anthropic-version: 2023-06-01` header**.

**Reuse of the shared toolkit**: even with the different shape, the adapter reuses `_base.parse_llm_json`, `_base.make_analysis`, `_base.call_with_retry`, `_base.LlmCallContext`, `_base.build_messages`. The only thing it doesn't reuse is `run_openai_compatible` because the request and response shapes are too different.

**21 unit tests via `httpx.MockTransport`**, organized into 3 classes:
- `TestConstruction` (3): empty key, whitespace key, valid construction
- `TestAnalyzeHappyPath` (9): provider name + analysis, /v1/messages endpoint URL, x-api-key header (not Bearer), anthropic-version header, top-level system field, max_tokens set, no response_format, custom model, multi-block content joining
- `TestAnalyzeErrors` (7): 429 retry success, 401 fail-fast, 529 overload retry (Anthropic-specific status), missing content array, only non-text blocks, malformed JSON in text block, non-JSON body

**Registry wiring**: added `_build_anthropic()` factory + `VIDSCOPE_ANTHROPIC_API_KEY` + `VIDSCOPE_ANTHROPIC_MODEL` (default `claude-haiku-4-5`). The registry now has **7 names**: heuristic, stub, groq, nvidia, openrouter, openai, anthropic. 5 LLM providers, 2 zero-cost defaults.

**Quality gates after T02**:
- ✅ pytest: **552 passed**, 5 deselected, in 14.59s (was 490 before M004 = +62 LLM tests total)
- ✅ mypy strict: **81 source files** OK (was 80, +1 anthropic.py)
- ✅ ruff: clean (1 long line in `_build_anthropic` docstring fixed)
- ✅ lint-imports: **9 contracts kept**, 0 broken

The `llm-never-imports-other-adapters` contract correctly verified that AnthropicAnalyzer doesn't reach for any other adapter — and that none of the other 4 providers reach for `anthropic.py`.

## Verification

All 4 quality gates clean in parallel: pytest 552 passed in 14.59s, mypy 81 source files OK, ruff clean (after splitting one long docstring line), lint-imports 9 contracts kept.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ 552 passed, 5 deselected | 14590ms |
| 2 | `python -m uv run mypy src` | 0 | ✅ 81 source files OK | 2100ms |
| 3 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept | 2100ms |
| 4 | `python -m uv run ruff check .` | 0 | ✅ all checks passed | 800ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/adapters/llm/anthropic.py`
- `src/vidscope/infrastructure/analyzer_registry.py`
- `tests/unit/adapters/llm/test_anthropic.py`
- `tests/unit/infrastructure/test_analyzer_registry.py`
