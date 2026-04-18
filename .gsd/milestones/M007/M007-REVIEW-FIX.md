---
phase: M007 Code Review Fix
fixed_at: 2026-04-18T00:00:00Z
review_path: .gsd/milestones/M007/M007-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase M007: Code Review Fix Report

**Fixed at:** 2026-04-18
**Source review:** `.gsd/milestones/M007/M007-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: Type Safety Bypass in ShowVideoUseCase.execute

**Files modified:** `src/vidscope/application/show_video.py`
**Commit:** `1cb03f8`
**Applied fix:** Removed all six `# type: ignore[arg-type]` suppressions. After the `if video is None: return` guard, added `assert video.id is not None` to narrow the type (with a message documenting the DB invariant), then assigned `vid_id: VideoId = video.id`. All repository calls now use `vid_id` — no type ignores remain.

---

### CR-02: Potential Null Dereference in LinkRepositorySQLite.add_many_for_video

**Files modified:** `src/vidscope/adapters/sqlite/link_repository.py`
**Commit:** `dc9f503`
**Applied fix:** Captured the `result` of `self._conn.execute(links_table.insert().values(payloads))` and checked `result.rowcount`. If `rowcount` is `None` or `0`, a `StorageError` is raised before `list_for_video` is called. Added a `except StorageError: raise` guard so the rowcount error is not re-wrapped by the outer `except SQLAlchemyError` block (also updated as part of WR-03).

---

### CR-03: Silent Empty Tag Deduplication in HashtagRepositorySQLite

**Files modified:** `src/vidscope/adapters/sqlite/hashtag_repository.py`
**Commit:** `c77cd9f`
**Applied fix:** Added `import logging` and `_logger = logging.getLogger(__name__)` at module level. Separated the combined `if not canon or canon in seen` condition into two distinct branches: the `not canon` branch now emits `_logger.debug(...)` identifying the raw tag and video id before continuing, making the drop observable at DEBUG log level.

---

### WR-01: Incomplete Error Handling in MetadataExtractStage.execute

**Files modified:** `src/vidscope/pipeline/stages/metadata_extract.py`
**Commit:** `5b0409e`
**Applied fix:** Replaced the ternary `description = video.description if video is not None else None` pattern with an explicit guard: raises `IndexingError` when `video is None`, then accesses `video.description` directly. This eliminates the implicit null-coalescing and makes the failure mode explicit and loud.

---

### WR-02: Unsafe Type Conversion in SearchLibraryUseCase.execute

**Files modified:** `src/vidscope/application/search_library.py`
**Commit:** `c30db3c`
**Applied fix:** Added a multi-line comment above the `music_track` facet set comprehension documenting that `None == music_track` is always `False` in Python, that this is intentional, and that NULL rows mean "unknown" and should not match a specific track search. Added an inline `# excludes NULL rows` comment on the comparison line.

---

### WR-03: Bare Exception Catching in Repository Adapters

**Files modified:** `src/vidscope/adapters/sqlite/hashtag_repository.py`, `src/vidscope/adapters/sqlite/mention_repository.py`, `src/vidscope/adapters/sqlite/link_repository.py`, `src/vidscope/adapters/sqlite/video_repository.py`
**Commit:** `a49bb5d`
**Applied fix:** Added `from sqlalchemy.exc import SQLAlchemyError` import to all four files. Changed every `except Exception as exc` that wraps storage failures to `except SQLAlchemyError as exc`. In `link_repository.py` the existing `except StorageError: raise` guard (added by CR-02) is preserved so the rowcount `StorageError` propagates without being re-wrapped. In `video_repository.py` both the `add()` and `upsert_by_platform_id()` handlers were updated.

---

## Skipped Issues

None — all in-scope findings were fixed successfully.

---

_Fixed: 2026-04-18_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
