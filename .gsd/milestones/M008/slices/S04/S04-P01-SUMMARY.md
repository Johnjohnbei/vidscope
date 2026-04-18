---
phase: M008/S04
plan: P01
subsystem: application-cli-mcp-surface
tags: [ocr, vision, frame-texts, show-video, search-library, mcp, cli, fts5]
dependency_graph:
  requires:
    - vidscope.domain.entities.FrameText (S01-P01)
    - vidscope.ports.repositories.FrameTextRepository (S01-P01)
    - vidscope.ports.unit_of_work.UnitOfWork.frame_texts (S01-P01)
    - vidscope.domain.entities.Video.thumbnail_key + content_shape (S03-P01)
    - vidscope.pipeline.stages.VisualIntelligenceStage (S02-P01, S03-P01)
  provides:
    - ShowVideoResult.frame_texts: tuple[FrameText, ...]
    - ShowVideoResult.thumbnail_key: str | None
    - ShowVideoResult.content_shape: str | None
    - SearchLibraryUseCase.execute(on_screen_text=...) facet
    - vidscope show <id> renders on-screen text + thumbnail + content_shape
    - vidscope search --on-screen-text <query> flag
    - vidscope_get_frame_texts MCP tool
  affects:
    - src/vidscope/application/show_video.py (extended DTO + execute)
    - src/vidscope/application/search_library.py (new facet parameter)
    - src/vidscope/cli/commands/show.py (new rendering sections)
    - src/vidscope/cli/commands/search.py (new CLI option)
    - src/vidscope/mcp/server.py (new tool)
tech_stack:
  added: []
  patterns:
    - Additive DTO extension (safe-empty defaults preserve caller compat)
    - Facet-set intersection pattern (mirrors M007 hashtag/mention/has_link)
    - In-memory frame_id→timestamp_ms JOIN (avoid extra DB query in MCP tool)
    - Rich markup bracket escape (\\[ prefix for facet_str display)
key_files:
  created:
    - tests/unit/mcp/test_frame_texts_tool.py
  modified:
    - src/vidscope/application/show_video.py
    - src/vidscope/application/search_library.py
    - src/vidscope/cli/commands/show.py
    - src/vidscope/cli/commands/search.py
    - src/vidscope/mcp/server.py
    - tests/unit/application/test_show_video.py
    - tests/unit/application/test_search_library.py
    - tests/unit/cli/test_show_cmd.py
    - tests/unit/cli/test_search_cmd.py
    - tests/unit/mcp/test_server.py
decisions:
  - "D-M008-S04-01: Rich markup escape — facet_str uses \\[ prefix to prevent rich from swallowing [on-screen=promo] as a markup tag; discovered during T02 GREEN phase"
  - "D-M008-S04-02: In-memory frame_id→timestamp_ms JOIN in vidscope_get_frame_texts — reuses ShowVideoUseCase.execute (which already fetches frames) to avoid adding a new repo method or a second DB query"
  - "D-M008-S04-03: ft_preview variable name (not preview) in show.py — avoids mypy type assignment conflict with the existing description preview variable of type str in the same function scope"
metrics:
  duration: ~25 minutes
  completed_at: "2026-04-18T14:08:53Z"
  tasks: 3
  files_created: 1
  files_modified: 9
  tests_added: 31
  total_tests: 1064
---

# Phase M008 Slice S04 Plan P01 Summary

**One-liner:** Exposition des signaux M008 dans les surfaces CLI et MCP — ShowVideoResult étendu avec frame_texts+thumbnail_key+content_shape, facette on_screen_text FTS5 dans SearchLibraryUseCase, --on-screen-text CLI flag, et tool MCP vidscope_get_frame_texts avec JOIN timestamp_ms depuis frames.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| T01 | Extend ShowVideoResult + CLI renderer | de0f946 | show_video.py, show.py, test_show_video.py, test_show_cmd.py |
| T02 | on_screen_text facet + --on-screen-text CLI | 5dcee59 | search_library.py, search.py, test_search_library.py, test_search_cmd.py |
| T03 | vidscope_get_frame_texts MCP tool | 1315bed | server.py, test_frame_texts_tool.py, test_server.py |

## Verification Results

```
uv run pytest tests/unit/application/test_show_video.py -q  → 29 passed
uv run pytest tests/unit/application/test_search_library.py -q → 34 passed (incl. 6 M008)
uv run pytest tests/unit/cli/ -q → all passed
uv run pytest tests/unit/mcp/ -q → 35 passed (incl. 6 new M008)
uv run pytest -q → 1064 passed, 9 deselected
uv run mypy src → Success: no issues found in 105 source files
uv run lint-imports → Contracts: 11 kept, 0 broken
uv run vidscope --help | grep show → ok
uv run vidscope search --help | grep on-screen-text → ok
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy type assignment conflict — preview variable shadowing**
- **Found during:** T01 mypy check
- **Issue:** `preview = result.frame_texts[:_FRAME_TEXT_PREVIEW_LIMIT]` was assigned type `tuple[FrameText, ...]` but mypy inferred it as `str` because `preview` was already bound to `str` (description truncation) earlier in the same function scope
- **Fix:** Renamed the frame_texts slice variable to `ft_preview` to avoid the name collision
- **Files modified:** `src/vidscope/cli/commands/show.py`
- **Commit:** de0f946

**2. [Rule 1 - Bug] Rich markup swallows facet_str brackets**
- **Found during:** T02 GREEN phase — `test_on_screen_text_facet_rendered_in_header` failed
- **Issue:** `facet_str = " [" + facets + "]"` — rich interprets `[on-screen=promo]` as a markup tag and silently drops it from output. This bug existed for M007 facets too but was never tested (existing tests only checked `execute` call args, not rendered output)
- **Fix:** Changed opening bracket to `\\[` (rich escape) so the literal `[` is rendered to the terminal
- **Files modified:** `src/vidscope/cli/commands/search.py`
- **Commit:** 5dcee59

**3. [Rule 1 - Bug] test_server.py hardcoded eight-tool count**
- **Found during:** T03 full suite run
- **Issue:** `test_server_registers_eight_tools` asserted the exact set of 8 tool names; adding `vidscope_get_frame_texts` (9th tool) caused AssertionError
- **Fix:** Updated test method to `test_server_registers_nine_tools` with the full 9-tool set including `vidscope_get_frame_texts`
- **Files modified:** `tests/unit/mcp/test_server.py`
- **Commit:** 1315bed

## Known Stubs

None — all new functionality is fully wired end-to-end:
- `ShowVideoResult.frame_texts` is populated from `uow.frame_texts.list_for_video` (real SQLite adapter from S01-P01)
- `thumbnail_key` and `content_shape` flow from `Video` entity columns set by `VisualIntelligenceStage` (S03-P01)
- `on_screen_text` facet calls `uow.frame_texts.find_video_ids_by_text` with real FTS5 query (S01-P01)
- `vidscope_get_frame_texts` reuses `ShowVideoUseCase` and real container

## Threat Flags

None — all trust boundaries introduced by this plan (FTS5 query from --on-screen-text, MCP tool video_id argument, ShowVideoResult→CLI renderer) were covered by the plan's threat model (T-M008-S04-01 through T-M008-S04-06). No new unplanned surfaces were introduced.

## Self-Check: PASSED

Files verified:
- `src/vidscope/application/show_video.py` (frame_texts field + execute) — FOUND
- `src/vidscope/application/search_library.py` (on_screen_text facet) — FOUND
- `src/vidscope/cli/commands/show.py` (on-screen text section) — FOUND
- `src/vidscope/cli/commands/search.py` (--on-screen-text option) — FOUND
- `src/vidscope/mcp/server.py` (vidscope_get_frame_texts) — FOUND
- `tests/unit/mcp/test_frame_texts_tool.py` — FOUND

Commits verified:
- de0f946 T01 ShowVideoResult M008 extension — FOUND
- 5dcee59 T02 on_screen_text facet + CLI — FOUND
- 1315bed T03 MCP tool — FOUND

Tests: 1064 passed, 9 deselected
mypy: Success: no issues found in 105 source files
import-linter: Contracts: 11 kept, 0 broken
