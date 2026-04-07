---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: AnthropicAnalyzer (native /v1/messages format)

Anthropic adapter using the native messages API instead of the OpenAI-compat layer. Different request shape (top-level system field, no response_format, max_tokens required) and different response shape (content[0].text instead of choices[0].message.content). Reuses _base.parse_llm_json + _base.make_analysis + _base.call_with_retry as-is. Auth via x-api-key header (Anthropic's native convention) + anthropic-version header. env var VIDSCOPE_ANTHROPIC_API_KEY, default model claude-haiku-4-5. Tests via httpx.MockTransport: construction + happy path + 401 + 429 retry + 529 overload retry + missing content array + malformed JSON in content text. Register in analyzer_registry with factory _build_anthropic.

## Inputs

- `src/vidscope/adapters/llm/_base.py`
- `src/vidscope/adapters/llm/groq.py`

## Expected Output

- `anthropic.py + tests + registry factory`

## Verification

python -m uv run pytest tests/unit/adapters/llm tests/unit/infrastructure/test_analyzer_registry.py -q && python -m uv run lint-imports && python -m uv run mypy src && python -m uv run ruff check .
