---
id: T01
parent: S01
milestone: M004
key_files:
  - src/vidscope/adapters/llm/__init__.py
  - src/vidscope/adapters/llm/_base.py
  - tests/unit/adapters/llm/__init__.py
  - tests/unit/adapters/llm/test_base.py
key_decisions:
  - One shared prompt template across every provider — same JSON output schema means make_analysis stays simple
  - parse_llm_json with 3-stage fallback — different providers wrap JSON differently and we don't want vendor-specific parsers
  - Injectable sleep parameter on call_with_retry — test runs in microseconds, no time.sleep in CI
  - LlmCallContext as a typed dataclass — explicit beats kwargs sprawl
  - Transcript language takes precedence over LLM-reported language — Whisper is more reliable than LLM self-assessment
duration: 
verification_result: passed
completed_at: 2026-04-07T18:09:23.386Z
blocker_discovered: false
---

# T01: Shipped the shared LLM adapter helpers (_base.py): build_messages, parse_llm_json, call_with_retry, make_analysis. 34 unit tests via httpx.MockTransport, all green.

**Shipped the shared LLM adapter helpers (_base.py): build_messages, parse_llm_json, call_with_retry, make_analysis. 34 unit tests via httpx.MockTransport, all green.**

## What Happened

Created `src/vidscope/adapters/llm/__init__.py` (package marker + module docstring naming the future 5 providers + import-linter expectation) and `src/vidscope/adapters/llm/_base.py` (the shared toolkit).

**`build_messages(transcript)`** returns the OpenAI-compatible chat-completion messages list. System message is the strict-JSON prompt template asking for `language`, `keywords`, `topics`, `score`, `summary`. User message includes the language hint + transcript text (or `[no speech detected]` placeholder for empty transcripts). Same template across every future provider — guarantees consistent JSON shape.

**`parse_llm_json(raw)`** extracts a JSON object from the model's raw text output with three fallback strategies:
1. Bare JSON (the model followed instructions)
2. Markdown-fenced JSON (```json ... ``` or untagged ```...```)
3. First `{ ... }` substring (handles trailing/leading prose)

Empty input → AnalysisError("empty"). No parseable object → AnalysisError("parseable"). Malformed JSON in fence → AnalysisError("malformed"). All errors are non-retryable.

**`call_with_retry(client, ctx, sleep=time.sleep)`** is the retry helper. Retries on 429, 5xx, `httpx.TimeoutException`, `httpx.TransportError`. Fails fast on other 4xx. Exponential backoff (1s, 2s, 4s, capped at 8s). The `sleep` parameter is injectable so tests can pass `lambda _: None` and run instantly. Default `max_attempts=3`.

**`make_analysis(parsed, transcript, *, provider)`** turns parsed JSON into a domain `Analysis` instance. Defensive about every key:
- `keywords`: lowercased + stripped + capped at 10 + non-empty filter
- `topics`: stripped + capped at 3 + non-empty filter
- `score`: clamped to [0, 100], invalid values fall back to None
- `summary`: truncated to 200 chars
- `language`: prefers transcript's detected language, falls back to LLM's value only if transcript is UNKNOWN

**`LlmCallContext`** is the typed bag of arguments threaded through `call_with_retry` (method, url, headers, json_body, timeout, max_attempts).

**34 unit tests** in `test_base.py`, organized into 5 classes:
- `TestBuildMessages` (5): system + user shape, language hint, transcript text, empty placeholder, JSON instructions
- `TestParseLlmJson` (9): bare JSON, fenced JSON, untagged fence, trailing prose, empty/whitespace/no-JSON failures, malformed-in-fence, nested objects
- `TestCallWithRetry` (9): happy path, 429-then-success, 500-then-success, 429-exhausts, 400-fails-fast, 401-fails-fast, timeout-then-success, timeout-exhausts, default-max-attempts assertion
- `TestMakeAnalysis` (11): happy path, keyword lowercase + cap, topics cap, score clamp, score invalid → None, summary truncation, missing keys → defaults, empty-string filter, language fallback (UNKNOWN → LLM), transcript precedence (Whisper wins), non-dict raises

Every HTTP test uses `httpx.MockTransport` so there is zero real network. The retry tests pass `sleep=lambda _: None` so they run in microseconds.

**Quality gate after T01:** 466 unit tests (432 + 34 new), pytest clean. mypy + lint-imports + ruff not yet rerun for the new package — done in T03 along with the import-linter contract addition.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/llm/test_base.py -q` → 34 passed in 0.15s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/llm/test_base.py -q` | 0 | ✅ 34/34 LLM base tests green | 150ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/adapters/llm/__init__.py`
- `src/vidscope/adapters/llm/_base.py`
- `tests/unit/adapters/llm/__init__.py`
- `tests/unit/adapters/llm/test_base.py`
