---
id: T02
parent: S05
milestone: M001
key_files:
  - src/vidscope/infrastructure/analyzer_registry.py
  - src/vidscope/infrastructure/config.py
  - tests/unit/infrastructure/test_analyzer_registry.py
  - tests/unit/infrastructure/test_config.py
key_decisions:
  - Registry is a frozen dict of name → factory callable. Adding providers in M004 = adding entries to _FACTORIES, no caller changes.
  - Config returns the analyzer name string. Validation against the registry lives in build_analyzer, not Config. Same separation as cookies (Config returns path, downloader validates).
  - build_analyzer returns a fresh instance per call. Stateless analyzers don't care; future stateful ones (LLM clients with sessions) will need their own caching.
duration: 
verification_result: passed
completed_at: 2026-04-07T15:56:45.555Z
blocker_discovered: false
---

# T02: Shipped analyzer registry + Config.analyzer_name + VIDSCOPE_ANALYZER env var. Pluggable seam (R010) proven by registering both HeuristicAnalyzer and StubAnalyzer.

**Shipped analyzer registry + Config.analyzer_name + VIDSCOPE_ANALYZER env var. Pluggable seam (R010) proven by registering both HeuristicAnalyzer and StubAnalyzer.**

## What Happened

Analyzer registry is a single-function factory: `build_analyzer(name) -> Analyzer` looks up the name in a frozen `_FACTORIES` dict and returns a fresh instance, or raises ConfigError with the registered providers list if the name is unknown. Two providers registered today: 'heuristic' and 'stub'. M004 will add LLM-backed providers by extending `_FACTORIES` — the container's wiring code never changes.

Config grew a 4th env-resolved field: `analyzer_name: str` (default 'heuristic'), resolved from `VIDSCOPE_ANALYZER`. Validation against the registry happens in `build_analyzer`, not in Config — same separation pattern as cookies (Config returns the path, downloader validates it).

13 new tests across 2 files: registry happy path for both providers, unknown name raises ConfigError, error message lists registered providers, fresh instances per call, KNOWN_ANALYZERS is a frozenset, default analyzer is heuristic, env var override, empty env var falls back to default.

## Verification

Ran `python -m uv run pytest tests/unit/infrastructure tests/unit/adapters/heuristic -q` → 69 passed in 500ms.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/infrastructure tests/unit/adapters/heuristic -q` | 0 | ✅ pass (69/69) | 500ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/analyzer_registry.py`
- `src/vidscope/infrastructure/config.py`
- `tests/unit/infrastructure/test_analyzer_registry.py`
- `tests/unit/infrastructure/test_config.py`
