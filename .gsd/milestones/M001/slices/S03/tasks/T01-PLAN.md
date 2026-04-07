---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: Config: VIDSCOPE_WHISPER_MODEL env var + Config.whisper_model field

Extend src/vidscope/infrastructure/config.py with whisper_model: str field on Config (default 'base'). Resolution: VIDSCOPE_WHISPER_MODEL env var if set, otherwise 'base'. Validation: only accept known faster-whisper model names ('tiny', 'tiny.en', 'base', 'base.en', 'small', 'small.en', 'medium', 'medium.en', 'large-v3', 'distil-large-v3'). Reject unknown values with ConfigError. Tests cover: default value, env var override, invalid value rejection.

## Inputs

- ``src/vidscope/infrastructure/config.py``

## Expected Output

- ``src/vidscope/infrastructure/config.py` — Config.whisper_model field + _ENV_WHISPER_MODEL constant + validation`
- ``tests/unit/infrastructure/test_config.py` — 4 new tests in TestWhisperModelConfig`

## Verification

python -m uv run pytest tests/unit/infrastructure/test_config.py -q
