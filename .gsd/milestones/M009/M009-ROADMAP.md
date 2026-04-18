# M009 — Engagement signals + velocity tracking

## Vision
Current `videos.view_count` is a single snapshot from the first ingest. Velocity and engagement — the actual signal for "this is trending" — are invisible. M009 introduces a **time-series** table `video_stats` appended every time a refresh probes the URL. Derived metrics (`views_velocity_24h`, `engagement_rate`, `viral_coefficient`) are computed on read. Existing `vidscope watch refresh` is extended to re-probe stats on already-ingested videos (metadata-only call, no media re-download). New `vidscope trending --since <window>` ranks by velocity. D031 pins the append-only contract.

## Slice Overview

| ID | Slice | Risk | Depends | Done when |
|----|-------|------|---------|-----------|
| S01 | Domain + time-series table + StatsProbe port | medium | M006/S01 | `VideoStats` entity, `StatsProbe` Protocol, `YtdlpStatsProbe` adapter (uses `extract_info(download=False)`), `video_stats` table append-only, migration 008, Container wiring. |
| S02 | StatsStage + refresh-stats CLI | medium | S01 | New `StatsStage` runnable standalone (outside default add-pipeline graph), `vidscope refresh-stats <id|--all|--since>` command, idempotent per (video_id, captured_at) bucket. |
| S03 | Watch-refresh integration | low | S02 | `vidscope watch refresh` extended: for every known video of watched creators, run StatsStage; reports "N new videos + M refreshed stats"; per-video error isolation. |
| S04 | Derived metrics + trending CLI | low | S01 | Pure-Python `metrics.py` computes velocity/engagement from `video_stats` history, `vidscope trending --since 7d [--platform] [--min-velocity]` ranks, MCP tool `vidscope_trending`. |

## Layer Architecture

| Slice | Layer | New/Changed files |
|-------|-------|-------------------|
| S01 | domain | `entities.py` (+VideoStats with captured_at, view/like/comment/share/save counts), `metrics.py` **new pure-domain module** (velocity, engagement_rate) |
| S01 | ports | `stats_probe.py` (Protocol), `video_stats_repository.py` |
| S01 | adapters/ytdlp | `ytdlp_stats_probe.py` **new** (leverages existing `probe` helper from M005 — extract_info download=False) |
| S01 | adapters/sqlite | `video_stats_repository.py`, `migrations/008_video_stats.py`, index on (video_id, captured_at) |
| S02 | pipeline | `stats_stage.py` **new**, registered in Container but *not* in default `add` graph |
| S02 | application | `use_cases/refresh_stats.py` |
| S02 | cli | `stats.py` **new** (`vidscope refresh-stats`) |
| S03 | application | `use_cases/refresh_watchlist.py` (extend with stats refresh loop) |
| S03 | cli | `watch.py` (extended summary output) |
| S04 | application | `use_cases/list_trending.py` |
| S04 | cli | `trending.py` **new** |
| S04 | mcp | `tools/trending.py` |

## Test Strategy

| Test kind | Scope | Tooling |
|-----------|-------|---------|
| Domain unit | VideoStats immutability, metrics.velocity with various history shapes (empty, single point, linear, accelerating, decelerating, negative — e.g. deleted views) | pytest |
| Domain unit — edge cases | Zero-duration window, missing intermediate stat rows, overlapping buckets, timezone alignment (UTC canonicalisation) | pytest |
| Adapter unit — probe | YtdlpStatsProbe with stubbed yt_dlp.YoutubeDL, verify `download=False` is forced, verify return shape | pytest |
| Adapter unit — repo | Append-only invariant: repo rejects UPDATE on existing row, INSERT always creates new | pytest |
| Pipeline integration | StatsStage with stub probe, verify video_stats row appended + pipeline_runs row + is_satisfied honoured (no duplicate within bucket) | pytest |
| Application unit | refresh_stats with InMemory probe+repo, list_trending ranking correctness | pytest |
| CLI snapshot | `vidscope refresh-stats --all`, `vidscope trending --since 7d` | CliRunner |
| Integration — watchlist | `vidscope watch refresh` summary shows both new-videos and stats-refresh counters, per-video error isolation verified | pytest |
| Architecture | 9 contracts green + metrics.py in domain layer with zero imports | lint-imports |
| E2E live | `verify-m009.sh`: `vidscope add <YouTube Short>` → wait 60s → `vidscope refresh-stats <id>` → assert video_stats has 2 rows, velocity computed | bash + real network |

### Time-series correctness gate
S01 ships a `test_metrics_property.py` using Hypothesis that asserts velocity monotonicity, additivity, and zero-bug on edge windows. Blocks merge if any property fails.

## Requirements Mapping

- Closes R050 (time-series `video_stats`), R051 (refresh-stats + watchlist extension), R052 (`vidscope trending`).
- Decision D031 (append-only) documented and enforced structurally by adapter tests.

## Out of Scope (explicit)

- No scheduler built-in — users already use cron/Task Scheduler (M003). `vidscope refresh-stats --all` is the command they wrap.
- No push notifications when trending crosses threshold — additive surface later.
- No historical backfill from scraped third-party analytics — we only have our own observations.
- No per-comment sentiment — comments aren't downloaded at all in M009 (only counts).
