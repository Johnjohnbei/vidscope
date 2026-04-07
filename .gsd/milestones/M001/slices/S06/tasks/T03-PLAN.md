---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: End-to-end live integration test for the full 5-stage pipeline + search hit

Extend tests/integration/test_ingest_live.py helper with a final assertion: after the run, call container.search_library use case (or directly query uow.search_index.search) with a likely keyword from the analysis and assert at least one result is returned. This proves the FTS5 indexing actually works end-to-end. The keyword can be derived from the persisted analysis.keywords[0] when non-empty, or skipped for instrumental videos. Also verify the CLI side: instantiate the SearchLibraryUseCase against the same DB and assert it returns the same results.

## Inputs

- ``tests/integration/test_ingest_live.py``

## Expected Output

- `updated test helper with FTS5 hit assertion`

## Verification

python -m uv run pytest tests/integration -m 'integration and slow' -v
