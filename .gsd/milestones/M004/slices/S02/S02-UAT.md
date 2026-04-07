# S02: Remaining 4 LLM providers (NVIDIA Build, OpenRouter, OpenAI, Anthropic) — UAT

**Milestone:** M004
**Written:** 2026-04-07T18:28:58.604Z

## UAT — M004/S02: 4 remaining LLM providers

### Manual smoke test (no API keys required)

```bash
# Confirm all 5 LLM providers + 2 defaults register
python -m uv run python -c "from vidscope.infrastructure.analyzer_registry import KNOWN_ANALYZERS; print(sorted(KNOWN_ANALYZERS))"
# Expected: ['anthropic', 'groq', 'heuristic', 'nvidia', 'openai', 'openrouter', 'stub']

# Confirm each provider fails cleanly without its API key
for p in groq nvidia openrouter openai anthropic; do
  python -m uv run python -c "from vidscope.infrastructure.analyzer_registry import build_analyzer; build_analyzer('$p')" 2>&1 | grep -i "VIDSCOPE_"
done
# Expected: 5 ConfigError lines mentioning the corresponding env var name + signup URL
```

### Live smoke test (requires real API key — pick whichever you have)

```bash
# Example with Groq (free tier, no credit card)
export VIDSCOPE_GROQ_API_KEY=gsk_...
export VIDSCOPE_ANALYZER=groq
vidscope add https://www.youtube.com/shorts/<some-short>
vidscope show <video-id>
# Expected: analysis row with provider='groq', score 0-100, summary <= 200 chars

# Replace with anthropic / nvidia / openrouter / openai as desired
```

### Quality gates

- [x] ruff clean
- [x] mypy strict on 81 source files
- [x] pytest 552 passed (was 432 + 120 new LLM tests)
- [x] lint-imports 9 contracts kept (including llm-never-imports-other-adapters)
- [x] No live network calls in unit tests (all via httpx.MockTransport)

