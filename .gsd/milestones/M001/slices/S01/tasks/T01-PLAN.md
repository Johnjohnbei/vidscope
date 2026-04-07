---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: Installed uv toolchain, pinned Python 3.13, declared runtime + dev deps with compatible-release specifiers, and committed uv.lock.

uv is not installed on the dev machine — this is the first blocker. Install uv via the official standalone installer (no Python dependency), initialize the project's .venv via `uv sync`, then declare the concrete runtime and dev dependencies in pyproject.toml. Runtime: typer, sqlalchemy, yt-dlp (Python lib), faster-whisper, rich (for typed CLI output). Dev: pytest, pytest-cov, ruff, mypy. Do NOT pin exact versions — use compatible-release specifiers (>=X.Y,<X+1). Generate and commit the uv.lock. Verify `uv sync` is idempotent and `uv run python -c 'import typer, sqlalchemy, yt_dlp, faster_whisper'` succeeds.

## Inputs

- ``pyproject.toml` — existing skeleton from bootstrap commit`

## Expected Output

- ``pyproject.toml` — with filled [project.dependencies] and [project.optional-dependencies.dev]`
- ``uv.lock` — committed lockfile produced by uv sync`
- ``.python-version` — pins Python minor version for reproducibility`

## Verification

uv --version && uv sync && uv run python -c "import typer, sqlalchemy, yt_dlp, faster_whisper; print('ok')"
