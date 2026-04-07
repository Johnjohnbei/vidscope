---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T06: verify-s03.sh end-to-end script

Create scripts/verify-s03.sh following the pattern of verify-s02.sh and verify-s07.sh. Include: uv sync, 4 quality gates, vidscope --help, vidscope doctor, unsupported URL exit 1, sandboxed integration test (TikTok + YouTube, conditional Instagram), and a real ingest+transcribe round-trip in the script's sandboxed data dir. Support --skip-integration. Note: the first run with integration triggers a faster-whisper model download — the script prints a warning before that step.

## Inputs

- ``scripts/verify-s07.sh` — template`

## Expected Output

- ``scripts/verify-s03.sh``

## Verification

bash scripts/verify-s03.sh --skip-integration
