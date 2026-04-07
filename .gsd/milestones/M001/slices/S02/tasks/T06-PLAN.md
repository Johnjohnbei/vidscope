---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T06: Integration tests: real yt-dlp against live public URLs (marked, skipped by default)

Create tests/integration/__init__.py and tests/integration/test_ingest_live.py with three tests marked `@pytest.mark.integration`, each targeting one platform with a known-stable public URL: YouTube (a creative commons sample like `https://www.youtube.com/watch?v=aqz-KE-bpKQ` Big Buck Bunny), TikTok (a public video URL — picked from a top trending page, documented), Instagram (a public Reel — same approach). Each test: builds a real container against a tmp_path data dir via VIDSCOPE_DATA_DIR, invokes `container.pipeline_runner.run(PipelineContext(source_url=url))`, asserts the result is success, asserts a videos row exists with non-empty title + media_key, asserts the media file exists on disk under the MediaStorage root. Mark the tests so they are skipped by default in `pytest tests/unit`; they only run with `pytest -m integration`. The TikTok and Instagram tests should catch any `IngestError` with `retryable=True` and mark the test as xfailed with a clear message (these platforms break upstream yt-dlp periodically; we don't want the suite to fail just because Instagram rotated a key yesterday). Add a top-of-file comment documenting how to run them manually and which URLs they depend on, plus the policy for refreshing URLs when they go 404.

## Inputs

- ``src/vidscope/infrastructure/container.py` — build_container`
- ``src/vidscope/pipeline/runner.py` — PipelineRunner`

## Expected Output

- ``tests/integration/__init__.py` — empty package marker`
- ``tests/integration/conftest.py` — tmp_path fixture that sandboxes VIDSCOPE_DATA_DIR + a container fixture`
- ``tests/integration/test_ingest_live.py` — three platform tests with `@pytest.mark.integration``
- ``pyproject.toml` — testpaths already includes tests/, integration marker already registered in T09 so no change needed — verify`

## Verification

python -m uv run pytest tests/integration -m integration -v
