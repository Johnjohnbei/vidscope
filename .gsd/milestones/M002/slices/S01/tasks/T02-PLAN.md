---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: MCP server package with 5 read-only tool handlers

Create src/vidscope/mcp/__init__.py and src/vidscope/mcp/server.py. server.py builds a FastMCP('vidscope') instance and registers 5 tools via @mcp.tool() decorators: vidscope_ingest(url), vidscope_search(query, limit=20), vidscope_get_video(video_id), vidscope_list_videos(limit=20), vidscope_get_status(limit=10). Each tool: (1) calls acquire_container() from cli._support OR builds its own container via build_container (better for test isolation — use build_container directly), (2) instantiates the matching M001 use case, (3) calls execute, (4) converts the typed DTO to a JSON-serializable dict via a _to_dict helper. Typed DomainError is caught and re-raised as a ValueError with a clean message (FastMCP surfaces exceptions to the client). Expose build_mcp_server(container) factory that returns the FastMCP instance — useful for tests that want to inject a test container. A module-level main() function builds the container and calls mcp.run() for stdio transport.

## Inputs

- ``src/vidscope/application/` — existing use cases`
- ``src/vidscope/infrastructure/container.py` — build_container`
- ``src/vidscope/domain/` — DTOs`

## Expected Output

- ``src/vidscope/mcp/server.py` — FastMCP instance with 5 tools + build_mcp_server(container) + main()`
- ``tests/unit/mcp/test_server.py` — tests calling each tool handler directly with a sandboxed container`

## Verification

python -m uv run pytest tests/unit/mcp -q && python -m uv run python -c 'from vidscope.mcp.server import build_mcp_server; from vidscope.infrastructure.container import build_container; import os, tempfile; os.environ["VIDSCOPE_DATA_DIR"] = tempfile.mkdtemp(); from vidscope.infrastructure.config import reset_config_cache; reset_config_cache(); s = build_mcp_server(build_container()); print("server:", s.name)'
