---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T04: Container wiring + integration test extension + verify-s05.sh

Update container.py: instantiate analyzer via build_analyzer(config.analyzer_name), construct AnalyzeStage, append to runner stages. Update test_container assertions: stage_names == ('ingest','transcribe','frames','analyze'), Container.analyzer is wired. Update CLI test for 4 pipeline_runs. Update integration test helper to assert analyses row exists after run with matching provider. Create scripts/verify-s05.sh.

## Inputs

- ``src/vidscope/pipeline/stages/analyze.py``
- ``src/vidscope/infrastructure/analyzer_registry.py``

## Expected Output

- ``src/vidscope/infrastructure/container.py``
- ``tests/unit/infrastructure/test_container.py``
- ``tests/unit/cli/test_app.py``
- ``tests/integration/test_ingest_live.py``
- ``scripts/verify-s05.sh``

## Verification

bash scripts/verify-s05.sh --skip-integration && python -m uv run pytest -q
