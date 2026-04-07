---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: Wire Groq into analyzer_registry + container + import-linter contract

Update analyzer_registry.py to register 'groq' factory that reads VIDSCOPE_GROQ_API_KEY + VIDSCOPE_GROQ_MODEL (default llama-3.1-8b-instant) from env. Update Config.analyzer_name to honor 'groq'. Add import-linter contract: vidscope.adapters.llm forbidden in domain, ports, pipeline, application, cli, mcp (only infrastructure may import it). Run all 4 quality gates.

## Inputs

- `src/vidscope/adapters/llm/groq.py`

## Expected Output

- `registry update + contract + tests`

## Verification

python -m uv run pytest tests/unit/infrastructure -q && python -m uv run lint-imports
