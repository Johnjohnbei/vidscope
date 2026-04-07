---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: Install mcp SDK + validate import

Run `python -m uv add mcp` to add the Model Context Protocol Python SDK as a runtime dependency. Verify it imports cleanly with `python -c 'from mcp.server.fastmcp import FastMCP; print(FastMCP)'`. Update pyproject.toml specifier to a compatible-release range. Add `mcp` to mypy's ignore_missing_imports override (mcp SDK may not ship with complete type stubs). Run pytest to confirm no regression.

## Inputs

- ``pyproject.toml` — existing runtime dependencies`

## Expected Output

- ``pyproject.toml` with mcp added to dependencies`
- ``uv.lock` updated`

## Verification

python -m uv run python -c 'from mcp.server.fastmcp import FastMCP; print("ok")' && python -m uv run pytest -q
