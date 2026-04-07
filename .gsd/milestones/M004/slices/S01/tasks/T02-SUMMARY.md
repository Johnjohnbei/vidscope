---
id: T02
parent: S01
milestone: M004
key_files:
  - src/vidscope/adapters/llm/groq.py
  - tests/unit/adapters/llm/test_groq.py
key_decisions:
  - Adapter constructor validates api_key immediately — misconfiguration caught at container build time
  - Injectable httpx.Client via constructor parameter — tests use MockTransport, prod uses real client
  - _owns_client flag tracks whether the adapter is responsible for client.close() — prevents double-close on injected clients
  - _no_sleep autouse fixture in tests — keeps retry tests instant without changing production code
  - Default model llama-3.1-8b-instant — cheapest + fastest Groq model, perfect for short transcripts
duration: 
verification_result: passed
completed_at: 2026-04-07T18:15:49.551Z
blocker_discovered: false
---

# T02: Shipped GroqAnalyzer — first concrete LLM provider, 17 unit tests via httpx.MockTransport, all green.

**Shipped GroqAnalyzer — first concrete LLM provider, 17 unit tests via httpx.MockTransport, all green.**

## What Happened

Created `src/vidscope/adapters/llm/groq.py` with `GroqAnalyzer` class implementing the `Analyzer` Protocol. Validated against current 2026 docs: endpoint `https://api.groq.com/openai/v1/chat/completions`, OpenAI-compatible chat-completion schema, `Authorization: Bearer` header, `response_format: {type: 'json_object'}` supported.

**Constructor**: requires non-empty `api_key` (raises `AnalysisError` immediately at construction time so misconfiguration is caught at container build, not at first call). Optional `model` (default `llama-3.1-8b-instant` — Groq's cheapest/fastest), `base_url`, `timeout`, and `client` parameters. The `client` parameter is the seam tests use to inject `httpx.MockTransport`.

**`analyze(transcript)`** flow:
1. Build messages via `_base.build_messages` (shared prompt template)
2. Build request body with `model`, `messages`, `temperature: 0.2`, `response_format: json_object`, `max_tokens: 512`
3. Build `LlmCallContext` with auth header and JSON body
4. Call `_base.call_with_retry(client, ctx)` — handles 429/5xx retry + timeouts
5. Parse JSON response, extract `choices[0].message.content`
6. Run extracted content through `_base.parse_llm_json` → `_base.make_analysis`
7. Return domain `Analysis` instance with `provider="groq"`

**Error paths covered**: empty/whitespace api_key, 401 fail-fast, 429-then-success retry, timeout-then-success retry, missing `choices` field, non-JSON body, missing `message.content`, malformed JSON in `content`.

**`client` lifecycle**: when caller injects a client (tests), GroqAnalyzer never closes it. When the adapter creates its own (production), it closes it after each call via `try/finally`. The `_owns_client` flag tracks this.

**17 unit tests** in `test_groq.py`, organized into 3 classes:
- `TestConstruction` (5): empty key, whitespace key, valid construction, custom model, key whitespace stripped
- `TestAnalyzeHappyPath` (5): provider name + analysis shape, Authorization header, endpoint URL, model passthrough, response_format request param
- `TestAnalyzeErrors` (7): 429 retry success, 401 fail fast, missing choices, non-JSON body, missing content, malformed content JSON, timeout retry success

The `_no_sleep` autouse fixture monkeypatches `_base.time.sleep` to a no-op so retry tests run instantly. Total runtime ~2 seconds for 17 tests including the retry paths.

**Quality gate after T02**: 466 + 17 = 483 unit tests for the LLM adapters (34 base + 17 groq). Full pytest run + mypy + import-linter run in T03 along with the registry wiring.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/llm/test_groq.py -q` → 17 passed in 2.17s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/llm/test_groq.py -q` | 0 | ✅ 17/17 GroqAnalyzer tests green | 2170ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/adapters/llm/groq.py`
- `tests/unit/adapters/llm/test_groq.py`
