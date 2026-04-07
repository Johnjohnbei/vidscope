---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T05: Integration test: Instagram with cookies (xfail when no cookies, pass when present)

Update tests/integration/test_ingest_live.py::TestLiveInstagram to honor VIDSCOPE_COOKIES_FILE. The test logic: (1) at the start, check if VIDSCOPE_COOKIES_FILE is set AND the file exists. (2) If NOT, xfail the test with reason='cookies not provided — set VIDSCOPE_COOKIES_FILE to enable Instagram tests'. (3) If YES, run the same _assert_successful_ingest path that YouTube and TikTok use — if it fails, that IS a real failure (not an xfail). The conftest fixture sandboxed_container already builds the container fresh so it will pick up VIDSCOPE_COOKIES_FILE. Tests are reordered in the file so Instagram appears FIRST per D027 (priority order Instagram > TikTok > YouTube). Document the manual steps to export Firefox/Chrome cookies in the test docstring so a developer reading the test knows how to enable it.

## Inputs

- ``tests/integration/test_ingest_live.py` — existing test file with the xfail logic`

## Expected Output

- ``tests/integration/test_ingest_live.py` — Instagram test reordered to first, conditional xfail/pass based on VIDSCOPE_COOKIES_FILE env var`

## Verification

python -m uv run pytest tests/integration -m integration -v
