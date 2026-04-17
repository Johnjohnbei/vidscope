# Phase M006/S01: Creator domain entity + SQLite adapter + migration — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in S01-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** M006/S01 — Creator domain entity + SQLite adapter + migration
**Areas discussed:** Identity key, Backfill strategy, videos.author fate, follower_count + avatar storage

---

## Gray area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Clé d'identité Creator | Which UNIQUE pair for creators table | ✓ |
| Backfill des vidéos M001-M005 | Strategy for legacy rows without creator_id | ✓ |
| Fate de videos.author | Keep / drop / computed | ✓ |
| Follower count + avatar storage | Current value vs time-series; URL vs cached image | ✓ |
| Vérification likes/resends pour viralité (user free-text) | — | ⚠ redirected as scope creep (M009) |

---

## Identity key

| Option | Description | Selected |
|--------|-------------|----------|
| (platform, platform_user_id) UNIQUE | Stable yt-dlp uploader_id, surrogate id, handle non-unique | ✓ |
| (platform, handle) UNIQUE | Human-friendly but breaks on rename | |
| Double UNIQUE | Two constraints, conflict on rename | |
| Business key as PK (no surrogate) | Breaks pattern of 5 existing repos | |

**User's choice:** (platform, platform_user_id) UNIQUE, surrogate id kept.
**Notes:** Matches D005/D006. Handle column exists but is non-unique — supports renames without data loss.

---

## Backfill strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Re-probe yt-dlp via Downloader.probe() | Network cost, precise data, reuses M005 method | ✓ |
| Placeholder is_legacy=true creator | No network, but loses M006's value for history | |
| Leave creator_id NULL, manual re-ingest | Breaks R042 (lossless) | |
| Hybrid placeholder + lazy probe | Complex, mixes two execution paths | |

**User's choice:** Re-probe yt-dlp via `Downloader.probe()`.
**Notes:** Mandatory `--dry-run` default; `--apply` required for mutation. 404s produce `is_orphan=true` creators so every video still gets a FK populated — R042 (lossless backfill) holds.

---

## videos.author fate

| Option | Description | Selected |
|--------|-------------|----------|
| Preserved as write-through cache | Legacy SQL + FTS5 index stay valid, repo owns sync | ✓ |
| Dropped in S01 migration | High risk: breaks external queries, FTS5 rebuild, relies on 100% backfill | |
| Dropped in S03 after validation | Two migrations, defers debt | |
| Transformed into SQL VIEW | Breaks direct UPDATE, complex for little gain | |

**User's choice:** Preserved as denormalised cache.
**Notes:** Sync is repository-layer responsibility. Application code never writes `videos.author` directly. Regression test required: updating `creator.display_name` + re-upserting video propagates to `videos.author`.

---

## Follower count model

| Option | Description | Selected |
|--------|-------------|----------|
| Scalar on creators.follower_count | Simple; M009 adds creator_stats time-series later if needed | ✓ |
| creator_stats time-series in M006 | Premature; scope creep; duplicates M009 design | |
| Hybrid scalar + shadow-write | Double-write complexity without immediate value | |

**User's choice:** Scalar on creators only.
**Notes:** Clean separation — M006 is identity cleanup, M009 owns temporal analytics. D031 (append-only stats) remains M009's concern.

---

## Avatar storage

| Option | Description | Selected |
|--------|-------------|----------|
| avatar_url string only | Zero cost, respects D010 | ✓ |
| Download + cache via MediaStorage | Resilient to profile privacy change but adds I/O on ingestion | |
| Lazy: URL default, download on CLI display | Mixes two paths | |

**User's choice:** avatar_url string only.
**Notes:** Acceptable risk: profile privatisation may 404 the URL, recoverable via re-probe.

---

## Claude's Discretion

- SQLAlchemy Core column types — follow existing adapter conventions.
- `CreatorRepository` Protocol method naming (idiomatic).
- `InMemoryCreatorRepository` test helper shape — built as needed for coverage target.
- Exact dry-run output wording in backfill script.

## Deferred Ideas

- **Creator-level virality / velocity** — M009 scope (already planned).
- **Avatar image cache** — additive milestone if URL 404s become painful.
- **Cross-platform identity resolution** — out of M006 entirely.
- **Creator clustering / niche detection** — M010 at earliest.
