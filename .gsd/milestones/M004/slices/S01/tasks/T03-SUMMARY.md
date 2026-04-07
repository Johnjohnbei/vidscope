---
id: T03
parent: S01
milestone: M004
key_files:
  - src/vidscope/infrastructure/analyzer_registry.py
  - .importlinter
  - tests/unit/infrastructure/test_analyzer_registry.py
  - src/vidscope/adapters/llm/_base.py
  - tests/unit/adapters/llm/test_base.py
key_decisions:
  - Read API key at factory invocation time, not at module import — importing the registry never crashes on a missing key
  - Wrap AnalysisError from constructor in ConfigError at the registry layer — single category of failure for the doctor command
  - Added httpx + mcp to domain/ports forbidden list — guards against future regression
  - New explicit llm-never-imports-other-adapters contract — structurally enforces 'one provider per file' for M004/S02
  - Error message includes console.groq.com signup URL — user can fix the issue without reading docs
duration: 
verification_result: passed
completed_at: 2026-04-07T18:18:35.583Z
blocker_discovered: false
---

# T03: Wired Groq into the analyzer registry, added httpx to pure layers' forbidden list, added llm-isolation contract. All 4 gates clean (ruff, mypy strict on 77 files, 490 pytest, 9 import-linter contracts).

**Wired Groq into the analyzer registry, added httpx to pure layers' forbidden list, added llm-isolation contract. All 4 gates clean (ruff, mypy strict on 77 files, 490 pytest, 9 import-linter contracts).**

## What Happened

**Registry wiring** (`src/vidscope/infrastructure/analyzer_registry.py`):

Added a `_build_groq()` factory function that reads `VIDSCOPE_GROQ_API_KEY` (required) + `VIDSCOPE_GROQ_MODEL` (optional, defaults to `llama-3.1-8b-instant`) from the environment. Wraps the underlying `AnalysisError` from the constructor in a `ConfigError` so the CLI doctor can show a single category of failure. The factory is registered under the name `"groq"` in `_FACTORIES`. The module docstring now lists all 5 future LLM providers (groq + nvidia + openrouter + openai + anthropic) so the next slices have a clear contract.

Important design choice: the API key is read at **factory invocation time**, not at module import time. So `import vidscope.infrastructure.analyzer_registry` never crashes on a missing key — only `build_analyzer("groq")` does, and only when explicitly requested. This means tests that don't touch Groq don't need to set env vars.

**Import-linter contracts updated** (`.importlinter`):

1. **`domain-is-pure`** + **`ports-are-pure`**: added `httpx` and `mcp` to the forbidden modules. This guarantees that nothing in `vidscope.domain` or `vidscope.ports` will ever import an HTTP client or the MCP SDK — those layers must stay pure stdlib + typing.

2. **`llm-never-imports-other-adapters`** (new contract): forbids `vidscope.adapters.llm` from importing any other adapter (sqlite, fs, ytdlp, whisper, ffmpeg, heuristic) or any inner layer (infrastructure, application, pipeline, cli, mcp). This is the structural enforcement of "each LLM provider is isolated to its own file with shared helpers in `_base`". Critical for M004/S02 when 4 more provider files get added.

3. **`pipeline-has-no-adapters`** + **`application-has-no-adapters`** + **`mcp-has-no-adapters`**: added `vidscope.adapters.llm` explicitly to the forbidden lists. The layered contract already implies this (adapters layer is below pipeline/application/mcp), but the explicit forbidden contract gives a much better error message when someone accidentally `import vidscope.adapters.llm.groq` from a use case.

Total contracts: 8 → 9.

**Registry test coverage** (`tests/unit/infrastructure/test_analyzer_registry.py`):

Added a new `TestBuildGroqAnalyzer` class with 6 tests:
- missing API key → `ConfigError("VIDSCOPE_GROQ_API_KEY")`
- whitespace-only API key → `ConfigError`
- valid API key → returns `GroqAnalyzer` instance with `provider_name == "groq"`
- default model when `VIDSCOPE_GROQ_MODEL` unset → no crash
- custom model via env → no crash
- error message includes signup URL `console.groq.com` (helps the user fix it fast)

All 6 use `monkeypatch.setenv`/`delenv` so tests don't pollute the process environment.

Also added one test in `TestKnownAnalyzers` confirming `"groq" in KNOWN_ANALYZERS`.

**Quality gates after T03**:
- ✅ ruff: clean (1 unused import fixed in test_base.py)
- ✅ mypy strict: 77 source files OK (1 backoff helper fixed with explicit float cast)
- ✅ pytest: 490 passed (was 432 before M004, +58 LLM tests = 432 + 34 + 17 + 7 = 490)
- ✅ lint-imports: 9 contracts kept (was 8, added llm-never-imports-other-adapters)

The architecture is now structurally enforced for the remaining 4 providers: any future provider file in `src/vidscope/adapters/llm/` will be automatically subject to the isolation contract — adding nvidia/openrouter/openai/anthropic in S02 requires zero changes to .importlinter.

## Verification

Ran the 4 quality gates in parallel via async_bash. All green: mypy 77 files (after fixing one Any-return in `_backoff_seconds`), ruff clean (after removing one unused import in test_base.py), pytest 490 passed in 6.42s, lint-imports 9 contracts kept.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept, 0 broken | 1500ms |
| 2 | `python -m uv run mypy src` | 0 | ✅ 77 source files OK | 7300ms |
| 3 | `python -m uv run ruff check .` | 0 | ✅ all checks passed | 7300ms |
| 4 | `python -m uv run pytest -q` | 0 | ✅ 490 passed, 5 deselected | 6420ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/analyzer_registry.py`
- `.importlinter`
- `tests/unit/infrastructure/test_analyzer_registry.py`
- `src/vidscope/adapters/llm/_base.py`
- `tests/unit/adapters/llm/test_base.py`
