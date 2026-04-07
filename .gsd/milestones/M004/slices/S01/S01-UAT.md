# S01: LLM adapter foundation: shared base + first concrete provider (Groq) — UAT

**Milestone:** M004
**Written:** 2026-04-07T18:19:48.061Z

## UAT — M004/S01: LLM adapter foundation + Groq

### Manual smoke test (no API key required)

```bash
# Verify the registry exposes the new groq name
python -m uv run python -c "from vidscope.infrastructure.analyzer_registry import KNOWN_ANALYZERS; print(sorted(KNOWN_ANALYZERS))"
# Expected: ['groq', 'heuristic', 'stub']

# Verify trying to use groq without an API key fails cleanly
python -m uv run python -c "from vidscope.infrastructure.analyzer_registry import build_analyzer; build_analyzer('groq')"
# Expected: ConfigError mentioning VIDSCOPE_GROQ_API_KEY and console.groq.com
```

### Live smoke test (requires real API key, optional)

```bash
# 1. Get a free key at https://console.groq.com (no credit card)
# 2. Export it
export VIDSCOPE_GROQ_API_KEY=gsk_...
export VIDSCOPE_ANALYZER=groq

# 3. Ingest a short video
vidscope add https://www.youtube.com/shorts/<some-short>

# 4. Show the result
vidscope show <video-id>
# Expected: analysis row with provider='groq' instead of 'heuristic'
```

### Quality gates

- [x] ruff clean
- [x] mypy strict on 77 source files
- [x] pytest 490 passed
- [x] lint-imports 9 contracts kept
- [x] No live network calls in unit tests (all via httpx.MockTransport)

