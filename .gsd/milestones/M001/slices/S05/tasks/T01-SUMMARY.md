---
id: T01
parent: S05
milestone: M001
key_files:
  - src/vidscope/adapters/heuristic/__init__.py
  - src/vidscope/adapters/heuristic/analyzer.py
  - src/vidscope/adapters/heuristic/stub.py
  - src/vidscope/adapters/heuristic/stopwords.py
  - tests/unit/adapters/heuristic/test_analyzer.py
key_decisions:
  - Pure stdlib (re + Counter), no third-party deps for the default analyzer per D010
  - Composite score: length (40) + diversity (30) + segments (30) = max 100. Each sub-signal has a clear cap.
  - Empty transcripts still return a valid Analysis row — the row exists for the FTS5 index in S06 even when there's no speech to index
  - StubAnalyzer is a deliberate placeholder — not meant for production, only to prove the pluggable seam works
  - Stopword lists store as frozensets for O(1) lookup
duration: 
verification_result: passed
completed_at: 2026-04-07T15:55:14.150Z
blocker_discovered: false
---

# T01: Shipped HeuristicAnalyzer + StubAnalyzer + FR/EN stopword lists — pure-Python zero-network analyzer with composite scoring, 15 unit tests, 70ms.

**Shipped HeuristicAnalyzer + StubAnalyzer + FR/EN stopword lists — pure-Python zero-network analyzer with composite scoring, 15 unit tests, 70ms.**

## What Happened

HeuristicAnalyzer is the default zero-cost zero-network analyzer per D010. Pure stdlib (re, collections.Counter), no third-party imports.

Strategy: tokenize via regex, exclude stopwords (FR + EN, ~300 words combined), filter to tokens >= 4 chars, take top 8 by frequency as keywords, top 3 as topics. Score is a composite of length (max 40 points), vocabulary diversity (max 30), segment density (max 30) capped at 100. Summary is the first ~200 chars truncated at the last space with ellipsis. Empty transcripts return a valid Analysis row with score=0 and summary='no speech detected' so the row exists for the search index in S06.

StubAnalyzer is a minimal second analyzer that returns a placeholder Analysis. Its only purpose is to prove the registry pattern in T02 — it lets us swap providers via env var without touching callers. R010's pluggable seam will be validated in T02 with the registry + container wiring.

Stopword lists in `stopwords.py` are frozensets of ~150 English + ~150 French words covering the most common articles, pronouns, conjunctions, prepositions, common verbs. Not exhaustive but enough to keep keyword extraction meaningful.

15 tests: empty transcript, whitespace only, English keyword extraction, French keyword extraction, topics subset of keywords, stopwords excluded (English), stopwords excluded (French), score in [0, 100], longer scores higher than shorter, short summary returned as is, long summary truncated with ellipsis, provider name, StubAnalyzer provider name + placeholder + video_id preservation.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/heuristic -q` → 15 passed in 70ms.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/heuristic -q` | 0 | ✅ pass (15/15) | 70ms |

## Deviations

None.

## Known Issues

Stopword lists are not exhaustive — they're tuned for common social-media short-form content. If the corpus shifts to formal text, more stopwords may be needed.

## Files Created/Modified

- `src/vidscope/adapters/heuristic/__init__.py`
- `src/vidscope/adapters/heuristic/analyzer.py`
- `src/vidscope/adapters/heuristic/stub.py`
- `src/vidscope/adapters/heuristic/stopwords.py`
- `tests/unit/adapters/heuristic/test_analyzer.py`
