---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: `vidscope_suggest_related` MCP tool + unit test + subprocess round-trip

Extend src/vidscope/mcp/server.py to register a 6th tool `vidscope_suggest_related(video_id, limit=5)` that wraps SuggestRelatedUseCase and converts the DTO to a JSON-serializable dict. Update unit tests in tests/unit/mcp/test_server.py to expect 6 tools and add tests for the new tool (empty library → empty suggestions, seeded library with overlapping videos → ranked results). Update the subprocess integration test in tests/integration/test_mcp_server.py to expect 6 tool names.

## Inputs

- ``src/vidscope/application/suggest_related.py``
- ``src/vidscope/mcp/server.py``

## Expected Output

- `Updated server.py with 6th tool`
- `Updated tests`

## Verification

python -m uv run pytest tests/unit/mcp -q && python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v
