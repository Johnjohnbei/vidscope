---
phase: M012
plan: S02
subsystem: analyze
tags: [analyze, heuristic, stopwords, ocr, carousel, r062, r063]
dependency_graph:
  requires: [M012/S01, M008/S01]
  provides: [R062, R063]
  affects: [analyze-pipeline, frame_texts-table, stopwords-module, heuristic-analyzer]
tech_stack:
  added: []
  patterns: [dataclasses-replace, frozenset-union, ocr-transcript-fallback, tdd-red-green]
key_files:
  created:
    - tests/unit/adapters/heuristic/test_stopwords.py
  modified:
    - src/vidscope/pipeline/stages/analyze.py
    - src/vidscope/adapters/heuristic/stopwords.py
    - tests/unit/pipeline/stages/test_analyze.py
    - tests/unit/adapters/heuristic/test_analyzer.py
decisions:
  - "dataclasses.replace(raw_analysis, video_id=ctx.video_id) used instead of manual
    field-by-field rebind — preserves all M010 additive fields automatically and resolves
    a latent debt where verticals/information_density etc. were silently dropped"
  - "Synthetic OCR Transcript stays in-memory (never persisted to transcripts table) to
    avoid polluting the transcripts table with non-audio content"
  - "Language.UNKNOWN used for all synthetic OCR Transcripts — no language detection
    added (scope strict R062, R067 candidate for future)"
  - "_FRENCH_CONTRACTIONS and _FRENCH_COMMON_VERBS as separate named frozensets unioned
    into FRENCH_STOPWORDS — improves readability, testability, and future extensibility"
  - "n'a (3 chars) and dit (3 chars) included in stopword sets despite being below
    _MIN_KEYWORD_LENGTH=4 — test T03 canonical list requires explicit membership"
metrics:
  duration: ~75min
  completed: "2026-04-21T08:49:00Z"
  tasks_completed: 7
  files_changed: 5
---

# Phase M012 Plan S02: Analyze intelligence carousel — Summary

**One-liner:** AnalyzeStage OCR fallback via `uow.frame_texts.list_for_video` removes IMAGE/CAROUSEL skip from `is_satisfied`, and French contractions + conjugated verbs (37+74 entries) are unioned into `FRENCH_STOPWORDS` to eliminate grammatical noise from keywords.

## Tasks Completed

| Task | Name | Commit | Status |
|------|------|--------|--------|
| T01 | RED — delete 2 obsolete M010 tests + add TestAnalyzeStageMediaTypeR062 | dcace57 | Done |
| T02 | RED — add TestAnalyzeStageOcrFallback (R062 execute OCR fallback) | 0674c92 | Done |
| T03 | RED — R063 tests (French contractions + verbs + stopwords coverage) | 84e17a8 | Done |
| T04 | GREEN R062 — AnalyzeStage OCR fallback + is_satisfied fix + M010 passthrough | 29590e5 | Done |
| T05 | GREEN R063 — extend stopwords.py with French contractions + common verbs | 5c0b3d2 | Done |
| T06 | Align test_missing_transcript_raises with R062 behavior | 3bee6dc | Done |
| T07 | Full suite regression gate — 1672/1673 pass, 0 new failures | 535533d | Done |

## Requirements Coverage

**R062 — AnalyzeStage carousel OCR fallback:**
- T01: is_satisfied no longer returns True unconditionally for IMAGE/CAROUSEL
- T04: is_satisfied checks `uow.analyses.get_latest_for_video(ctx.video_id)` regardless of media_type
- T04: execute() builds synthetic `Transcript(language=Language.UNKNOWN, full_text=ocr_concat, segments=())` from `uow.frame_texts.list_for_video(ctx.video_id)` when transcript is None
- T04: empty/whitespace FrameText rows filtered before concatenation
- T04: when neither transcript nor frame_texts exist, analyzer produces stub (score=0, summary="no speech detected") — no crash
- T04: `dataclasses.replace(raw_analysis, video_id=ctx.video_id)` preserves all M010 fields
- T06: test_missing_transcript_raises replaced by test_missing_transcript_no_ocr_produces_empty_analysis

**R063 — French stopwords extension:**
- T05: `_FRENCH_CONTRACTIONS` frozenset (37 entries): c'est, j'ai, d'un, qu'il, n'est, s'il, aujourd'hui, etc.
- T05: `_FRENCH_COMMON_VERBS` frozenset (74 entries): veux, peux, pouvez, montrer, montré, pris, mis, etc.
- T05: `FRENCH_STOPWORDS` (287 entries) absorbs both via `| _FRENCH_CONTRACTIONS | _FRENCH_COMMON_VERBS`
- T05: `ENGLISH_STOPWORDS` unchanged (196 entries) — both meet R063 minimum >= 100

## Test Results

```
1672 passed, 1 pre-existing failure (playwright not installed — hors scope)
0 regressions on M012/S01 baseline tests
New tests: +17 net (T01: 4, T02: 4, T03: 10, T06: 1, minus T01: -2 deleted)
Golden gate (test_golden.py): 10/10 passed — stopwords extension did not affect
  content_type/is_sponsored/sentiment classification fields
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Missing canonical contractions n'a and dit**
- **Found during:** T05 (stopwords GREEN run)
- **Issue:** Test T03 canonical lists included `n'a` (3 chars) and `dit` (3 chars).
  Both are below `_MIN_KEYWORD_LENGTH=4` so they'd never leak into keywords anyway,
  but the explicit membership tests required them in `FRENCH_STOPWORDS`.
- **Fix:** Added `"n'a"` to `_FRENCH_CONTRACTIONS` and `"dit"` to `_FRENCH_COMMON_VERBS`.
- **Files modified:** `src/vidscope/adapters/heuristic/stopwords.py`
- **Commit:** 5c0b3d2

**2. [Rule 3 — Blocking] Worktree branch based on older commit d19e0d7 instead of 50b02cc**
- **Found during:** Start of execution (worktree_branch_check)
- **Issue:** The worktree was at commit d19e0d7 (before M012/S01 changes), not 50b02cc.
  A soft reset to 50b02cc left M012/S01 files in staged state, causing first commit to
  include 44 spurious file changes.
- **Fix:** Hard reset to 50b02cc to restore clean working tree, then re-applied T01 changes.
- **Impact:** One extra commit created then hard-reset (not in final history).

## Known Stubs

None — R062 and R063 are fully implemented. The carousel analysis path is wired end-to-end:
`vidscope add <carousel-url>` → VisualIntelligenceStage writes frame_texts → AnalyzeStage
builds synthetic Transcript → HeuristicAnalyzer produces keywords/topics → Analysis persisted.

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced.
All mitigations from the plan's threat model remain satisfied:
- T-M012S02-01: `list_for_video` uses SQLAlchemy bind params (verified unchanged)
- T-M012S02-04: `is_satisfied` correctly prevents double-analysis via `get_latest_for_video`

## Retroactive note for pre-existing carousels

Pre-R062 carousels have `analysis=null` in DB. After M012/S02 deployment, re-running
`vidscope add <url>` is idempotent at ingest level (platform_id UNIQUE) but `AnalyzeStage`
will run and produce the missing Analysis row. No migration script needed.

## Self-Check: PASSED

Files verified:
- src/vidscope/pipeline/stages/analyze.py: exists, contains `uow.frame_texts.list_for_video`
- src/vidscope/adapters/heuristic/stopwords.py: exists, contains `_FRENCH_CONTRACTIONS`
- tests/unit/pipeline/stages/test_analyze.py: exists, contains `TestAnalyzeStageOcrFallback`
- tests/unit/adapters/heuristic/test_analyzer.py: exists, contains `TestHeuristicAnalyzerFrenchStopwordsR063`
- tests/unit/adapters/heuristic/test_stopwords.py: exists (new file)

Commits verified:
- dcace57: T01 RED — delete 2 obsolete tests + TestAnalyzeStageMediaTypeR062
- 0674c92: T02 RED — TestAnalyzeStageOcrFallback
- 84e17a8: T03 RED — R063 tests + test_stopwords.py
- 29590e5: T04 GREEN — AnalyzeStage OCR fallback
- 5c0b3d2: T05 GREEN — stopwords.py extension
- 3bee6dc: T06 — test_missing_transcript alignment
- 535533d: T07 — regression gate
