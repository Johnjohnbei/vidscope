---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: 3 use cases: Set/GetStatus/Clear cookies

Create src/vidscope/application/cookies.py with 3 use cases: SetCookiesUseCase(config, validator) -> SetCookiesResult; GetCookiesStatusUseCase(config, validator) -> CookiesStatus; ClearCookiesUseCase(config) -> ClearCookiesResult. Set copies a source path into <data_dir>/cookies.txt after validating. Status reads the configured cookies file and returns path/size/mtime/validation. Clear removes the file (raises if missing or path is not under data_dir for safety). Each use case is a small dataclass with inputs and a typed result. Tests via tmp_path with sandboxed VIDSCOPE_DATA_DIR.

## Inputs

- `src/vidscope/infrastructure/cookies_validator.py`
- `src/vidscope/infrastructure/config.py`

## Expected Output

- `3 use cases + tests`

## Verification

python -m uv run pytest tests/unit/application/test_cookies.py -q
