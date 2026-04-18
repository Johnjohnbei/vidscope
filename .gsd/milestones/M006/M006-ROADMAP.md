# M006 — Creator as first-class entity

## Vision
Today `videos.author` is a flat denormalised string. M006 introduces a `Creator` domain entity with its own table, FK from `videos`, and CLI/MCP surfaces. Every subsequent milestone (M007 mentions attribution, M009 creator-level velocity, M011 collections-by-creator) depends on this foundation. yt-dlp already exposes `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail` — zero new external deps. Backward-compat migration: `videos.author` kept as read-only cache, new `videos.creator_id` FK populated at ingest, backfill script covers existing rows.

## Slice Overview

| ID | Slice | Risk | Depends | Done when |
|----|-------|------|---------|-----------|
| S01 | Domain entity + port + SQLite adapter + migration | low | — | `Creator` frozen dataclass, `CreatorRepository` Protocol, `SqlCreatorRepository`, migration 003_creators, Container wires repo, backfill script migrates existing `videos.author` → `creators` rows, 9 import-linter contracts green. |
| S02 | Ingest stage populates creator before video row | medium | S01 | `YtdlpDownloader` returns `creator_info` in `DownloadResult`, `IngestStage` upserts creator then sets `video.creator_id`, idempotent re-ingest reuses creator row, typed error when yt-dlp omits uploader. |
| S03 | CLI + MCP surfaces | low | S02 | `vidscope creator show <handle>`, `vidscope creator list [--platform] [--min-followers]`, `vidscope creator videos <handle>`, MCP tool `vidscope_get_creator`, `vidscope show <id>` and `vidscope list` display creator info inline. |

## Layer Architecture

| Slice | Layer | New/Changed files |
|-------|-------|-------------------|
| S01 | domain | `entities.py` (+Creator), `values.py` (+CreatorId, PlatformUserId) |
| S01 | ports | `creator_repository.py` (Protocol: find_by_platform_user_id, upsert, find_by_handle, list_by_platform) |
| S01 | adapters/sqlite | `creator_repository.py`, `migrations/003_creators.py`, `schema.py` (+creators table, +videos.creator_id FK) |
| S01 | infrastructure | `container.py` (+creator_repository wiring), `scripts/backfill_creators.py` |
| S02 | ports | `downloader.py` (+CreatorInfo typed dict in DownloadResult) |
| S02 | adapters/ytdlp | `ytdlp_downloader.py` (extract uploader_id/url/follower_count/thumbnail) |
| S02 | pipeline | `ingest_stage.py` (upsert creator → set video.creator_id) |
| S03 | application | `use_cases/get_creator.py`, `use_cases/list_creators.py`, `use_cases/list_creator_videos.py` |
| S03 | cli | `creators.py` (Typer sub-app) |
| S03 | mcp | `tools/creator.py` |

## Test Strategy

Every slice ships tests at **every layer it touches** before merge. No slice closes with < 80% line coverage on new modules.

| Test kind | Scope | Tooling |
|-----------|-------|---------|
| Domain unit | Creator entity immutability, equality, frozen-slots, value-object validation | pytest, pure Python, zero I/O |
| Adapter unit | SqlCreatorRepository CRUD, UNIQUE (platform, platform_user_id), FK cascade on video delete, migration up/down | pytest + tmp SQLite |
| Pipeline integration | IngestStage with stubbed Downloader returning CreatorInfo, verifies creator upsert + video.creator_id | pytest + in-memory container |
| Application unit | Use cases with InMemoryCreatorRepository | pytest |
| CLI snapshot | Typer CliRunner, assert stdout formatting | pytest |
| Architecture | All 9 import-linter contracts stay green | `lint-imports` in pytest |
| Type | mypy strict on new modules | `mypy --strict` |
| E2E live | `verify-m006.sh`: `vidscope add <real YouTube Short>` → `sqlite3` assert creators row + `vidscope creator show` returns populated data | bash + real network |
| Backfill | Run backfill script against fixture DB with N legacy videos, assert every row now has creator_id, no data lost | pytest |

## Requirements Mapping

- Closes R040 (creator entity), R041 (creator CLI & MCP tool), R042 (lossless backfill).
- Unblocks: M007 (mentions → creator link), M009 (creator-level velocity), M011 (creator facet in search).

## Out of Scope (explicit)

- No creator-authored clustering (ML) — pure metadata in M006.
- No avatar image download-and-store — we keep the `avatar_url` string only; image fetch is additive later if needed.
- No cross-platform identity resolution (same person on IG + TikTok) — M006 treats each platform handle as distinct.
