---
id: T01
parent: S02
milestone: M004
key_files:
  - src/vidscope/adapters/llm/_base.py
  - src/vidscope/adapters/llm/groq.py
  - src/vidscope/adapters/llm/nvidia_build.py
  - src/vidscope/adapters/llm/openrouter.py
  - src/vidscope/adapters/llm/openai.py
  - src/vidscope/infrastructure/analyzer_registry.py
  - tests/unit/adapters/llm/test_nvidia_build.py
  - tests/unit/adapters/llm/test_openrouter.py
  - tests/unit/adapters/llm/test_openai.py
  - tests/unit/infrastructure/test_analyzer_registry.py
key_decisions:
  - Factored shared run_openai_compatible helper into _base.py — each concrete provider now ~50 lines instead of ~120
  - Refactored groq.py to delegate to the helper — same 17 tests still pass
  - OpenRouter sends HTTP-Referer + X-Title — VidScope appears on the OpenRouter leaderboards
  - Each provider factory reads env at invocation time — importing the registry never crashes
duration: 
verification_result: passed
completed_at: 2026-04-07T18:24:53.527Z
blocker_discovered: false
---

# T01: Shipped 3 OpenAI-compatible LLM providers (NVIDIA Build, OpenRouter, OpenAI) + factored shared `run_openai_compatible` helper. 4 quality gates clean, registry now has 6 names.

**Shipped 3 OpenAI-compatible LLM providers (NVIDIA Build, OpenRouter, OpenAI) + factored shared `run_openai_compatible` helper. 4 quality gates clean, registry now has 6 names.**

## What Happened

**Refactor first.** Before adding the 3 new providers, I extracted a `run_openai_compatible(client, base_url, api_key, model, transcript, provider_name, ...)` helper into `_base.py`. Reason: Groq's `analyze()` had ~30 lines of generic logic (build body, build context, call retry, parse choices/message/content) and the next 3 providers would have been pure copy-paste.

The helper takes the provider-specific bits as kwargs (`base_url`, `api_key`, `model`, `provider_name`, `extra_headers`, `use_json_response_format`) and returns a domain `Analysis`. Each concrete provider is now ~50 lines of constructor + delegate. Refactored `groq.py` to use the helper — its 17 tests still pass unchanged.

**Three new providers**, each in its own file:

`nvidia_build.py` (NvidiaBuildAnalyzer):
- `https://integrate.api.nvidia.com/v1/chat/completions`
- Default model `meta/llama-3.1-8b-instruct`
- env `VIDSCOPE_NVIDIA_API_KEY` (`nvapi-` prefix from build.nvidia.com)
- 9 unit tests via `httpx.MockTransport`

`openrouter.py` (OpenRouterAnalyzer):
- `https://openrouter.ai/api/v1/chat/completions`
- Default model `meta-llama/llama-3.3-70b-instruct:free`
- env `VIDSCOPE_OPENROUTER_API_KEY`
- Sends `HTTP-Referer` + `X-Title` headers so VidScope shows up on the OpenRouter leaderboards
- 9 unit tests including a dedicated test for the identification headers

`openai.py` (OpenAIAnalyzer):
- `https://api.openai.com/v1/chat/completions`
- Default model `gpt-4o-mini` (cheapest production model)
- env `VIDSCOPE_OPENAI_API_KEY`
- 10 unit tests including a 503-then-success retry path

**Registry wiring** (`analyzer_registry.py`):
- Added 3 factories: `_build_nvidia()`, `_build_openrouter()`, `_build_openai()`
- Each factory follows the same pattern as `_build_groq`: read env at invocation time, validate non-empty, wrap construction errors in `ConfigError` with actionable signup URL
- Registry now has 6 names: heuristic, stub, groq, nvidia, openrouter, openai
- Module docstring lists all 5 LLM providers with the slice that ships them

**Registry test coverage**:
- New `TestBuildNvidiaAnalyzer`, `TestBuildOpenRouterAnalyzer`, `TestBuildOpenAIAnalyzer` classes
- Each: missing key → ConfigError, valid key → instance, error message includes signup URL
- 9 new registry tests on top of the existing 7 groq tests

**Quality gates**:
- ✅ ruff: clean (1 long line in `_build_openrouter` docstring + error message — split into multiple lines)
- ✅ mypy strict: 80 source files OK (was 77, +3 new providers)
- ✅ pytest: LLM + registry suites = 105 passed in 8.56s
- ✅ lint-imports: 9 contracts kept, 0 broken

The `llm-never-imports-other-adapters` contract correctly verified that none of the 3 new providers imports any other adapter — each only imports `_base.py` + domain.

## Verification

Ran all 4 quality gates after the new files landed. All green. Specifically:\n- pytest tests/unit/adapters/llm tests/unit/infrastructure/test_analyzer_registry.py = 105 passed in 8.56s\n- mypy src = 80 source files OK\n- ruff check . = all checks passed (after fixing 1 long line)\n- lint-imports = 9 contracts kept

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/llm tests/unit/infrastructure/test_analyzer_registry.py -q` | 0 | ✅ 105 passed | 8560ms |
| 2 | `python -m uv run mypy src` | 0 | ✅ 80 source files OK | 2100ms |
| 3 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept | 2100ms |
| 4 | `python -m uv run ruff check .` | 0 | ✅ all checks passed | 800ms |

## Deviations

Refactored shared logic into `run_openai_compatible` helper instead of leaving `groq.py` as the canonical example with copy-paste in the new files. This is a positive deviation — eliminates ~80 lines of duplication and makes future provider additions ~30 lines instead of ~80.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/adapters/llm/_base.py`
- `src/vidscope/adapters/llm/groq.py`
- `src/vidscope/adapters/llm/nvidia_build.py`
- `src/vidscope/adapters/llm/openrouter.py`
- `src/vidscope/adapters/llm/openai.py`
- `src/vidscope/infrastructure/analyzer_registry.py`
- `tests/unit/adapters/llm/test_nvidia_build.py`
- `tests/unit/adapters/llm/test_openrouter.py`
- `tests/unit/adapters/llm/test_openai.py`
- `tests/unit/infrastructure/test_analyzer_registry.py`
