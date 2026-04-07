---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T03: CLI mcp serve subcommand + doctor mcp check

Create src/vidscope/cli/commands/mcp.py with an `mcp_app` Typer sub-application and a `serve` command that calls vidscope.mcp.server.main(). Register the sub-application on the main app in src/vidscope/cli/app.py via `app.add_typer(mcp_app, name='mcp')`. Extend src/vidscope/infrastructure/startup.py with check_mcp_sdk() returning a CheckResult with three states (ok+importable / ok+not-importable-but-optional? — no, mcp is a runtime dep now, so just ok or fail). Add check_mcp_sdk() to run_all_checks(). Update tests/unit/infrastructure/test_startup.py accordingly. Manual smoke: `vidscope mcp --help` shows the serve subcommand.

## Inputs

- ``src/vidscope/mcp/server.py``
- ``src/vidscope/cli/app.py``

## Expected Output

- ``src/vidscope/cli/commands/mcp.py` with mcp_app + serve command`
- ``src/vidscope/cli/app.py` with mcp sub-app registered`
- ``src/vidscope/infrastructure/startup.py` with check_mcp_sdk()`
- `Updated tests`

## Verification

python -m uv run pytest tests/unit -q && python -m uv run vidscope mcp --help && python -m uv run vidscope doctor
