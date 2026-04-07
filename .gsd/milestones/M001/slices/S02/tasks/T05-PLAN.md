---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T05: CLI add command: display real ingest result

Update src/vidscope/cli/commands/add.py to render the enriched IngestResult. On RunStatus.OK: rich Panel with video_id, platform, title, author, duration, media_key, URL, and a green success header. On RunStatus.SKIPPED: same Panel with a yellow 'already ingested' header and the existing video fields. On RunStatus.FAILED: fail_user with the error message. On any other status: fail_system with the raw status.value. Update the existing T08 CliRunner tests in tests/unit/cli/test_app.py to match the new output format — the PENDING placeholder is gone, so the 'after add shows one run' test must expect either OK (if the use case is wired with a fake PipelineRunner that returns OK) or the real ingest path (which would need network, out of scope for unit tests). Strategy: inject a fake PipelineRunner into the use case via a temporary monkeypatch at the container level in the CLI test fixture. Add a new test that verifies the fail path when the use case returns FAILED.

## Inputs

- ``src/vidscope/application/ingest_video.py` — enriched IngestResult from T04`

## Expected Output

- ``src/vidscope/cli/commands/add.py` — updated to render OK/SKIPPED/FAILED with rich formatting`
- ``tests/unit/cli/test_app.py` — updated CLI tests covering OK, SKIPPED, FAILED paths with fake PipelineRunner`

## Verification

python -m uv run pytest tests/unit/cli -q
