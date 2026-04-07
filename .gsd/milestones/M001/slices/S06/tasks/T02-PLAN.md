---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: Container wiring for the 5th stage + CLI test extension

Update container.py to append IndexStage to the pipeline runner stages list as the 5th and final stage. Update test_container assertions: stage_names == ('ingest','transcribe','frames','analyze','index'). Update CLI test_after_add to expect 5 pipeline_runs. The CLI test fixture stub_pipeline doesn't need changes — IndexStage uses real DB writes which are already exercised.

## Inputs

- ``src/vidscope/pipeline/stages/index.py``

## Expected Output

- `updated container.py + tests`

## Verification

python -m uv run pytest tests/unit -q
