---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T07: verify-s07.sh: end-to-end S07 verification with optional Instagram live test

Create scripts/verify-s07.sh following the same pattern as verify-s01/verify-s02. Steps: uv sync, ruff check, mypy strict, lint-imports, pytest unit suite, vidscope --help, vidscope doctor (must include the new cookies check), vidscope add unsupported URL exits 1, vidscope add empty URL exits 1, then conditional integration block: if VIDSCOPE_COOKIES_FILE is set and the file exists, run the integration suite including Instagram and expect ALL THREE platforms to pass; if not, run integration with the existing xfail expectation for Instagram. Final summary message reflects whether Instagram was validated or not. The script supports --skip-integration like verify-s02.sh.

## Inputs

- ``scripts/verify-s02.sh` — template`
- ``tests/integration/test_ingest_live.py` — the integration tests this script runs`

## Expected Output

- ``scripts/verify-s07.sh` — portable verification script with cookie-aware integration block`

## Verification

bash scripts/verify-s07.sh --skip-integration
