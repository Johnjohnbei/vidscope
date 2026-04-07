---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T03: vidscope cookies CLI sub-application + register in app.py

Create src/vidscope/cli/commands/cookies.py with a Typer sub-application exposing 3 commands: set <source-path>, status, clear [--yes]. set and clear print success/failure with rich formatting. status prints a small table with path/size/mtime/valid. Register cookies_app via add_typer in src/vidscope/cli/app.py. Tests via Typer's CliRunner.

## Inputs

- `src/vidscope/application/cookies.py`

## Expected Output

- `cookies sub-application + CLI tests + app.py registration + 4 quality gates clean`

## Verification

python -m uv run pytest tests/unit/cli/test_cookies.py tests/unit/cli/test_app.py -q && python -m uv run mypy src && python -m uv run lint-imports && python -m uv run ruff check .
