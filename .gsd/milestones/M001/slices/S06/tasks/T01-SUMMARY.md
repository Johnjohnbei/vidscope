---
id: T01
parent: S06
milestone: M001
key_files:
  - src/vidscope/pipeline/stages/index.py
  - src/vidscope/pipeline/stages/__init__.py
  - tests/unit/pipeline/stages/test_index.py
key_decisions:
  - IndexStage.is_satisfied always False — re-indexing is cheap (single DELETE+INSERT per source) and idempotent. Better to re-index on every run than to risk stale indexes.
  - Stage indexes both transcripts AND analysis summaries so vidscope search can match either source
duration: 
verification_result: passed
completed_at: 2026-04-07T16:04:09.061Z
blocker_discovered: false
---

# T01: Shipped IndexStage: writes transcripts + analysis summaries to FTS5 via uow.search_index, idempotent re-indexing — 6 stage tests, search returns real hits.

**Shipped IndexStage: writes transcripts + analysis summaries to FTS5 via uow.search_index, idempotent re-indexing — 6 stage tests, search returns real hits.**

## What Happened

IndexStage is the smallest stage so far because all the heavy lifting happens in the SearchIndexSQLite adapter from S01. The stage just orchestrates: read latest transcript, read latest analysis, call index_transcript and/or index_analysis based on what's available. Returns a StageResult with the count of documents indexed.

is_satisfied always returns False because re-indexing is cheap and idempotent (the SearchIndexSQLite adapter uses DELETE-then-INSERT semantics). Re-running on the same video updates the index instead of duplicating.

6 tests with real SQLite + real FTS5: indexes both transcript and analysis (search returns hits), specific keyword matching, indexes transcript only when no analysis, indexes 0 when neither exists, is_satisfied always False, missing video_id raises IndexingError.

## Verification

Ran `python -m uv run pytest tests/unit/pipeline/stages -q` → 37 passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/pipeline/stages -q` | 0 | ✅ pass (37/37) | 690ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/pipeline/stages/index.py`
- `src/vidscope/pipeline/stages/__init__.py`
- `tests/unit/pipeline/stages/test_index.py`
