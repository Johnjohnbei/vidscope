---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T04: Live integration test extension + verify-s04.sh

Extend tests/integration/test_ingest_live.py helper to assert frames rows exist after the run (skip gracefully if ffmpeg is not on PATH — the FramesStage will raise FrameExtractionError, the runner will mark it FAILED, and the helper will detect that). Actually: better approach — if ffmpeg is missing, the integration test should skip via pytest.importorskip-style check, NOT propagate as a real failure. Add a `_ffmpeg_available()` helper that uses shutil.which. If ffmpeg is missing, the frame assertions are skipped but ingest+transcribe assertions still run. Create scripts/verify-s04.sh following the established pattern.

## Inputs

- ``tests/integration/test_ingest_live.py``
- ``scripts/verify-s03.sh``

## Expected Output

- ``tests/integration/test_ingest_live.py` — frame assertions guarded by ffmpeg availability check`
- ``scripts/verify-s04.sh``

## Verification

bash scripts/verify-s04.sh --skip-integration
