---
phase: M009-engagement-signals-velocity-tracking
reviewed: 2026-04-18T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/vidscope/domain/metrics.py
  - src/vidscope/ports/stats_probe.py
  - src/vidscope/adapters/sqlite/video_stats_repository.py
  - src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py
  - src/vidscope/pipeline/stages/stats_stage.py
  - src/vidscope/application/refresh_stats.py
  - src/vidscope/application/list_trending.py
  - src/vidscope/cli/commands/stats.py
  - src/vidscope/cli/commands/trending.py
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# M009: Code Review Report

**Reviewed:** 2026-04-18
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

M009 introduces append-only engagement-counter snapshots, velocity/engagement
metrics, batch stats refresh, and a `vidscope trending` CLI command. The
hexagonal layer boundaries are correctly respected: no infrastructure imports
appear in domain, ports, application, or pipeline layers. SQLAlchemy Core
parameterised statements are used consistently; no raw string interpolation was
found. The `_int_or_none` helper in the yt-dlp adapter properly defends against
type-confusion from malicious API responses.

Four warnings were found, all correctness issues that can produce silent
wrong results or silently discard data under specific edge conditions. No
critical security issues were identified.

---

## Warnings

### WR-01: `append()` silently returns the *latest* row instead of the conflict row on duplicate insert

**File:** `src/vidscope/adapters/sqlite/video_stats_repository.py:62-71`

**Issue:** When `ON CONFLICT DO NOTHING` fires (a duplicate `(video_id,
captured_at)` already exists), `append()` calls `latest_for_video()` and then
scans `_rows_for_video()` looking for a row whose `captured_at` equals
`stats.captured_at`. In practice `latest_for_video()` returns the *most-recent*
snapshot by `captured_at DESC`, which may not be the conflicting row if a newer
snapshot has already been inserted between the two calls. When `captured_at`
equality is not found among the rows, the fallback at line 71 returns the
*input* entity with `id=None` — meaning the caller receives an entity that
looks unsaved and whose `id` is `None`. Any caller that uses the returned
`id` (e.g., to link a follow-up record) will silently propagate `None`.

```python
# Current code (lines 62-71)
existing = self.latest_for_video(stats.video_id)
if existing is not None:
    for row in self._rows_for_video(stats.video_id):
        entity = _row_to_entity(row)
        if entity.captured_at == stats.captured_at:
            return entity
return stats   # <-- returns id=None when conflict row is not found
```

**Fix:** Query the conflict row directly by the unique key pair instead of
scanning all rows and hoping for a match:

```python
def append(self, stats: VideoStats) -> VideoStats:
    payload = _entity_to_row(stats)
    stmt = (
        sqlite_insert(video_stats_table)
        .values(**payload)
        .on_conflict_do_nothing(index_elements=["video_id", "captured_at"])
    )
    self._conn.execute(stmt)

    # Fetch the row by its unique key — covers both insert and conflict cases.
    fetch_stmt = (
        select(video_stats_table)
        .where(video_stats_table.c.video_id == int(stats.video_id))
        .where(video_stats_table.c.captured_at == stats.captured_at)
        .limit(1)
    )
    row = self._conn.execute(fetch_stmt).mappings().first()
    if row is not None:
        return _row_to_entity(dict(row))
    return stats  # defensive only; should never reach here
```

---

### WR-02: `views_velocity_24h` imports `timedelta` inside the function body on every call

**File:** `src/vidscope/domain/metrics.py:63`

**Issue:** `from datetime import timedelta` is executed inside
`views_velocity_24h()` at line 63 on every invocation. This is an unintentional
pattern — the top-level `from __future__ import annotations` is already present,
and `timedelta` is part of stdlib. While Python caches module imports and the
runtime overhead is negligible, placing an import inside a function body that
is called in a hot loop (once per candidate video in `ListTrendingUseCase`)
obscures the module's actual dependencies and violates the project's convention
of top-level stdlib imports.

```python
# Line 63 — inside the function body
from datetime import timedelta
```

**Fix:** Move to the top of the file alongside the other stdlib imports:

```python
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
```

---

### WR-03: `_parse_since` in `stats.py` accepts multi-digit numbers only when every char before the suffix is a digit — leading zeros pass silently

**File:** `src/vidscope/cli/commands/stats.py:47`

**Issue:** The guard `not s[:-1].isdigit()` rejects non-digit prefixes but
accepts `"007d"` (leading zeros) and `"0h"` silently because `"007".isdigit()`
is `True`. The `n <= 0` check on line 53 catches `n=0` but not `"007"` which
parses as `7` and passes. This is the same pattern duplicated in
`trending.py:44`. The issue is minor in isolation but is inconsistent with
the stated strict-parser goal (T-INPUT-02) and the symmetric `_parse_window`
in `trending.py` has the same flaw — a single shared validator would eliminate
the duplication and the inconsistency at once.

```python
# stats.py line 47
if len(s) < 2 or not s[:-1].isdigit():
    ...
n = int(s[:-1])   # "007" -> 7, no rejection of leading zeros
```

**Fix:** Add an explicit check for leading zeros, or consolidate the two
nearly-identical parsers into a shared utility in `vidscope.cli._support`:

```python
def _parse_time_window(raw: str | None, *, allow_none: bool = False) -> timedelta | None:
    if raw is None or not raw.strip():
        if allow_none:
            return None
        raise typer.BadParameter("--since is required")
    s = raw.strip().lower()
    digits, unit = s[:-1], s[-1]
    if not digits or not digits.isdigit() or digits != str(int(digits)):
        raise typer.BadParameter(
            f"invalid --since window: {raw!r} (expected N(h|d), e.g. 7d or 24h)"
        )
    n = int(digits)
    if n <= 0:
        raise typer.BadParameter(f"--since must be positive, got {raw!r}")
    if unit == "h":
        return timedelta(hours=n)
    if unit == "d":
        return timedelta(days=n)
    raise typer.BadParameter(
        f"invalid --since unit: {unit!r} (expected 'h' or 'd')"
    )
```

---

### WR-04: `ListTrendingUseCase` has an N+1 query pattern inside the candidate loop

**File:** `src/vidscope/application/list_trending.py:118-129`

**Issue:** For each `vid` in `candidate_ids` the loop issues two separate
queries: `uow.video_stats.list_for_video(vid)` (line 119) and
`uow.videos.get(vid)` (line 127). With the default candidate limit of
`max(limit * 5, 100) = 100` candidates this is up to 200 round-trips inside
a single UoW transaction. SQLite with a local file is fast, so this is not
a crash risk, but it is the principal scalability bottleneck for the trending
command and is O(K) queries where K is the candidate cap — not O(1).

This is highlighted here because the code comment at line 110 explicitly
describes the scalability rationale ("SQL GROUP BY ... O(K) where K is the
candidate limit") while the inner loop actually issues 2K queries. The
comments and the implementation are inconsistent, which may mislead future
maintainers.

```python
# list_trending.py lines 117-141
for vid in candidate_ids:               # up to 100 candidates
    history = uow.video_stats.list_for_video(vid, limit=1000)  # query 1
    ...
    video = uow.videos.get(vid)         # query 2 — N+1 here
```

**Fix (short-term):** Add a `list_by_ids(video_ids)` method to
`VideoRepository` that fetches all needed `Video` rows in a single `WHERE id
IN (...)` query before the loop:

```python
video_map = {v.id: v for v in uow.videos.list_by_ids(list(candidate_ids))}

for vid in candidate_ids:
    history = uow.video_stats.list_for_video(vid, limit=1000)
    ...
    video = video_map.get(vid)
    if video is None:
        continue
    entries.append(...)
```

The `video_stats` history queries are harder to batch because each video's
history is variable-length; the `videos` fetch is the lowest-cost fix.

---

## Info

### IN-01: `engagement_rate` treats all-None counters as `0.0` not `None`

**File:** `src/vidscope/domain/metrics.py:111-117`

**Issue:** When all four engagement counters (`like_count`, `comment_count`,
`repost_count`, `save_count`) are `None`, `likes + comments + reposts + saves`
evaluates to `0`, and the function returns `0.0 / view_count = 0.0`. Per
design rule D-03 ("None is NOT 0"), returning `0.0` when there is no
engagement data is semantically different from returning `0.0` when all
engagement counters are genuinely zero. The docstring says `None` is returned
"when all engagement counters are None" but the code does not implement that
case.

```python
# Lines 111-117
likes = stats.like_count or 0       # None -> 0
comments = stats.comment_count or 0
reposts = stats.repost_count or 0
saves = stats.save_count or 0
numerator = likes + comments + reposts + saves
return numerator / stats.view_count  # returns 0.0 even when all are None
```

**Fix:** Add the all-None guard described in the docstring:

```python
if (
    stats.like_count is None
    and stats.comment_count is None
    and stats.repost_count is None
    and stats.save_count is None
):
    return None

likes = stats.like_count or 0
...
```

---

### IN-02: `StatsStage.execute` error message leaks the raw source URL

**File:** `src/vidscope/pipeline/stages/stats_stage.py:83-85`

**Issue:** When the probe returns `None`, the `DomainError` raised at line 83
includes `ctx.source_url` verbatim in the message string:

```python
raise DomainError(
    f"stats probe returned no data for {ctx.source_url}",
    stage=StageName.STATS,
)
```

This string is propagated all the way to the CLI via `RefreshStatsResult.message`
and printed to the user's terminal. For batch runs the full list of messages
can be serialised to logs. A URL can contain OAuth tokens, session IDs, or
private-key query parameters depending on the platform. The risk is low for
public video URLs, but it is a pattern that violates the principle of not
leaking internal details through error messages (project rule: "Error messages
must not leak internal details").

**Fix:** Sanitise or truncate the URL in the error message:

```python
from urllib.parse import urlparse

safe_url = urlparse(ctx.source_url)._replace(query="", fragment="").geturl()
raise DomainError(
    f"stats probe returned no data for {safe_url}",
    stage=StageName.STATS,
)
```

---

### IN-03: `_rows_for_video` helper has no `limit` and fetches unbounded rows

**File:** `src/vidscope/adapters/sqlite/video_stats_repository.py:184-191`

**Issue:** `_rows_for_video` is called from `append()` to find the conflict
row (see WR-01). It issues `SELECT * FROM video_stats WHERE video_id = ?` with
no `LIMIT`. If a video has thousands of snapshots this fetches every row into
memory even though `append()` only needs to match `captured_at == stats.captured_at`.
This method would become a correctness risk once the WR-01 fix is applied (the
entire method is no longer needed after that fix), but if it is kept for other
callers the unbounded scan should be documented.

**Fix:** Apply the WR-01 fix and remove `_rows_for_video`, or add an explicit
`LIMIT` and a docstring warning about the unbounded scan:

```python
def _rows_for_video(self, video_id: VideoId, *, limit: int = 1000) -> list[dict[str, Any]]:
    """Return raw rows for ``video_id`` ordered by captured_at asc.

    WARNING: no default limit cap. Callers must supply an appropriate limit.
    """
    stmt = (
        select(video_stats_table)
        .where(video_stats_table.c.video_id == int(video_id))
        .order_by(video_stats_table.c.captured_at.asc())
        .limit(limit)
    )
    return [dict(row) for row in self._conn.execute(stmt).mappings().all()]
```

---

### IN-04: `velocity` display in `trending.py` suppresses the value `0.0` in the table

**File:** `src/vidscope/cli/commands/trending.py:145-149`

**Issue:** The rendering block uses a falsy check to decide whether to format
the velocity:

```python
velocity = (
    f"{entry.views_velocity_24h:.1f}"
    if entry.views_velocity_24h        # falsy for 0.0!
    else "0.0"
)
```

Because `0.0` is falsy in Python, a video whose velocity is exactly `0.0`
renders as `"0.0"` via the else-branch rather than `f"{0.0:.1f}"` = `"0.0"` —
in this case the output is the same string, so there is no visible bug.
However, a very small positive velocity such as `0.00001` would be formatted
as `"0.0"` through the format branch, which truncates rather than rounds for
display. More importantly, if the type annotation is ever relaxed to
`float | None`, this pattern will mask `None` values that should render as
`"-"`. The explicit check is safer and clearer.

**Fix:**

```python
velocity = (
    f"{entry.views_velocity_24h:.1f}"
    if entry.views_velocity_24h is not None
    else "-"
)
```

---

### IN-05: Duplicate `_parse_window` / `_parse_since` logic across two CLI files

**File:** `src/vidscope/cli/commands/stats.py:33-61` and `src/vidscope/cli/commands/trending.py:31-58`

**Issue:** The two functions are structurally identical — same regexp-free digit
check, same unit dispatch, same error messages — with only the function name and
the `None`-return semantics differing. Any future change to the valid units
(e.g., adding `w` for weeks) must be applied in two places. This is a
maintainability smell rather than a correctness issue.

**Fix:** Extract a shared `_parse_time_window(raw: str | None, *, allow_none:
bool) -> timedelta | None` helper into `vidscope.cli._support` and have both
commands import from there. This also addresses WR-03 in a single location.

---

_Reviewed: 2026-04-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
