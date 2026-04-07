---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: StubAnalyzer + analyzer registry to prove the pluggable seam (R010)

Create src/vidscope/adapters/heuristic/stub.py with StubAnalyzer (provider_name='stub'), a minimal second implementation that returns empty/placeholder analysis. The point is to prove the registry pattern, not to ship a useful provider. Add src/vidscope/infrastructure/analyzer_registry.py with build_analyzer(name: str, ...) -> Analyzer that returns the right concrete analyzer instance. Add VIDSCOPE_ANALYZER env var to Config (default 'heuristic'). Container reads config.analyzer_name and calls build_analyzer to get the active analyzer.

## Inputs

- ``src/vidscope/adapters/heuristic/analyzer.py``
- ``src/vidscope/ports/pipeline.py``

## Expected Output

- ``src/vidscope/adapters/heuristic/stub.py` — StubAnalyzer`
- ``src/vidscope/infrastructure/analyzer_registry.py` — build_analyzer + registry`
- ``src/vidscope/infrastructure/config.py` — analyzer_name field + VIDSCOPE_ANALYZER env`
- ``tests/unit/infrastructure/test_analyzer_registry.py``
- ``tests/unit/infrastructure/test_config.py` — analyzer_name tests`

## Verification

python -m uv run pytest tests/unit -q
