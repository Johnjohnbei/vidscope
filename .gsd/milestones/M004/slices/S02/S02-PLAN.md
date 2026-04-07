# S02: Remaining 4 providers (NVIDIA Build, OpenRouter, OpenAI, Anthropic)

**Goal:** Add the remaining 4 LLM providers (NVIDIA Build, OpenRouter, OpenAI, Anthropic) as concrete adapters under `vidscope.adapters.llm`. Each provider is a single file extending the shared `_base.py` from S01. The Anthropic adapter uses the native `/v1/messages` format (not the OpenAI-compat layer) to avoid the production caveat documented by Anthropic.
**Demo:** After this: All 5 LLM analyzers register and pass their unit tests.

## Tasks
- [x] **T01: Shipped 3 OpenAI-compatible LLM providers (NVIDIA Build, OpenRouter, OpenAI) + factored shared `run_openai_compatible` helper. 4 quality gates clean, registry now has 6 names.** — Three OpenAI-compatible providers in one task because they share 95% of the code with GroqAnalyzer:
- nvidia_build.py: base_url https://integrate.api.nvidia.com/v1, default model meta/llama-3.1-8b-instruct, env VIDSCOPE_NVIDIA_API_KEY
- openrouter.py: base_url https://openrouter.ai/api/v1, default model meta-llama/llama-3.3-70b-instruct:free, env VIDSCOPE_OPENROUTER_API_KEY, optional X-Title + HTTP-Referer headers
- openai.py: base_url https://api.openai.com/v1, default model gpt-4o-mini, env VIDSCOPE_OPENAI_API_KEY

Each gets ~10 unit tests via httpx.MockTransport (construction + happy path + 401 fail-fast + 429 retry + missing choices + malformed content). Each registered in analyzer_registry with its own factory.
  - Estimate: 2h
  - Files: src/vidscope/adapters/llm/nvidia_build.py, src/vidscope/adapters/llm/openrouter.py, src/vidscope/adapters/llm/openai.py, src/vidscope/infrastructure/analyzer_registry.py, tests/unit/adapters/llm/test_nvidia_build.py, tests/unit/adapters/llm/test_openrouter.py, tests/unit/adapters/llm/test_openai.py, tests/unit/infrastructure/test_analyzer_registry.py
  - Verify: python -m uv run pytest tests/unit/adapters/llm tests/unit/infrastructure/test_analyzer_registry.py -q && python -m uv run lint-imports
- [x] **T02: Shipped AnthropicAnalyzer using the native /v1/messages format (not the OpenAI-compat layer). All 5 LLM providers now register. 552 tests, 9 contracts, 81 source files mypy strict.** — Anthropic adapter using the native messages API instead of the OpenAI-compat layer. Different request shape (top-level system field, no response_format, max_tokens required) and different response shape (content[0].text instead of choices[0].message.content). Reuses _base.parse_llm_json + _base.make_analysis + _base.call_with_retry as-is. Auth via x-api-key header (Anthropic's native convention) + anthropic-version header. env var VIDSCOPE_ANTHROPIC_API_KEY, default model claude-haiku-4-5. Tests via httpx.MockTransport: construction + happy path + 401 + 429 retry + 529 overload retry + missing content array + malformed JSON in content text. Register in analyzer_registry with factory _build_anthropic.
  - Estimate: 1h30m
  - Files: src/vidscope/adapters/llm/anthropic.py, src/vidscope/infrastructure/analyzer_registry.py, tests/unit/adapters/llm/test_anthropic.py, tests/unit/infrastructure/test_analyzer_registry.py
  - Verify: python -m uv run pytest tests/unit/adapters/llm tests/unit/infrastructure/test_analyzer_registry.py -q && python -m uv run lint-imports && python -m uv run mypy src && python -m uv run ruff check .
