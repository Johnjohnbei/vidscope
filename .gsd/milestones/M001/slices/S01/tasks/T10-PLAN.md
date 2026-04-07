---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T10: End-to-end socle verification script on the layered architecture

Prove the full socle works from clean state: (1) nuke the data_dir; (2) `uv sync`; (3) `uv run vidscope --help` lists all six commands; (4) `uv run vidscope status` returns empty report exit 0 and creates the DB + all five tables + FTS5 virtual table; (5) verify table existence via a tiny Python snippet; (6) `uv run vidscope doctor` runs checks; (7) `uv run vidscope add 'https://example.com/fake'` writes a PENDING pipeline_runs row; (8) `uv run vidscope status` now shows exactly 1 row; (9) `uv run pytest -q` fully green; (10) `uv run ruff check src tests`, `uv run mypy src`, `uv run lint-imports` all clean. Package everything in scripts/verify-s01.sh (bash, portable — uses `python -m uv run` so it works on Windows git-bash, macOS, Linux). Script exits non-zero on any failed step and prints pass/fail summary.

## Inputs

- ``src/vidscope/cli/app.py``
- ``src/vidscope/adapters/sqlite/schema.py``
- ``src/vidscope/infrastructure/startup.py``
- ``pyproject.toml``
- ``.importlinter``

## Expected Output

- ``scripts/verify-s01.sh` — portable verification script exercising install, CLI dispatch, DB creation, layered tests, and all quality gates`

## Verification

bash scripts/verify-s01.sh
