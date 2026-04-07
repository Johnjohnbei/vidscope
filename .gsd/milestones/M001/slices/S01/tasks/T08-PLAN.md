---
estimated_steps: 1
estimated_files: 12
skills_used: []
---

# T08: CLI as a package: Typer app + one file per command + doctor

Convert the cli entry point into a package src/vidscope/cli/ with app.py exposing the Typer app, commands/__init__.py, and one file per command: add.py, show.py, list.py, search.py, status.py, doctor.py. Each command is a thin wrapper: parse args, build the container via build_container(), instantiate the relevant use case, call use_case.execute(), format the result via rich Tables or Panels, handle typed DomainError by printing a user-actionable message and exiting with code 1, handle unexpected exceptions with exit code 2 and a reference to `vidscope doctor`. The `add` command calls IngestVideoUseCase (writes a PENDING row, returns 'not yet implemented — S02 will wire real ingest'). The `doctor` command runs run_all_checks() and prints a rich Table. The `status` command calls GetStatusUseCase and prints a rich Table of the last N runs (0 rows is valid). `list`, `show`, `search` call their use cases and print empty results gracefully. Update pyproject.toml entry point from `vidscope.cli:app` to `vidscope.cli.app:app`. Add tests/unit/cli/test_app.py using Typer's CliRunner to assert every subcommand returns exit code 0 on a fresh tmp data dir.

## Inputs

- ``src/vidscope/application/ingest_video.py``
- ``src/vidscope/application/get_status.py``
- ``src/vidscope/application/show_video.py``
- ``src/vidscope/application/list_videos.py``
- ``src/vidscope/application/search_library.py``
- ``src/vidscope/infrastructure/container.py``
- ``src/vidscope/infrastructure/startup.py``
- ``src/vidscope/domain/errors.py``

## Expected Output

- ``src/vidscope/cli/app.py` — Typer app + shared error handler`
- ``src/vidscope/cli/commands/add.py` — add command wiring IngestVideoUseCase`
- ``src/vidscope/cli/commands/show.py` — show command wiring ShowVideoUseCase`
- ``src/vidscope/cli/commands/list.py` — list command wiring ListVideosUseCase`
- ``src/vidscope/cli/commands/search.py` — search command wiring SearchLibraryUseCase`
- ``src/vidscope/cli/commands/status.py` — status command wiring GetStatusUseCase`
- ``src/vidscope/cli/commands/doctor.py` — doctor command running run_all_checks()`
- ``pyproject.toml` — updated entry point`
- ``tests/unit/cli/test_app.py` — CliRunner assertions for every subcommand`

## Verification

python -m uv run pytest tests/unit/cli -q && python -m uv run vidscope --help && python -m uv run vidscope status && python -m uv run vidscope doctor && python -m uv run vidscope add 'https://example.com/fake' && python -m uv run vidscope status
