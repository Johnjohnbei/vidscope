---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T04: import-linter mcp layer contract

Extend .importlinter with a new forbidden contract: `vidscope.mcp` must NOT import `vidscope.adapters` directly. It CAN import `vidscope.application`, `vidscope.infrastructure.container`, `vidscope.domain`. This enforces that the MCP interface layer is as clean as the CLI interface layer. Update the architecture test in tests/architecture/test_layering.py to include the new contract name in the expected list. Also add `mcp` as a layer in the main layers contract between cli and application (both cli and mcp are interface layers that consume application).

## Inputs

- `.importlinter`

## Expected Output

- ``.importlinter` with new mcp-has-no-adapters contract and mcp in layers list`
- ``tests/architecture/test_layering.py` with updated expected contract names`

## Verification

python -m uv run lint-imports && python -m uv run pytest tests/architecture -q
