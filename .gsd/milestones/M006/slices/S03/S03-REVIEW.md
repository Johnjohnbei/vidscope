---
phase: M006-S03
reviewed: 2026-04-17T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - scripts/verify-m006-s03.sh
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/application/__init__.py
  - src/vidscope/application/get_creator.py
  - src/vidscope/application/list_creator_videos.py
  - src/vidscope/application/list_creators.py
  - src/vidscope/application/show_video.py
  - src/vidscope/cli/app.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/commands/creators.py
  - src/vidscope/cli/commands/list.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/domain/entities.py
  - src/vidscope/mcp/server.py
  - src/vidscope/ports/repositories.py
  - tests/unit/application/test_get_creator.py
  - tests/unit/application/test_list_creator_videos.py
  - tests/unit/application/test_list_creators.py
  - tests/unit/cli/test_creators.py
  - tests/unit/mcp/test_server.py
  - tests/unit/mcp/test_server_creator.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase M006/S03: Code Review Report

**Reviewed:** 2026-04-17T00:00:00Z
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

This slice delivers three application use cases (`GetCreatorUseCase`, `ListCreatorsUseCase`, `ListCreatorVideosUseCase`), the `VideoRepository.list_by_creator` adapter method, a Typer `creator` sub-app (show/list/videos), a `vidscope_get_creator` MCP tool, and the E2E verification harness. The overall design is clean and follows the hexagonal architecture conventions established in earlier milestones consistently.

Three warnings are raised:

1. `ListCreatorVideosUseCase` silently produces a wrong `total` for creators with more than 10,000 videos because it proxies the count via a second `list_by_creator(limit=10000)` call instead of a dedicated port method.
2. `ListCreatorsUseCase`'s no-filter path hardcodes the three current platforms in three separate queries, which means the count (`uow.creators.count()`) and the listing can silently diverge when a fourth platform is later introduced.
3. `test_server_creator.py` accesses `mcp._tool_manager._tools`, a private FastMCP internal, making all creator MCP unit tests fragile to upstream library refactors.

No critical security or data-safety issues were found.

---

## Warnings

### WR-01: `total` silently capped at 10,000 in `ListCreatorVideosUseCase`

**File:** `src/vidscope/application/list_creator_videos.py:59-63`

**Issue:** The use case calls `list_by_creator` twice — once with `limit` for the page and once with `limit=10000` to derive the total count. If a creator ever has more than 10,000 linked videos the `total` field is silently wrong (capped at 10,000). There is no `count_by_creator()` method on `VideoRepository`, so the workaround is the only option given the current port, but the 10,000 magic cap makes the contract incorrect and is not documented.

**Fix:** Add a `count_by_creator(creator_id: CreatorId) -> int` method to the `VideoRepository` port and implement it in `VideoRepositorySQLite`. Until then, document the cap explicitly in the docstring so it is visible in the contract:

```python
# In ports/repositories.py — add to VideoRepository Protocol:
def count_by_creator(self, creator_id: CreatorId) -> int:
    """Return the total number of videos linked to ``creator_id``."""
    ...

# In list_creator_videos.py — replace the double-fetch with:
videos = uow.videos.list_by_creator(creator.id, limit=limit)
total = uow.videos.count_by_creator(creator.id)
```

Until the port is extended, at minimum add an `# NOTE: capped at 10_000` comment and a named constant instead of the bare magic number:

```python
_COUNT_LIMIT = 10_000  # temporary until count_by_creator() port method exists
all_videos = uow.videos.list_by_creator(creator.id, limit=_COUNT_LIMIT)
total = len(all_videos)
```

---

### WR-02: `ListCreatorsUseCase` no-filter path hardcodes platform enum values

**File:** `src/vidscope/application/list_creators.py:78-90`

**Issue:** When neither `platform` nor `min_followers` is supplied, the use case builds the result by calling `list_by_platform` once per hardcoded platform (`YOUTUBE`, `TIKTOK`, `INSTAGRAM`). The `total` is obtained from `uow.creators.count()`, which is platform-agnostic. If a fourth platform is added to `Platform`, creators on that platform will be counted in `total` but absent from `creators`, so the displayed "showing N of M" will be misleading without any error or warning.

**Fix:** Drive the no-filter loop from the enum definition so new platforms are included automatically:

```python
# Replace the three explicit list_by_platform calls with:
all_creators: list[Creator] = []
for plat in Platform:
    all_creators.extend(uow.creators.list_by_platform(plat, limit=200))
creators = sorted(
    all_creators,
    key=lambda c: c.last_seen_at or c.created_at or _EPOCH,
    reverse=True,
)[:limit]
```

Alternatively, add a `list_all(limit: int) -> list[Creator]` method to `CreatorRepository` and implement it with a single SQL query ordered by `last_seen_at DESC`.

---

### WR-03: MCP creator tool tests access private FastMCP internals

**File:** `tests/unit/mcp/test_server_creator.py:51-59`

**Issue:** `_get_tool` reaches into `mcp._tool_manager._tools` to extract the registered tool function. This is a private attribute of FastMCP's internal `ToolManager`. Any FastMCP release that renames or restructures `_tool_manager` or `_tools` will silently break all 8 creator MCP tests without any upstream type error.

The pre-existing `test_server.py` uses `asyncio.run(server.call_tool(name, args))` instead, which is the public API. The creator tests should follow the same pattern.

**Fix:** Replace the `_get_tool` helper and its direct invocations with the public `call_tool` API, matching the pattern already established in `test_server.py`:

```python
import asyncio

def _call_tool(server, name: str, args: dict) -> dict:
    _, structured = asyncio.run(server.call_tool(name, args))
    assert isinstance(structured, dict)
    return structured

class TestVidscopeGetCreatorTool:
    def test_found_returns_creator_dict(self, container: Container) -> None:
        _insert_creator(container, "@alice")
        server = build_mcp_server(container)
        result = _call_tool(server, "vidscope_get_creator",
                            {"handle": "@alice", "platform": "youtube"})
        assert result["found"] is True
        assert result["creator"]["handle"] == "@alice"
```

---

## Info

### IN-01: `upsert_by_platform_id` comment inaccurate — `id` is not in the payload

**File:** `src/vidscope/adapters/sqlite/video_repository.py:74-79`

**Issue:** The comment on line 74 reads "update every field except id and created_at", implying `id` is actively excluded from the update map. In practice `_video_to_row()` never includes `id` in the dict, so the exclusion clause `if key not in ("created_at",)` is only excluding `created_at`. The mention of `id` is misleading documentation.

**Fix:** Update the comment to accurately reflect what the code does:

```python
# On conflict, update every non-identity field except created_at.
update_map = {
    key: stmt.excluded[key]
    for key in payload
    if key not in ("created_at",)
}
```

---

### IN-02: `verify-m006-s03.sh` step 4 grep on `tail -3` may miss "passed" for zero-test edge case

**File:** `scripts/verify-m006-s03.sh:115`

**Issue:** The test gate greps the last 3 lines of pytest output for the word "passed". If a test file is accidentally empty and pytest emits `no tests ran` without "passed", the step reports FAIL even though no test actually failed. This is a rare edge case but produces a confusing failure message during early development.

**Fix:** Extend the grep to also match `"no tests ran"` as a skip-worthy outcome, or alternatively use pytest's exit-code directly:

```bash
python -m uv run pytest "${_test_files[@]}" -x -q --tb=short
_exit=$?
if [ $_exit -eq 0 ] || [ $_exit -eq 5 ]; then   # 5 = no tests collected
  ok "Tests unitaires S03 verts"
else
  fail "Des tests unitaires S03 échouent"
fi
```

---

### IN-03: `show_video.py` suppresses type errors on `video.id` without a guard

**File:** `src/vidscope/application/show_video.py:46-48`

**Issue:** After the `if video is None: return` guard, `video.id` is typed as `VideoId | None` (from the `Video` dataclass definition). The three `# type: ignore[arg-type]` comments suppress the resulting mypy errors. Since `video` was fetched from the repository, `id` will always be populated in practice, but this pattern bypasses static type checking and would silently break if a `Video` with `id=None` were passed.

**Fix:** Assert the invariant so mypy and runtime agree:

```python
video = uow.videos.get(VideoId(video_id))
if video is None:
    return ShowVideoResult(found=False)
assert video.id is not None, "repo-returned Video must have id populated"
transcript = uow.transcripts.get_for_video(video.id)
frames = tuple(uow.frames.list_for_video(video.id))
analysis = uow.analyses.get_latest_for_video(video.id)
```

This removes the need for `# type: ignore` and documents the invariant explicitly.

---

_Reviewed: 2026-04-17T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
