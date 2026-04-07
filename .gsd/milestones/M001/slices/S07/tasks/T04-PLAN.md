---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T04: CLI doctor: third check for cookies file presence

Add a check_cookies() function to src/vidscope/infrastructure/startup.py that returns a CheckResult with name='cookies' and three possible states: (1) ok=True, version_or_error='configured at {path}', remediation='' — when VIDSCOPE_COOKIES_FILE is set and the file exists; (2) ok=True, version_or_error='not configured (optional)', remediation='To ingest Instagram or other gated content, see docs/cookies.md' — when no cookies are configured; (3) ok=False, version_or_error='configured at {path} but file is missing', remediation='Check VIDSCOPE_COOKIES_FILE points to a real file' — when env var is set but file does not exist. Important nuance: 'not configured' is OK because cookies are optional — only the third state (configured but missing) is a real failure. run_all_checks() now includes check_cookies(). The doctor command picks it up automatically. Tests cover all three states via monkeypatching VIDSCOPE_COOKIES_FILE.

## Inputs

- ``src/vidscope/infrastructure/startup.py``
- ``src/vidscope/infrastructure/config.py``

## Expected Output

- ``src/vidscope/infrastructure/startup.py` — check_cookies() + run_all_checks() includes it`
- ``tests/unit/infrastructure/test_startup.py` — 3 new tests for the three cookie states`

## Verification

python -m uv run pytest tests/unit/infrastructure/test_startup.py -q && python -m uv run vidscope doctor
