---
phase: M010
plan: S04
subsystem: application+cli
tags: [use-case, cli, facet-search, explain, sql-parameterized]
dependency_graph:
  requires: [M010-S01]
  provides: [ExplainAnalysisUseCase, SearchVideosUseCase, vidscope-explain, vidscope-search-M010]
  affects: [cli, application, ports, adapters/sqlite]
tech_stack:
  added: []
  patterns: [frozen-dataclass-DTO, parameterized-SQL-via-SQLAlchemy-Core, Typer-Annotated, BadParameter-defensive-parsing]
key_files:
  created:
    - src/vidscope/application/explain_analysis.py
    - src/vidscope/application/search_videos.py
    - src/vidscope/cli/commands/explain.py
    - tests/unit/application/test_explain_analysis.py
    - tests/unit/application/test_search_videos.py
    - tests/unit/cli/test_explain.py
  modified:
    - src/vidscope/ports/repositories.py
    - src/vidscope/adapters/sqlite/analysis_repository.py
    - src/vidscope/application/__init__.py
    - src/vidscope/cli/commands/__init__.py
    - src/vidscope/cli/commands/search.py
    - src/vidscope/cli/app.py
    - tests/unit/adapters/sqlite/test_analysis_repository.py
    - tests/unit/cli/test_search_cmd.py
    - tests/unit/cli/test_app.py
decisions:
  - "list_by_filters uses max(id) subquery (not created_at) for latest-analysis detection -- AUTOINCREMENT guarantees newer rows have larger ids"
  - "SearchVideosUseCase keeps FTS5 passthrough when filters.is_empty() -- zero overhead for unfiltered queries"
  - "search.py keeps SearchLibraryUseCase import for backward-compat with existing test patches"
  - "sponsored CLI flag is str (not bool) to avoid Typer bool option limitations -- parsed defensively via _parse_sponsored"
metrics:
  duration: "~45 minutes"
  completed: "2026-04-18"
  tasks_completed: 3
  files_modified: 14
requirements: [R053, R055]
---

# Phase M010 Plan S04: ExplainAnalysis + SearchVideos facets + CLI Summary

One-liner: ExplainAnalysisUseCase + SearchVideosUseCase with SQL-parameterized facet filters + `vidscope explain` command + M010 facets on `vidscope search`.

## What Was Built

### Task 1: `AnalysisRepository.list_by_filters` (port + SQLite impl)

**Port signature** (`src/vidscope/ports/repositories.py`):

```python
def list_by_filters(
    self,
    *,
    content_type: ContentType | None = None,
    min_actionability: float | None = None,
    is_sponsored: bool | None = None,
    limit: int = 1000,
) -> list[VideoId]: ...
```

**Filter semantics (NULL excluded everywhere):**
- `content_type`: latest analysis.content_type == enum.value. NULL stored values excluded.
- `min_actionability`: latest analysis.actionability IS NOT NULL AND >= float. NULL excluded.
- `is_sponsored`: strict bool equality. NULL excluded (unknown != False).
- All filters are AND-combined. None = ignored.
- Videos with no analysis row are excluded from results.

**SQLite implementation** (`src/vidscope/adapters/sqlite/analysis_repository.py`):
- Uses `GROUP BY video_id` + `max(id)` subquery (AUTOINCREMENT guarantees latest = max id)
- All values bound via SQLAlchemy Core operators (`col == value`) -- no string interpolation
- 9 tests: per-filter, combined AND, latest-wins, SQL-injection-safe, limit

### Task 2: Use Cases

**`ExplainAnalysisUseCase.execute(video_id: int) -> ExplainAnalysisResult`**
- `found=False` when no video matches the id
- `found=True, analysis=None` when video exists but no analysis yet
- `found=True, video=..., analysis=...` happy path

**`ExplainAnalysisResult`** (frozen dataclass, slots=True):
```python
found: bool
video: Video | None = None
analysis: Analysis | None = None
```

**`SearchVideosUseCase.execute(query, *, limit=20, filters=None) -> SearchLibraryResult`**
- `filters=None` or `SearchFilters()` (all None) -> pure FTS5 passthrough (V1 behavior preserved)
- With filters: calls `uow.analyses.list_by_filters(...)` to get allowed video_ids, then filters FTS5 hits
- Oversamples FTS5 by 5x to compensate for filtering before truncating to `limit`

**`SearchFilters`** (frozen dataclass, slots=True):
```python
content_type: ContentType | None = None
min_actionability: float | None = None
is_sponsored: bool | None = None
```

**application-has-no-adapters KEPT**: no infrastructure/adapter imports in application layer.

### Task 3: CLI

**`vidscope explain <id>`**
- Exit 0: shows Panel(reasoning) + 5 scores (overall, information_density, actionability, novelty, production_quality) + categorical fields (content_type, sentiment, is_sponsored) + verticals + keywords
- Exit 1: "no video with id N" when video not found
- Exit 1: "no analysis yet for video N -- run vidscope add again" when video has no analysis
- ASCII-only output (no unicode glyphs -- Windows cp1252 compat)

**`vidscope search` extended with M010 facets:**
- `--content-type TYPE`: restricted to ContentType enum values (tutorial, review, vlog, news, story, opinion, comedy, educational, promo, unknown). BadParameter on invalid value.
- `--min-actionability N`: Typer validates `min=0, max=100`. BadParameter on out-of-range.
- `--sponsored true|false`: strict parsing (true/yes/1 or false/no/0). BadParameter otherwise.

**Typer validation examples:**
```
vidscope search "x" --content-type podcast    -> exit 2, BadParameter
vidscope search "x" --min-actionability -10   -> exit 2, Typer range error
vidscope search "x" --sponsored maybe         -> exit 2, BadParameter
```

**`vidscope --help`** lists `explain` command.

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1 | 9801410 | feat(M010-S04): Task 1 -- AnalysisRepository.list_by_filters (port + SQLite impl) + 9 tests |
| Task 2 | 613db6c | feat(M010-S04): Task 2 -- ExplainAnalysisUseCase + SearchVideosUseCase + SearchFilters |
| Task 3 | f112202 | feat(M010-S04): Task 3 -- vidscope explain + search M010 facets + CLI registration |

## Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| `TestListByFilters` (sqlite adapter) | 9 | GREEN |
| `test_explain_analysis.py` | 3 | GREEN |
| `test_search_videos.py` | 9 | GREEN |
| `test_explain.py` (CLI) | 5 | GREEN |
| `TestSearchM010Facets` (CLI) | 9 | GREEN |
| `test_app_help_lists_explain_command` | 1 | GREEN |
| **Total S04** | **36** | **GREEN** |

Pre-existing test failures (hors scope S04): 9 tests in `TestSearchFacetOptions` and `TestOnScreenTextFlag` were already failing before S04 (--hashtag, --mention, --has-link, --on-screen-text options not implemented). These remain in the same state.

## Deviations from Plan

### Auto-fixed Issues

None -- plan executed exactly as written.

### Pre-existing Issues (out of scope, deferred)

9 tests in `test_search_cmd.py` (`TestSearchFacetOptions`, `TestOnScreenTextFlag`) were already failing before S04 began (exit code 2 for unknown options). These test features (--hashtag, --mention, --has-link, --on-screen-text) that do not exist in the codebase. Documented in deferred-items.md for future milestones.

Pre-existing collection errors (hors scope): Creator, FrameText, VisualIntelligenceStage modules referenced in tests but not yet implemented.

## Known Stubs

None. All data flows are wired:
- `ExplainAnalysisUseCase` reads from real repository via UoW
- `SearchVideosUseCase` calls real `list_by_filters` + FTS5
- CLI commands render all fields, no placeholder text

## Threat Flags

No new trust boundaries introduced beyond those analyzed in the plan's threat model. All CLI inputs are validated via Typer constraints + defensive parsing before reaching SQL layer.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `src/vidscope/application/explain_analysis.py` | FOUND |
| `src/vidscope/application/search_videos.py` | FOUND |
| `src/vidscope/cli/commands/explain.py` | FOUND |
| `.gsd/milestones/M010/M010-S04-SUMMARY.md` | FOUND |
| commit 9801410 | FOUND |
| commit 613db6c | FOUND |
| commit f112202 | FOUND |
