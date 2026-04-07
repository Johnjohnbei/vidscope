---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: vidscope watch CLI sub-application

Create src/vidscope/cli/commands/watch.py with a Typer sub-application exposing: `vidscope watch add <url>`, `vidscope watch list`, `vidscope watch remove <handle> [--platform]`, `vidscope watch refresh`. Each command instantiates the matching use case via the container. Add command parses the URL, calls AddWatchedAccountUseCase, prints confirmation. List command renders a rich Table with handle/platform/url/last_checked. Remove takes a handle (and optional --platform if ambiguous) and calls the use case. Refresh prints a summary at the end (accounts checked, new videos, errors). Register on the root app via add_typer. CliRunner tests for each command.

## Inputs

- ``src/vidscope/application/watchlist.py``

## Expected Output

- ``src/vidscope/cli/commands/watch.py``
- `Updated app.py + tests`

## Verification

python -m uv run pytest tests/unit/cli -q && python -m uv run vidscope watch --help
