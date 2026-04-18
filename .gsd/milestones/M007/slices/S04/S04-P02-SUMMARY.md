---
plan_id: S04-P02
phase: M007/S04
subsystem: application + cli + mcp
tags: [show-video, mcp-tool, hashtags, mentions, links, rich-content]
dependency_graph:
  requires: [S04-P01]
  provides: [vidscope_list_links MCP tool, enriched show_video use case, enriched show CLI]
  affects: [src/vidscope/application/show_video.py, src/vidscope/cli/commands/show.py, src/vidscope/mcp/server.py]
tech_stack:
  added: []
  patterns: [frozen dataclass additive extension, MCP tool closure pattern, TDD RED-GREEN-REFACTOR]
key_files:
  created:
    - tests/unit/application/test_show_video.py
    - tests/unit/cli/test_show_cmd.py
  modified:
    - src/vidscope/application/show_video.py
    - src/vidscope/cli/commands/show.py
    - src/vidscope/mcp/server.py
    - tests/unit/mcp/test_server.py
decisions:
  - ShowVideoResult gains 3 additive tuple fields defaulting to () for backward compat
  - vidscope show displays description truncated at 240 chars, music, hashtags (#), mentions (@), links count
  - vidscope_list_links MCP tool mirrors CLI semantics with optional source filter
metrics:
  duration_minutes: 35
  completed_at: "2026-04-18T11:03:29Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 6
  tests_added: 20
  tests_total: 935
---

# Phase M007 Plan S04-P02: User Surface Finalization Summary

**One-liner:** ShowVideoResult enriched with hashtags/mentions/links tuples + vidscope show displays M007 rich metadata + vidscope_list_links MCP tool exposing extracted URLs to AI agents.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T01 | Extend ShowVideoUseCase + ShowVideoResult | 30939f1 | show_video.py, test_show_video.py |
| T02 | Extend vidscope show CLI | f564998 | show.py, test_show_cmd.py |
| T03 | Add vidscope_list_links MCP tool | 7eac741 | server.py, test_server.py |

## What Was Built

### T01 — ShowVideoUseCase enrichment (TDD)

`ShowVideoResult` gains 3 new tuple fields, all defaulting to `()` for backward compatibility:

- `hashtags: tuple[Hashtag, ...] = ()`
- `mentions: tuple[Mention, ...] = ()`
- `links: tuple[Link, ...] = ()`

`ShowVideoUseCase.execute` reads all 3 relations from the unit of work within the same transaction:

```python
hashtags = tuple(uow.hashtags.list_for_video(video.id))
mentions = tuple(uow.mentions.list_for_video(video.id))
links = tuple(uow.links.list_for_video(video.id))
```

5 tests cover: found/not-found, all-three-repos called, backward compat, field types.

### T02 — vidscope show CLI enrichment (TDD)

The `show_command` now renders all M007 rich metadata after the video panel:

- **description**: displayed verbatim, truncated at 240 chars with `…` if longer (`_DESCRIPTION_PREVIEW_CHARS = 240`)
- **music**: `track — artist` format, `none` fallback
- **hashtags**: `#tag1, #tag2` format with `#` prefix, `none` fallback
- **mentions**: `@handle1, @handle2` format with `@` prefix, `none` fallback
- **links**: total count (not listed — use `vidscope links <id>` for full list)

11 tests cover all display paths, truncation, empty states, and `show 999` regression.

### T03 — vidscope_list_links MCP tool (TDD)

New tool registered via `build_mcp_server`, mirrors `ListLinksUseCase` semantics:

```python
def vidscope_list_links(video_id: int, source: str | None = None) -> dict[str, Any]:
```

Return schema:

```json
{
  "found": true,
  "video_id": 42,
  "source_filter": "description",
  "links": [
    {"id": 1, "url": "...", "normalized_url": "...", "source": "description", "position_ms": null}
  ]
}
```

On miss: `{"found": false, "video_id": 999, "links": []}`. DomainError re-raised as ValueError.

Updated `test_server_registers_eight_tools` to include the new tool. 4 new integration-style tests using `sandboxed_container` + real SQLite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unused import `dataclasses.field` in show_video.py**
- **Found during:** T03 ruff check
- **Issue:** Plan's action included `from dataclasses import dataclass, field` but `field` is not needed (no field() defaults in the dataclass)
- **Fix:** Removed `field` from the import
- **Files modified:** src/vidscope/application/show_video.py
- **Commit:** 7eac741

**2. [Rule 1 - Bug] Unused imports in test files**
- **Found during:** T03 ruff check
- **Issue:** `pytest`, `Language`, `TranscriptSegment`, `PlatformUserId` imported but unused in test_show_video.py; `pytest` unused in test_show_cmd.py; `VideoId` duplicated in test_server.py seed function
- **Fix:** Removed all unused imports
- **Files modified:** tests/unit/application/test_show_video.py, tests/unit/cli/test_show_cmd.py, tests/unit/mcp/test_server.py
- **Commit:** 7eac741

### Out-of-scope Pre-existing Issues (deferred)

The following ruff errors exist in pre-existing files and were NOT introduced by this plan:

- `tests/unit/application/test_list_creator_videos.py:8` — F401 unused import `ListCreatorVideosResult`
- `tests/unit/application/test_list_creators.py:114-116` — E501 lines too long (3 occurrences)

These are logged for future cleanup.

## Known Stubs

None. All data fields are wired from real repositories via `uow.*.list_for_video`.

## Threat Flags

None. The plan's threat model covered all new surfaces:
- T-S04P02-01: MCP URL exposure — accepted (local stdio, public URLs)
- T-S04P02-02: negative video_id — mitigated (int typing + repo returns None)
- T-S04P02-03: long description — mitigated (`_DESCRIPTION_PREVIEW_CHARS = 240`)
- T-S04P02-04: mention display — accepted (public @handles)
- T-S04P02-05: no MCP audit log — accepted (single-user local)

## Quality Gates

| Gate | Status |
|------|--------|
| `pytest -q` (935 tests) | PASSED |
| `mypy src` | PASSED |
| `lint-imports` (10 contracts) | PASSED |
| `ruff check src tests` (plan files) | PASSED |
| `vidscope show --help` | PASSED |
| MCP `vidscope_list_links` registered | PASSED |

## Self-Check: PASSED

- `src/vidscope/application/show_video.py` — FOUND
- `src/vidscope/cli/commands/show.py` — FOUND
- `src/vidscope/mcp/server.py` — FOUND
- `tests/unit/application/test_show_video.py` — FOUND
- `tests/unit/cli/test_show_cmd.py` — FOUND
- Commit 30939f1 — FOUND
- Commit f564998 — FOUND
- Commit 7eac741 — FOUND
