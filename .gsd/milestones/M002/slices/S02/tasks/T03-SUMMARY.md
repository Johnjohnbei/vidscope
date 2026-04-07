---
id: T03
parent: S02
milestone: M002
key_files:
  - src/vidscope/mcp/server.py
  - tests/unit/mcp/test_server.py
  - tests/integration/test_mcp_server.py
key_decisions:
  - 6th tool slots into the existing build_mcp_server factory without any structural change — the pattern is proven
  - DTO conversion preserves every field on SuggestRelatedResult so an MCP client has the same data as the CLI user
  - Unit test seeds 3 videos with overlapping analyses directly via the repository layer — no stubbing of the pipeline runner, the test exercises the full DB path
duration: 
verification_result: passed
completed_at: 2026-04-07T17:27:10.522Z
blocker_discovered: false
---

# T03: Registered `vidscope_suggest_related` as the 6th MCP tool + updated unit and subprocess tests. Server now exposes 6 tools, 17 MCP unit tests green, 2 subprocess integration tests green, 370 total unit tests green.

**Registered `vidscope_suggest_related` as the 6th MCP tool + updated unit and subprocess tests. Server now exposes 6 tools, 17 MCP unit tests green, 2 subprocess integration tests green, 370 total unit tests green.**

## What Happened

Extended `vidscope.mcp.server.build_mcp_server` with a 6th `@mcp.tool()` decorator registering `vidscope_suggest_related(video_id, limit=5)`. The tool wraps SuggestRelatedUseCase from T01, catches DomainError, and converts the result DTO to a JSON-serializable dict preserving every field: source_video_id, source_found, source_title, source_keywords list, reason, and a suggestions list with video_id, title, platform, score, matched_keywords per entry.

Updated `tests/unit/mcp/test_server.py`:
- `test_server_registers_five_tools` renamed to `test_server_registers_six_tools` with the expected set extended
- New `TestVidscopeSuggestRelated` class with 3 tests:
  - Empty library returns `source_found=False` with "no video with id X" reason
  - Populated library (3 seeded videos with overlapping keywords) returns ranked suggestions; matching video is in results, unrelated is not, matched_keywords is the intersection, score is Jaccard 2/4 = 0.5
  - Limit parameter respected (limit=1 returns at most 1 suggestion)
- Added `_seed_related_library` helper that creates 3 videos with analyses: source (python/cooking/recipe), matching (python/recipe/food — 2/4 overlap), unrelated (gardening/plants — 0 overlap)

Updated `tests/integration/test_mcp_server.py` subprocess test expected set to include `vidscope_suggest_related`.

**Quality gates after T03:**
- 370 unit tests passed (up from 353)
- 5 deselected integration tests (3 live ingest + 2 MCP subprocess)
- ruff clean (1 auto-fix for unused-variable in a tuple unpack, 1 manual fix using `_matching_id` underscore prefix)
- mypy strict clean on 70 source files
- import-linter 8 contracts kept

**S02 is complete after T03**: SuggestRelatedUseCase (T01), CLI command (T02), MCP tool (T03). The suggestion engine is exposed via both interfaces (CLI and MCP) with identical results, which is exactly the point of the hexagonal architecture — one use case, multiple interface wrappers.

## Verification

Ran `python -m uv run pytest tests/unit/mcp -q` → 17 passed in 950ms. Ran `python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v` → 2 passed in 1.79s including the updated 6-tool-names assertion. Ran full suite → 370 passed, 5 deselected. Ruff/mypy/lint-imports all clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/mcp -q` | 0 | ✅ 17/17 MCP unit tests green including 3 new suggest_related tests | 950ms |
| 2 | `python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v` | 0 | ✅ 2/2 subprocess tests green with 6-tool-names assertion | 1790ms |
| 3 | `python -m uv run pytest -q` | 0 | ✅ 370 passed, 5 deselected | 3550ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/mcp/server.py`
- `tests/unit/mcp/test_server.py`
- `tests/integration/test_mcp_server.py`
