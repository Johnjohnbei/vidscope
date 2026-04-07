---
id: T01
parent: S02
milestone: M002
key_files:
  - src/vidscope/application/suggest_related.py
  - src/vidscope/application/__init__.py
  - tests/unit/application/test_suggest_related.py
key_decisions:
  - Jaccard similarity on keyword sets — simplest signal that produces meaningful ordering. M004 LLM analyzers will improve input quality; R026 embeddings deferred.
  - Score == 0 candidates excluded — no point returning a 0.0 score even if the user asked for limit=10
  - Ties broken by video_id for deterministic ordering — test reproducibility matters
  - Single open UoW for the whole operation — all reads in one transaction, no write
  - 500-candidate cap as a safety net for pathological large libraries — documented as known limitation
  - Empty source keywords returns empty suggestions with a clear reason — 'no signal → no result' is honest
duration: 
verification_result: passed
completed_at: 2026-04-07T17:22:54.892Z
blocker_discovered: false
---

# T01: Shipped SuggestRelatedUseCase with Jaccard keyword overlap — 11 unit tests covering happy path, 6 edge cases, score ordering. Pure stdlib, zero deps.

**Shipped SuggestRelatedUseCase with Jaccard keyword overlap — 11 unit tests covering happy path, 6 edge cases, score ordering. Pure stdlib, zero deps.**

## What Happened

SuggestRelatedUseCase implements R023's v1 suggestion engine. Algorithm:

1. Open a UnitOfWork that stays open for the whole operation
2. Fetch source video + its latest analysis
3. If source analysis is None OR keywords are empty, return empty with a clear reason
4. Fetch all videos in the library (capped at 500 via `list_recent(limit=500)`)
5. For each candidate != source, fetch its latest analysis
6. Compute Jaccard = |intersection| / |union| on keyword sets
7. Skip candidates with score 0
8. Sort descending by score (ties broken by video_id for determinism)
9. Take top `limit` (clamped to [1, 100])

**Three DTOs:**
- `Suggestion`: one entry with video_id, title, platform, score, matched_keywords (sorted tuple of intersection)
- `SuggestRelatedResult`: source_video_id, source_found, source_title, source_keywords, suggestions tuple, reason string
- `reason` always explains why the list is empty when it is: "no video with id X", "no analysis keywords yet", "no candidates share keywords", "library is empty", or "found N related videos"

**Pure stdlib**: only uses `frozenset` for set operations. No numpy, no sklearn, no scipy. Fast for libraries up to 500 videos (the cap is a safety net — real libraries will be well below).

**11 tests cover:**
- Happy path: 3 candidates with high/low/zero overlap → only high and low returned, high ranked first
- Limit clamps results: 5 matching candidates, limit=3 → 3 returned
- Source video excluded from results
- Matched keywords are only the intersection (sorted)
- Missing source returns not_found with clear reason
- Source with no analysis returns empty with "no analysis keywords" reason
- Source with empty keywords returns empty (analysis exists but keywords=()) 
- Library with only source returns empty with "no candidates share keywords"
- Candidates without analyses are skipped silently
- Invalid limit (-5 → clamped to 1, 9999 → returns all available)
- Full overlap (1.0) beats partial (0.5) in the ranking

Runtime: 210ms for all 11 tests on real SQLite.

## Verification

Ran `python -m uv run pytest tests/unit/application/test_suggest_related.py -q` → 11 passed in 210ms.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/application/test_suggest_related.py -q` | 0 | ✅ 11/11 tests green | 210ms |

## Deviations

None.

## Known Issues

Candidate scanning is O(N) over the library with one DB query per candidate for the analysis fetch. For libraries beyond 500 videos this becomes expensive. The 500 cap is a safety net; if the user's library grows large, M003 can add a keyword index table or precompute a sparse vector representation.

## Files Created/Modified

- `src/vidscope/application/suggest_related.py`
- `src/vidscope/application/__init__.py`
- `tests/unit/application/test_suggest_related.py`
