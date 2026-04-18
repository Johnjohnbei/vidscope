---
plan_id: S02-P02
phase: M007/S02
subsystem: adapters/text
tags: [url-normalization, regex-extraction, link-extractor, import-linter, corpus-gate]
dependency_graph:
  requires: [S02-P01]
  provides: [vidscope.adapters.text, normalize_url, RegexLinkExtractor, text-adapter-is-self-contained contract]
  affects: [S03-pipeline-wiring, S04-cli-mcp]
tech_stack:
  added: []
  patterns: [two-pass regex extraction, span-overlap deduplication, TLD allowlist, corpus quality gate]
key_files:
  created:
    - src/vidscope/adapters/text/__init__.py
    - src/vidscope/adapters/text/url_normalizer.py
    - src/vidscope/adapters/text/regex_link_extractor.py
    - tests/fixtures/link_corpus.json
    - tests/unit/adapters/text/__init__.py
    - tests/unit/adapters/text/test_url_normalizer.py
    - tests/unit/adapters/text/test_regex_link_extractor.py
  modified:
    - .importlinter
    - tests/architecture/test_layering.py
decisions:
  - Email addresses excluded from bare-domain pass via (?<![\w@]) lookbehind
  - Span-overlap deduplication prevents capturing sub-domain tails of scheme-explicit URLs
  - Root slash "/" stripped only when no query string is present (preserves "/?param=val")
  - Import inside extract() method moved to module level via urllib.parse (removed inline import)
metrics:
  duration: ~35min
  completed: "2026-04-18T10:18:17Z"
  tasks: 3
  files_created: 7
  files_modified: 2
  tests_added: 36
---

# Phase M007 Plan S02-P02: Text Adapter + Regex LinkExtractor + Import-Linter Contract Summary

**One-liner:** Two-pass regex URL extractor with 103-entry corpus gate + pure-Python URLNormalizer (stdlib only) + `text-adapter-is-self-contained` import-linter contract (10th contract, all green).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| T01 | URLNormalizer pure-Python + text adapter package | 3618779 | `adapters/text/__init__.py`, `url_normalizer.py`, `test_url_normalizer.py` |
| T02 | RegexLinkExtractor + corpus 103 strings (gate non-négociable) | 32f3be9 | `regex_link_extractor.py`, `link_corpus.json`, `test_regex_link_extractor.py` |
| T03 | Import-linter contract text-adapter-is-self-contained | 0f6c1f3 | `.importlinter`, `test_layering.py` |

## What Was Built

### `normalize_url` (pure stdlib)

Normalization rules applied in order:
1. Prepend `https://` when no scheme present (bare domain support)
2. Lowercase scheme + host (path case preserved)
3. Strip fragment (`#...`)
4. Filter `utm_*` params (case-insensitive)
5. Sort remaining query params alphabetically
6. Strip trailing slash from path — only when no query string (preserves `/?a=1`)

Idempotent: `normalize_url(normalize_url(x)) == normalize_url(x)` for all inputs. Never raises.

### `RegexLinkExtractor`

Two-pass strategy:
- **Pass 1 (scheme-explicit):** `https?://[^\s<>"'...]+ ` — high precision, matches the vast majority of URLs in captions/descriptions.
- **Pass 2 (bare-domain):** restricted TLD allowlist (`com`, `net`, `org`, `io`, `co`, `fr`, `uk`, `de`, `app`, `dev`, `ly`, `gg`, `tv`, `me`, `ai`, `tech`, `shop`, `store`, `xyz`, `link`, `page`) to avoid false positives.

Deduplication by `normalized_url` + span-overlap tracking (Pass 2 skips any match whose character span falls within a Pass 1 match).

### Corpus `link_corpus.json`

103 entries total: **51 positive** + **32 negative** + **20 edge**.

Quality gate: `TestLinkCorpus.test_positive_corpus`, `test_negative_corpus`, `test_edge_corpus` — each iterates the full corpus and compares `{normalize_url(u) for u in expected_urls}` vs actual extracted normalized URLs.

### Import-linter (10th contract)

`text-adapter-is-self-contained` forbids `adapters/text` from importing any other adapter, infrastructure, application, pipeline, cli, or mcp module. Reciprocal forbids added to `sqlite`, `fs`, and `llm` contracts. All 10 contracts KEPT.

## Test Results

- `tests/unit/adapters/text/`: **36 passed** (16 url_normalizer + 17 extractor basics + 3 corpus gate)
- `tests/architecture/test_layering.py`: **3 passed** (all 10 contracts verified)
- Full suite: **835 passed**, 0 regressions
- `mypy src`: Success (96 files)
- `lint-imports`: 10 kept, 0 broken

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Email false-positive in bare-domain regex**
- **Found during:** T02 corpus verification
- **Issue:** `firstname.lastname@email.com` was extracting `https://email.com` as a bare-domain match because `@` is not a `\w` character, so the `(?<!\w)` lookbehind did not block the match on `email.com`.
- **Fix:** Changed lookbehind from `(?<!\w)` to `(?<![\w@])` — the `@` in the exclusion class blocks matches preceded by an email local-part.
- **Files modified:** `src/vidscope/adapters/text/regex_link_extractor.py`
- **Commit:** 32f3be9

**2. [Rule 1 - Bug] Double-capture of sub-domain tails as bare-domain URLs**
- **Found during:** T02 corpus verification
- **Issue:** `https://docs.python.org/3/` correctly matched by Pass 1, but `python.org/3` was also matched by Pass 2 (host `python.org` ≠ `docs.python.org`, so host-dedup did not prevent it). Similarly for `https://sub.example.com/page` extracting both the full URL and `example.com/page`.
- **Fix:** Replaced host-set dedup with span-overlap tracking. Pass 2 skips any match whose `(start, end)` character span falls entirely within a Pass 1 match span.
- **Files modified:** `src/vidscope/adapters/text/regex_link_extractor.py`
- **Commit:** 32f3be9

**3. [Rule 1 - Bug] Root slash `/` incorrectly stripped when query string present**
- **Found during:** T01 test run
- **Issue:** `normalize_url("https://example.com/?b=2&a=1")` returned `https://example.com?a=1&b=2` (missing `/?`) instead of `https://example.com/?a=1&b=2`.
- **Fix:** Strip root `/` only when the filtered query string is empty; when a query string is present, preserve `/` as the path component.
- **Files modified:** `src/vidscope/adapters/text/url_normalizer.py`
- **Commit:** 3618779

**4. [Rule 2 - Missing functionality] Architecture test EXPECTED_CONTRACTS incomplete**
- **Found during:** T03
- **Issue:** `test_layering.py` EXPECTED_CONTRACTS did not include `llm adapter does not import other adapters` (contract existed in `.importlinter` but was not verified by the test). Also missing the 2 renamed contracts and the new 10th contract.
- **Fix:** Updated EXPECTED_CONTRACTS to list all 10 contract names explicitly (was 8, now 10).
- **Files modified:** `tests/architecture/test_layering.py`
- **Commit:** 0f6c1f3

## Known Stubs

None — `RegexLinkExtractor.extract()` is fully implemented and all corpus entries are active (no `skip_reason`).

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. `adapters/text` is pure in-process text processing (no I/O, no DB).

## Self-Check: PASSED

All 10 key files confirmed present on disk. All 3 task commits (3618779, 32f3be9, 0f6c1f3) confirmed in git log.
