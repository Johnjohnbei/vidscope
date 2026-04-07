---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: GroqAnalyzer concrete adapter

Create src/vidscope/adapters/llm/groq.py with class GroqAnalyzer implementing the Analyzer protocol. Uses httpx.Client to call Groq's OpenAI-compatible /openai/v1/chat/completions endpoint. Reads model + API key + base_url from constructor. Provider name 'groq'. analyze() builds the prompt, calls _base.call_with_retry, parses the response, returns Analysis. Constructor validates API key is non-empty. Tests via httpx.MockTransport: happy path, 429 retry success, timeout, malformed JSON, missing API key, fatal 401.

## Inputs

- `src/vidscope/adapters/llm/_base.py`

## Expected Output

- `groq.py + 10+ tests`

## Verification

python -m uv run pytest tests/unit/adapters/llm/test_groq.py -q
