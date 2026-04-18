---
phase: M010
plan: S03
subsystem: llm-adapter
tags: [llm, parsing, m010, prompt-v2, make-analysis, defensive-parsing]
dependency_graph:
  requires: [M010-S01, M010-S02]
  provides: [M010-S03]
  affects: [groq, nvidia_build, openrouter, openai, anthropic]
tech_stack:
  added: []
  patterns:
    - defensive parsing (try/except ValueError → None)
    - clamping float to [0.0, 100.0]
    - StrEnum membership validation
    - frozenset lookup for bool coercion
key_files:
  created: []
  modified:
    - src/vidscope/adapters/llm/_base.py
    - tests/unit/adapters/llm/test_base.py
    - tests/unit/adapters/llm/test_groq.py
    - tests/unit/adapters/llm/test_nvidia_build.py
    - tests/unit/adapters/llm/test_openrouter.py
    - tests/unit/adapters/llm/test_openai.py
    - tests/unit/adapters/llm/test_anthropic.py
decisions:
  - "_parse_* helpers stay private — not in __all__, imported by tests via direct module access"
  - "domain/__init__.py and entities.py extended to export ContentType/SentimentLabel (Rule 3 — worktree was on old branch)"
metrics:
  duration_minutes: 42
  completed_at: "2026-04-18T18:17:57Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 7
  tests_added: 81
  tests_total: 187
---

# Phase M010 Plan S03: LLM adapter _base.py — Prompt V2 + make_analysis V2 Summary

**One-liner:** `_SYSTEM_PROMPT` V2 requests 13 JSON keys + 6 defensive `_parse_*` helpers extend `make_analysis` to populate all 9 M010 fields without raising on any LLM input.

## What Was Built

### Task 1: Prompt V2 + make_analysis V2 (TDD)

**`_SYSTEM_PROMPT` V2** now requests EXACTLY 13 keys (5 V1 preserved + 8 M010 new):

```
V1 preserved: language, keywords, topics, score, summary
M010 new: verticals, information_density, actionability, novelty,
          production_quality, sentiment, is_sponsored, content_type, reasoning
```

The prompt explicitly lists enum values for `sentiment` (positive/negative/neutral/mixed) and `content_type` (tutorial/review/vlog/news/story/opinion/comedy/educational/promo/unknown), and constrains numeric fields to integers in [0, 100].

**6 private helpers added to `_base.py`:**

| Helper | Signature | Defensive rule |
|--------|-----------|----------------|
| `_parse_score_100` | `(value: Any) -> float \| None` | NaN/non-numeric → None; clamp to [0.0, 100.0] |
| `_parse_sentiment` | `(value: Any) -> SentimentLabel \| None` | Unknown string → None (never ValueError) |
| `_parse_content_type` | `(value: Any) -> ContentType \| None` | Unknown string → None (never ValueError) |
| `_parse_bool_flag` | `(value: Any) -> bool \| None` | Accepts bool/int 0-1/truthy strings; anything else → None |
| `_parse_verticals` | `(value: Any, *, max_count: int = 5) -> tuple[str, ...]` | Non-list → (); normalises lowercase, deduplicates, caps at 5 |
| `_parse_reasoning` | `(value: Any) -> str \| None` | Empty/non-string → None; truncated at 500 chars + "..." |

**`make_analysis` V2 signature** (unchanged external interface):

```python
def make_analysis(
    parsed: dict[str, Any], transcript: Transcript, *, provider: str
) -> Analysis:
```

Internal change: now populates 9 additional fields using the helpers above. All 5 V1 fields (keywords, topics, score, summary, language) are preserved unchanged.

### Task 2: Provider integration tests (3 per provider × 5 providers = 15 tests)

Each provider test file received a `TestM010Extended*` class with 3 tests:
1. **happy_path_all_m010_fields** — MockTransport returns full M010 JSON; asserts all 9 fields populated
2. **partial_m010_fields** — MockTransport returns only 3 M010 fields; asserts they parse, others are None
3. **invalid_m010_values_safe** — MockTransport returns bogus enum values + non-numeric scores; asserts all → None, no exception

| Provider | Test class | Response format |
|----------|-----------|-----------------|
| groq | `TestM010ExtendedGroqJson` | OpenAI-compatible `choices[0].message.content` |
| nvidia_build | `TestM010ExtendedNvidiaJson` | Same |
| openrouter | `TestM010ExtendedOpenRouterJson` | Same |
| openai | `TestM010ExtendedOpenAIJson` | Same |
| anthropic | `TestM010ExtendedAnthropicJson` | Native `content[{type:text, text:...}]` |

**The 5 provider source files were NOT modified** — they delegate to `run_openai_compatible` (groq, nvidia, openrouter, openai) or `parse_llm_json` + `make_analysis` (anthropic). M004 design holds.

## Defensive Rules Applied

| Input scenario | Behaviour |
|---------------|-----------|
| Score = 150 | Clamped to 100.0 |
| Score = -5 | Clamped to 0.0 |
| Score = "75" (string) | Converted to 75.0 |
| Score = "bogus" | None |
| Score = NaN | None |
| `sentiment="joyful"` (not in enum) | None |
| `sentiment="NEGATIVE"` (uppercase) | SentimentLabel.NEGATIVE (case-insensitive) |
| `content_type="podcast"` (not in enum) | None |
| `is_sponsored=1` | True |
| `is_sponsored="false"` | False |
| `is_sponsored="maybe"` | None |
| `verticals="tech"` (string not list) | () |
| `verticals=["tech","TECH","ai"]` | ("tech", "ai") — deduped, lowercase |
| `reasoning=""` | None |
| `reasoning="x"*800` | Truncated at 500 chars + "..." |
| Missing field entirely | None / () |

## Test Summary

| File | V1 tests | M010 tests | Total |
|------|---------|-----------|-------|
| test_base.py | 34 | 72 | 106 |
| test_groq.py | ~28 | 3 | ~31 |
| test_nvidia_build.py | ~10 | 3 | ~13 |
| test_openrouter.py | ~11 | 3 | ~14 |
| test_openai.py | ~10 | 3 | ~13 |
| test_anthropic.py | ~7 | 3 | ~10 |
| **Total** | **~100** | **~87** | **187** |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] ContentType + SentimentLabel missing from worktree**

- **Found during:** Task 1, phase GREEN (ImportError on test collection)
- **Issue:** This worktree was based on an old branch (pre-S01). `src/vidscope/domain/values.py` did not contain `ContentType` or `SentimentLabel` enums. `src/vidscope/domain/entities.py` `Analysis` dataclass had no M010 fields. `src/vidscope/domain/__init__.py` did not export them.
- **Fix:** Added `ContentType` and `SentimentLabel` StrEnums to `values.py`; extended `Analysis` dataclass with all 9 M010 fields (defaults to None/()) in `entities.py`; added exports to `domain/__init__.py`. These are identical to the S01 deliverables already on `main`.
- **Files modified:** `src/vidscope/domain/values.py`, `src/vidscope/domain/entities.py`, `src/vidscope/domain/__init__.py`
- **Commit:** e7f126c (included in Task 1 commit)

## Known Stubs

None — all 9 M010 fields are fully wired from LLM JSON response through `make_analysis` into `Analysis`. No placeholder values or TODO markers.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced by S03. The `_parse_*` helpers address T-INPUT-01 through T-INPUT-04 from the plan's threat register:

- T-INPUT-01: `_parse_sentiment` / `_parse_content_type` use StrEnum membership check → arbitrary strings → None
- T-INPUT-02: `_parse_score_100` clamps via `min(100.0, max(0.0, float(x)))` — Python float, no overflow
- T-INPUT-04: `_parse_reasoning` truncates at 500 chars — no memory explosion

## Self-Check

- FOUND: src/vidscope/adapters/llm/_base.py
- FOUND: tests/unit/adapters/llm/test_base.py (106 tests)
- FOUND: tests/unit/adapters/llm/test_groq.py + 4 other providers
- FOUND: .gsd/milestones/M010/M010-S03-SUMMARY.md
- FOUND commit e7f126c (Task 1 — Prompt V2 + make_analysis V2)
- FOUND commit eef5c23 (Task 2 — provider M010 integration tests)
- 187 tests pass

**Self-Check: PASSED**
