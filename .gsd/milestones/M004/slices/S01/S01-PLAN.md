# S01: LLM adapter foundation: shared base + first concrete provider (Groq)

**Goal:** Build the shared LLM helper layer (_base.py) and the first concrete provider (Groq), validating the architecture before scaling to 5 providers.
**Demo:** After this: VIDSCOPE_ANALYZER=groq with a stub HTTP client produces an Analysis row through the existing pipeline.

## Tasks
- [x] **T01: Shipped the shared LLM adapter helpers (_base.py): build_messages, parse_llm_json, call_with_retry, make_analysis. 34 unit tests via httpx.MockTransport, all green.** — Create src/vidscope/adapters/llm/__init__.py + src/vidscope/adapters/llm/_base.py. _base.py contains: (1) build_prompt(transcript) returning a system + user message tuple asking for JSON output with keys keywords/topics/score/summary; (2) parse_llm_json(raw_text) extracting JSON from raw text (handles markdown-fenced JSON, bare JSON, partial truncation); (3) call_with_retry(client, request, max_attempts=3) retry loop with exponential backoff for 429/5xx; (4) AnalysisRecord typed dict that maps from parsed JSON to Analysis fields. Pure helpers, no concrete provider yet.
  - Estimate: 1h30m
  - Files: src/vidscope/adapters/llm/__init__.py, src/vidscope/adapters/llm/_base.py, tests/unit/adapters/llm/__init__.py, tests/unit/adapters/llm/test_base.py
  - Verify: python -m uv run pytest tests/unit/adapters/llm/test_base.py -q
- [x] **T02: Shipped GroqAnalyzer — first concrete LLM provider, 17 unit tests via httpx.MockTransport, all green.** — Create src/vidscope/adapters/llm/groq.py with class GroqAnalyzer implementing the Analyzer protocol. Uses httpx.Client to call Groq's OpenAI-compatible /openai/v1/chat/completions endpoint. Reads model + API key + base_url from constructor. Provider name 'groq'. analyze() builds the prompt, calls _base.call_with_retry, parses the response, returns Analysis. Constructor validates API key is non-empty. Tests via httpx.MockTransport: happy path, 429 retry success, timeout, malformed JSON, missing API key, fatal 401.
  - Estimate: 2h
  - Files: src/vidscope/adapters/llm/groq.py, tests/unit/adapters/llm/test_groq.py
  - Verify: python -m uv run pytest tests/unit/adapters/llm/test_groq.py -q
- [x] **T03: Wired Groq into the analyzer registry, added httpx to pure layers' forbidden list, added llm-isolation contract. All 4 gates clean (ruff, mypy strict on 77 files, 490 pytest, 9 import-linter contracts).** — Update analyzer_registry.py to register 'groq' factory that reads VIDSCOPE_GROQ_API_KEY + VIDSCOPE_GROQ_MODEL (default llama-3.1-8b-instant) from env. Update Config.analyzer_name to honor 'groq'. Add import-linter contract: vidscope.adapters.llm forbidden in domain, ports, pipeline, application, cli, mcp (only infrastructure may import it). Run all 4 quality gates.
  - Estimate: 1h
  - Files: src/vidscope/infrastructure/analyzer_registry.py, src/vidscope/infrastructure/config.py, .importlinter, tests/unit/infrastructure/test_analyzer_registry.py, tests/unit/infrastructure/test_config.py
  - Verify: python -m uv run pytest tests/unit/infrastructure -q && python -m uv run lint-imports
