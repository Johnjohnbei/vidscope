---
estimated_steps: 5
estimated_files: 8
skills_used: []
---

# T01: NvidiaBuildAnalyzer + OpenRouterAnalyzer + OpenAIAnalyzer (OpenAI-compatible providers)

Three OpenAI-compatible providers in one task because they share 95% of the code with GroqAnalyzer:
- nvidia_build.py: base_url https://integrate.api.nvidia.com/v1, default model meta/llama-3.1-8b-instruct, env VIDSCOPE_NVIDIA_API_KEY
- openrouter.py: base_url https://openrouter.ai/api/v1, default model meta-llama/llama-3.3-70b-instruct:free, env VIDSCOPE_OPENROUTER_API_KEY, optional X-Title + HTTP-Referer headers
- openai.py: base_url https://api.openai.com/v1, default model gpt-4o-mini, env VIDSCOPE_OPENAI_API_KEY

Each gets ~10 unit tests via httpx.MockTransport (construction + happy path + 401 fail-fast + 429 retry + missing choices + malformed content). Each registered in analyzer_registry with its own factory.

## Inputs

- `src/vidscope/adapters/llm/groq.py`
- `src/vidscope/adapters/llm/_base.py`

## Expected Output

- `3 adapter files + 3 test files + registry update + ~30 new tests`

## Verification

python -m uv run pytest tests/unit/adapters/llm tests/unit/infrastructure/test_analyzer_registry.py -q && python -m uv run lint-imports
