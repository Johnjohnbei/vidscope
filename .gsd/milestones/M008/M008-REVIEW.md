---
phase: M008
reviewed: 2026-04-18T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - src/vidscope/adapters/sqlite/frame_text_repository.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/adapters/vision/__init__.py
  - src/vidscope/adapters/vision/haarcascade_face_counter.py
  - src/vidscope/adapters/vision/rapidocr_engine.py
  - src/vidscope/application/search_library.py
  - src/vidscope/application/show_video.py
  - src/vidscope/cli/commands/search.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/values.py
  - src/vidscope/infrastructure/container.py
  - src/vidscope/infrastructure/startup.py
  - src/vidscope/mcp/server.py
  - src/vidscope/pipeline/stages/metadata_extract.py
  - src/vidscope/pipeline/stages/visual_intelligence.py
  - src/vidscope/ports/ocr_engine.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - .importlinter
  - pyproject.toml
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# M008: Code Review Report

**Reviewed:** 2026-04-18
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

M008 introduces the VisualIntelligenceStage (OCR via RapidOCR + face-count via OpenCV Haarcascade), the `FrameTextRepository` side table with FTS5 sync, two new domain columns (`thumbnail_key`, `content_shape`), the `on_screen_text` search facet, and the `vidscope_get_frame_texts` MCP tool. The architecture is clean: both vision adapters are self-contained, the import-linter contracts are respected, and the layering rules are followed throughout.

No critical (security-breaking or data-loss) issues were found. Five warnings require attention before this milestone is closed: a silent data-loss window in the FTS5 sync path, a path-traversal check that misses the backslash on Windows, a `_video_to_row` omission that strips `thumbnail_key`/`content_shape` on every future `upsert_by_platform_id` call, a `is_satisfied` logic gap that can cause the stage to claim satisfaction prematurely, and a rowcount reliability concern on bulk SQLite inserts. Four info items cover naming/quality improvements.

---

## Warnings

### WR-01: FTS5 sync re-queries ALL rows for the frame, not just newly inserted ones

**File:** `src/vidscope/adapters/sqlite/frame_text_repository.py:75-93`

**Issue:** After the bulk INSERT, `add_many_for_frame` immediately calls `_list_by_frame(frame_id)` to retrieve the inserted rows and sync them into `frame_texts_fts`. `_list_by_frame` returns every row for the given `frame_id`, not only the rows inserted in this call. On a re-run (e.g. crash recovery), if a frame already has rows from a previous partial write, those pre-existing rows are inserted into `frame_texts_fts` a second time. FTS5 has no uniqueness enforcement, so duplicate entries accumulate silently, causing `find_video_ids_by_text` to return duplicates and `DISTINCT` at query time does not deduplicate the *rank aggregation*. This is a data-correctness bug for re-runs.

**Fix:** Capture the inserted row count before re-querying and slice to the last N rows, or (better) use `RETURNING id` to get only the newly created ids, then sync only those:

```python
# Option A: use RETURNING (SQLite >= 3.35, SQLAlchemy 2.0 supports it)
result = self._conn.execute(
    frame_texts_table.insert().values(payloads).returning(frame_texts_table.c.id)
)
new_ids = {row[0] for row in result}
inserted = [r for r in self._list_by_frame(frame_id) if r.id in new_ids]

# Option B: count rows before, query after, slice the tail
count_before = len(self._list_by_frame(frame_id))
self._conn.execute(frame_texts_table.insert().values(payloads))
all_rows = self._list_by_frame(frame_id)
inserted = all_rows[count_before:]
```

---

### WR-02: Path-traversal guard misses Windows backslash separator

**File:** `src/vidscope/pipeline/stages/visual_intelligence.py:242-249`

**Issue:** The guard `if "/" in id_segment or ".." in id_segment` only rejects forward-slash traversal. On Windows the OS path separator is `\`, so a `platform_id` like `..\\..\\etc\\passwd` passes the check but `Path(thumb_key)` resolves it as a parent-directory traversal when `MediaStorage.store` writes the file through `pathlib`. The project targets cross-platform use (pyproject.toml classifiers include "Operating System :: OS Independent").

**Fix:** Extend the check to cover the backslash:

```python
_SUSPICIOUS = frozenset({"/", "\\", ".."})

def _is_suspicious(segment: str) -> bool:
    return ".." in segment or "/" in segment or "\\" in segment

if _is_suspicious(id_segment):
    _logger.warning(...)
    thumbnail_key = None
```

---

### WR-03: `_video_to_row` omits `thumbnail_key` and `content_shape`, causing silent column erasure on re-ingest

**File:** `src/vidscope/adapters/sqlite/video_repository.py:208-226`

**Issue:** `_video_to_row` builds the payload for both `add` and `upsert_by_platform_id`. It does NOT include `thumbnail_key` or `content_shape`. The `upsert_by_platform_id` statement uses `ON CONFLICT DO UPDATE SET ... (every key in payload)`. This means if `vidscope add <url>` is re-run on a video that has already been through `VisualIntelligenceStage`, the upsert overwrites `thumbnail_key` and `content_shape` with `NULL` (because the columns are absent from the update map). The visual metadata is silently lost.

**Fix:** Add the two new columns to `_video_to_row`:

```python
def _video_to_row(video: Video) -> dict[str, Any]:
    return {
        # ... existing keys ...
        "thumbnail_key": video.thumbnail_key,
        "content_shape": video.content_shape,
    }
```

---

### WR-04: `is_satisfied` can return `True` prematurely when FrameText rows exist but visual-metadata columns are missing

**File:** `src/vidscope/pipeline/stages/visual_intelligence.py:118-138`

**Issue:** `is_satisfied` checks three conditions: (a) `frame_texts.has_any_for_video`, (b) `video.thumbnail_key is not None`, (c) `video.content_shape is not None`. The logic is an early-return-on-False chain — all three must be true. However, `has_any_for_video` can return `True` (OCR rows were written) even when the stage crashed immediately after the FTS5 sync but *before* the `update_visual_metadata` call, because both writes happen inside the same open `uow` transaction but `update_visual_metadata` is called after the per-frame loop.

Because the UoW commits the full transaction on clean exit, a crash mid-execute means the transaction is rolled back entirely — so this scenario cannot occur in practice under normal crash conditions (transaction is atomic). However, if `update_visual_metadata` raises `StorageError` (video row missing — which is the documented raise path), the exception propagates out of `execute`, the UoW rolls back, and `is_satisfied` correctly returns `False` on the next run. This is fine.

The real issue is the inverse: `is_satisfied` is also called by the runner *before* the transaction is opened for this stage. At that point, a pre-existing video where `VisualIntelligenceStage` previously returned a `SKIPPED StageResult` (because `engine_marked_unavailable`, line 276) will have `frame_texts = 0` rows AND `thumbnail_key` populated (from a previous successful run that did only thumbnail+face-count). The `has_any_for_video` check returns `False`, so the stage will re-run — correct. But if a future code path (test or migration) pre-populates `frame_texts` for a video without running face-count, `is_satisfied` will return `True` incorrectly and permanently skip face-count and thumbnail update.

Document this coupling explicitly so future maintainers don't loosen the `is_satisfied` check:

```python
def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
    """Return True only when ALL three outputs are present:
    (a) at least one FrameText row (OCR ran),
    (b) thumbnail_key is set (thumbnail was copied),
    (c) content_shape is set (face-count ran).
    All three are written atomically in a single execute() transaction,
    so a partial state means execute() never completed successfully.
    Do NOT weaken this check — (a) alone is insufficient.
    """
```

This is a documentation/correctness warning; the current logic is sound for the production code path, but the comment in the existing code does not explain why all three conditions are necessary.

---

### WR-05: `rowcount` reliability on multi-row bulk insert with SQLite may be dialect-dependent

**File:** `src/vidscope/adapters/sqlite/frame_text_repository.py:58-65`

**Issue:** After `frame_texts_table.insert().values(payloads)` (a multi-row VALUES insert), the code checks `result.rowcount is None or result.rowcount == 0` and raises `StorageError` if true. For a batch insert with N rows, SQLAlchemy's SQLite dialect may return `rowcount = -1` (indeterminate) rather than N, depending on the SQLite version and driver in use. `-1` is not `None` and not `0`, so the guard passes — but `rowcount = -1` does not guarantee the insert succeeded. This has been observed with the `pysqlite` driver on bulk inserts in SQLAlchemy 2.0.x.

Additionally, the check fires incorrectly if the input list `texts` has exactly 0 items — but that case is handled by the early `if not texts: return []` at line 43, so it cannot reach the check in practice.

**Fix:** Remove the unreliable `rowcount` guard and rely on the re-query in `_list_by_frame` for confirmation:

```python
self._conn.execute(frame_texts_table.insert().values(payloads))
# Re-query to capture ids for FTS5 sync — this is the ground truth.
inserted = self._list_by_frame(frame_id)
if not inserted:
    raise StorageError(
        f"add_many_for_frame: insert acknowledged but no rows "
        f"retrieved for frame {int(frame_id)}"
    )
```

---

## Info

### IN-01: Graceful-degradation detection uses private sentinel `_unavailable` via `getattr`

**File:** `src/vidscope/pipeline/stages/visual_intelligence.py:274`

**Issue:** `getattr(self._ocr, "_unavailable", False)` reaches into the adapter's private state. This breaks the `OcrEngine` Protocol boundary: the Protocol does not declare `_unavailable`, so any non-`RapidOcrEngine` implementation that never sets that attribute (e.g. a test fake) will silently suppress the SKIPPED branch even when no text was extracted. The port docstring says "If the engine also exposes a `_unavailable` sentinel flag" — optional by design, but the coupling is fragile.

**Suggestion:** Add an optional `is_available() -> bool` method to the `OcrEngine` Protocol with a default implementation, or pass an explicit `ocr_available: bool` flag to `VisualIntelligenceStage.__init__` at wiring time:

```python
# In container.py
ocr_available = find_spec("rapidocr_onnxruntime") is not None
visual_intelligence_stage = VisualIntelligenceStage(
    ocr_engine=ocr_engine,
    ocr_available=ocr_available,
    ...
)
```

---

### IN-02: `vidscope_get_frame_texts` MCP tool reuses `ShowVideoUseCase` instead of a dedicated use case

**File:** `src/vidscope/mcp/server.py:391-437`

**Issue:** The `vidscope_get_frame_texts` tool fetches the full `ShowVideoResult` (video + transcript + frames + analysis + creator + hashtags + mentions + links + frame_texts) and discards everything except `frames` and `frame_texts`. This is a read-amplification issue: for a video with many relations, the tool loads and discards ~7 unnecessary queries per call. Not in-scope as a performance issue for v1, but it signals the use case is being abused.

**Suggestion:** Create a dedicated `GetFrameTextsUseCase` in `src/vidscope/application/` that only queries `uow.videos.get` + `uow.frames.list_for_video` + `uow.frame_texts.list_for_video`. This also makes the frame-texts tool's contract explicit and testable in isolation.

---

### IN-03: `check_vision` in `startup.py` imports `version` twice under the same local name

**File:** `src/vidscope/infrastructure/startup.py:413-419`

**Issue:** `from importlib.metadata import version` is imported twice on lines 413 and 418, both assigned to the local name `version`. The second import shadows the first. Python handles this correctly (both refer to the same object), but it is confusing and would be flagged by any linter configured to catch duplicate imports.

**Suggestion:** Import once before both `try` blocks:

```python
try:
    from importlib.metadata import version as _pkg_version
    rapidocr_v = _pkg_version("rapidocr-onnxruntime")
except Exception:
    rapidocr_v = "unknown"
try:
    cv2_v = _pkg_version("opencv-python-headless")
except Exception:
    cv2_v = "unknown"
```

---

### IN-04: `platform_segment` can be the literal string `"unknown"` in the thumbnail key

**File:** `src/vidscope/pipeline/stages/visual_intelligence.py:239`

**Issue:** When `ctx.platform` is `None`, the thumbnail key becomes `videos/unknown/<id>/thumb.jpg`. `ctx.platform` is `None` only before the IngestStage has run, but `VisualIntelligenceStage.execute` runs after `FramesStage` which in turn requires `IngestStage` to have completed. In practice `ctx.platform` will never be `None` at this point. However, the fallback silently produces a valid-looking but semantically incorrect key with no warning.

**Suggestion:** Replace the silent fallback with an explicit guard that raises `IndexingError`, consistent with how the stage already guards `ctx.video_id is None`:

```python
if ctx.platform is None:
    raise IndexingError(
        "visual_intelligence: ctx.platform is None — "
        "ingest stage must run first"
    )
platform_segment = ctx.platform.value
```

---

_Reviewed: 2026-04-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
