---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Shared LLM base: prompt + JSON parser + retry helper

Create src/vidscope/adapters/llm/__init__.py + src/vidscope/adapters/llm/_base.py. _base.py contains: (1) build_prompt(transcript) returning a system + user message tuple asking for JSON output with keys keywords/topics/score/summary; (2) parse_llm_json(raw_text) extracting JSON from raw text (handles markdown-fenced JSON, bare JSON, partial truncation); (3) call_with_retry(client, request, max_attempts=3) retry loop with exponential backoff for 429/5xx; (4) AnalysisRecord typed dict that maps from parsed JSON to Analysis fields. Pure helpers, no concrete provider yet.

## Inputs

- `src/vidscope/adapters/heuristic/analyzer.py`
- `src/vidscope/ports/pipeline.py`

## Expected Output

- `_base.py + tests`

## Verification

python -m uv run pytest tests/unit/adapters/llm/test_base.py -q
