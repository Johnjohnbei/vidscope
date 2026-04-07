---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T05: Subprocess integration test: spawn MCP server + JSON-RPC tools/list round-trip

Create tests/integration/test_mcp_server.py with a @pytest.mark.integration test that spawns `python -m uv run vidscope mcp serve` as a subprocess (or directly `python -c 'from vidscope.mcp.server import main; main()'`) via asyncio.subprocess, uses the mcp ClientSession + stdio_client to connect, calls session.list_tools(), and asserts the returned tool list contains the 5 expected tool names. This is the proof that the server actually responds to JSON-RPC over stdio. Sandbox VIDSCOPE_DATA_DIR via a tmp_path fixture so the subprocess has a clean DB.

## Inputs

- ``src/vidscope/mcp/server.py``

## Expected Output

- ``tests/integration/test_mcp_server.py` with a subprocess round-trip test`

## Verification

python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v
