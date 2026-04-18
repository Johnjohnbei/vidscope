---
phase: M008
fixed_at: 2026-04-18T00:00:00Z
review_path: .gsd/milestones/M008/M008-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase M008: Code Review Fix Report

**Fixed at:** 2026-04-18
**Source review:** .gsd/milestones/M008/M008-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### WR-01 + WR-05: FTS5 sync targets only newly inserted rows; rowcount guard removed

**Files modified:** `src/vidscope/adapters/sqlite/frame_text_repository.py`
**Commit:** 57f62d3
**Applied fix:** Both findings addressed in a single atomic edit. Replaced the unreliable `result.rowcount` check (WR-05) with a count-before/slice approach (WR-01): `count_before = len(_list_by_frame(frame_id))` is captured before the INSERT, then `all_rows[count_before:]` targets only newly written rows for FTS5 sync. A re-query-based `StorageError` replaces the rowcount guard as the ground truth for insert confirmation.

---

### WR-02: Path-traversal guard extended to cover Windows backslash

**Files modified:** `src/vidscope/pipeline/stages/visual_intelligence.py`
**Commit:** d0a9691
**Applied fix:** Added `"\\" in id_segment` to the existing traversal guard so the condition now reads `"/" in id_segment or "\\" in id_segment or ".." in id_segment`, blocking both Unix forward-slash and Windows backslash traversal attempts.

---

### WR-03: _video_to_row now includes thumbnail_key and content_shape

**Files modified:** `src/vidscope/adapters/sqlite/video_repository.py`
**Commit:** cfa3b55
**Applied fix:** Added `"thumbnail_key": video.thumbnail_key` and `"content_shape": video.content_shape` to the dict returned by `_video_to_row`. This ensures `upsert_by_platform_id` preserves visual metadata on re-ingest instead of silently NULLing those columns.

---

### WR-04: is_satisfied docstring explains why all three conditions are required

**Files modified:** `src/vidscope/pipeline/stages/visual_intelligence.py`
**Commit:** 50bff3f
**Applied fix:** Rewrote the `is_satisfied` docstring to explicitly state that all three outputs (FrameText rows, thumbnail_key, content_shape) are written atomically in one transaction, that partial state means the stage never completed, and that weakening the check to (a) alone would cause permanent skipping for videos pre-populated via test fixtures or migrations.

---

## Verification

- `uv run pytest -q --tb=short`: **1064 passed, 9 deselected** — no regressions
- `uv run mypy src`: **Success: no issues found in 105 source files**

---

_Fixed: 2026-04-18_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
