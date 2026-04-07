---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T05: verify-m001.sh — final milestone-level verification script

Create scripts/verify-m001.sh: the authoritative 'is M001 done' signal. Runs every quality gate, the full unit suite, the live integration suite (with --skip-integration flag), then performs a real end-to-end demo: ingest a YouTube short, list videos, show the video, search for a keyword from the analysis, doctor. Summary message announces M001 readiness for completion or lists the steps that failed.

## Inputs

- ``scripts/verify-s05.sh``

## Expected Output

- ``scripts/verify-m001.sh``

## Verification

bash scripts/verify-m001.sh --skip-integration
