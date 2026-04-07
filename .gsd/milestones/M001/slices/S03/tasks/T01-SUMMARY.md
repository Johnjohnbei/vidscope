---
id: T01
parent: S03
milestone: M001
key_files:
  - src/vidscope/infrastructure/config.py
  - tests/unit/infrastructure/test_config.py
key_decisions:
  - Validate whisper model name at config build time against a known set — typos fail loud at startup
  - Pattern from S07/T01 reused: env var > default, validation in helper, lazy domain import to avoid circular dependencies
duration: 
verification_result: passed
completed_at: 2026-04-07T15:27:24.621Z
blocker_discovered: false
---

# T01: Added Config.whisper_model with VIDSCOPE_WHISPER_MODEL env var resolution and known-models validation — 4 new tests, 264 total green.

**Added Config.whisper_model with VIDSCOPE_WHISPER_MODEL env var resolution and known-models validation — 4 new tests, 264 total green.**

## What Happened

T01 follows the exact same pattern as S07/T01 (cookies config). New `whisper_model: str` field on Config with default "base", `_resolve_whisper_model()` helper that reads `VIDSCOPE_WHISPER_MODEL` and validates against `_KNOWN_WHISPER_MODELS` frozenset. Unknown values raise `ConfigError` at config build time with the supported list in the message — typos like "tinyy" fail loud at startup, not at the first transcribe call. The known-models set covers tiny/base/small/medium/large variants plus their .en monolingual versions and the distil-* fast variants. ConfigError is imported lazily inside the helper to avoid pulling domain into module-import-time.

## Verification

Ran `python -m uv run pytest tests/unit/infrastructure/test_config.py -q` → 19 passed. Full suite stays at 264 passed (260 + 4 new whisper tests).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/infrastructure/test_config.py -q` | 0 | ✅ pass (19/19) | 310ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/config.py`
- `tests/unit/infrastructure/test_config.py`
