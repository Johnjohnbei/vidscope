---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T07: verify-s02.sh: end-to-end ingest verification script

Create scripts/verify-s02.sh following the same pattern as scripts/verify-s01.sh: sandboxed tmp data dir, step-tracked output with colors, sum up failed steps at the end. Steps: (1) uv sync, (2) ruff check, (3) mypy strict, (4) lint-imports, (5) pytest -q (unit tests, fast), (6) vidscope --help still works, (7) vidscope doctor still runs (tolerate exit 2 if ffmpeg missing, yt-dlp must be OK), (8) pytest -m integration -v (the live ingest tests on all three platforms — this is the step that actually exercises R001 against reality), (9) after integration: verify via inline Python that the sandboxed DB contains at least one videos row per platform that succeeded, (10) vidscope status shows the integration runs. Tolerate Instagram integration test failing with a clear message (R001 note: Instagram is the most fragile brick). The script has a --skip-integration flag for fast iteration that skips step 8.

## Inputs

- ``scripts/verify-s01.sh` — template to follow`
- ``tests/integration/test_ingest_live.py` — the tests this script runs`

## Expected Output

- ``scripts/verify-s02.sh` — portable bash verification script exercising install + gates + unit tests + live ingest on three platforms + DB verification`

## Verification

bash scripts/verify-s02.sh --skip-integration
