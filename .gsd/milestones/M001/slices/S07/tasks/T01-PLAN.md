---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: Config: VIDSCOPE_COOKIES_FILE env var + Config.cookies_file field

Extend src/vidscope/infrastructure/config.py with a new optional field `cookies_file: Path | None` on the frozen Config dataclass. Resolution rules: (1) if VIDSCOPE_COOKIES_FILE env var is set, use it (expanded + resolved to absolute path). (2) Otherwise, check if `<data_dir>/cookies.txt` exists — use it if yes. (3) Otherwise, set to None. The field is None by default which preserves the existing public-content workflow. Add a module-level constant _ENV_COOKIES_FILE = 'VIDSCOPE_COOKIES_FILE'. Update _build_config() to compute cookies_file. Tests in tests/unit/infrastructure/test_config.py: env var override resolution, default-from-data-dir resolution when file exists, None when neither, env var precedence over default.

## Inputs

- ``src/vidscope/infrastructure/config.py` — existing Config dataclass and _build_config function`

## Expected Output

- ``src/vidscope/infrastructure/config.py` — Config gains cookies_file field, _build_config resolves it from env or data_dir default`
- ``tests/unit/infrastructure/test_config.py` — 4 new tests covering all resolution paths`

## Verification

python -m uv run pytest tests/unit/infrastructure/test_config.py -q && python -m uv run python -c "import os, tempfile; tmp=tempfile.mkdtemp(); os.environ['VIDSCOPE_DATA_DIR']=tmp; from vidscope.infrastructure.config import reset_config_cache, get_config; reset_config_cache(); c=get_config(); assert c.cookies_file is None; print('ok')"
