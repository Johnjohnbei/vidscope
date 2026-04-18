# Phase M006/S02: Ingest stage populates creator — Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

S02 wires the live ingest pipeline to the creator foundation built in S01.
Every call to `IngestStage.execute()` now:
1. Extracts creator metadata from the yt-dlp `info_dict` (zero extra network call)
2. Upserts the `Creator` row via `uow.creators` (full upsert — refreshes all mutable fields)
3. Passes `creator` to `uow.videos.upsert_by_platform_id(video, creator=creator)` so `video.creator_id` and the D-03 write-through cache (`videos.author`) are set atomically
4. All three operations share a single UoW transaction — rollback on video upsert failure also rolls back the creator upsert

**Out of S02:**
- CLI `vidscope creator …` → S03
- MCP tool `vidscope_get_creator` → S03
- Backfill of pre-S01 rows → already delivered in S01 (`scripts/backfill_creators.py`)

</domain>

<decisions>
## Implementation Decisions

### D-01: CreatorInfo TypedDict in IngestOutcome
`YtdlpDownloader.download()` returns `IngestOutcome` (existing type). Add a new optional field:
```python
creator_info: "CreatorInfo | None"
```
where `CreatorInfo` is a `TypedDict` defined in `src/vidscope/ports/pipeline.py` alongside `IngestOutcome`.

Fields to extract from yt-dlp `info_dict` (same keys as S01's ProbeResult extension):
- `platform_user_id: str` (from `uploader_id`)
- `handle: str | None` (from `uploader` — may change on rename)
- `display_name: str | None` (from `uploader` — same field, stored as display_name too)
- `profile_url: str | None` (from `uploader_url`)
- `avatar_url: str | None` (from `uploader_thumbnail` — string or first item if list)
- `follower_count: int | None` (from `channel_follower_count`)
- `is_verified: bool | None` (from `uploader_verified` via private `_extract_uploader_verified`)

**No double-probe.** The `info_dict` is already available inside `download()` — extraction is pure dict access.

### D-02: Uploader absent → ingest succeeds with creator_id=NULL
If `uploader_id` is absent or empty in the `info_dict`, `YtdlpDownloader.download()` sets `creator_info=None` in `IngestOutcome`.
`IngestStage` logs a WARNING and proceeds — the video is saved with `creator_id=NULL`, `videos.author` preserved as-is (D-03 write-through only fires when `creator` is not None).
No exception is raised. This handles legitimate cases: compilations, playlists without a single uploader, geo-restricted metadata.

### D-03: Full upsert on re-ingest
When a video is re-ingested and its creator already exists in the DB, `uow.creators.upsert()` performs a **full upsert** (`ON CONFLICT DO UPDATE SET handle=…, display_name=…, follower_count=…, avatar_url=…, last_seen_at=…`).
Rationale: `follower_count` and `display_name` can change; keeping them fresh costs nothing (SQLAlchemy Core's ON CONFLICT is a no-op when values are identical).
`created_at` and `first_seen_at` are NOT overwritten (preserved from the first insert — same pattern as S01's `CreatorRepositorySQLite.upsert`).

### D-04: Single UoW transaction for creator + video
In `IngestStage.execute()`:
1. Enter the existing UoW context (already opened by the pipeline runner)
2. `uow.creators.upsert(creator_from_info)` — returns Creator with populated `id`
3. `uow.videos.upsert_by_platform_id(video, creator=creator)` — sets `creator_id` + write-through cache atomically
4. UoW commits once at the end of the stage

If the video upsert fails (e.g., constraint violation), the whole transaction rolls back — no orphan creator rows.
The UoW already supports both repos in a shared connection (delivered in S01).

### Claude's Discretion
- Exact name and position of `CreatorInfo` TypedDict in `ports/pipeline.py` (append after `IngestOutcome`, before `Downloader` Protocol)
- Whether `handle` and `display_name` map to the same `uploader` field or are treated separately (recommended: same field for now, consistent with S01's `ProbeResult`)
- Internal helper `_extract_creator_info(info_dict) -> CreatorInfo | None` in `YtdlpDownloader` to keep `download()` readable
- Test double: a `FakeDownloader` that returns `IngestOutcome` with a preset `creator_info` (needed for `IngestStage` unit tests — no real yt-dlp call)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing ingest pipeline
- `src/vidscope/pipeline/stages/ingest.py` — `IngestStage.execute()` to extend (add creator upsert step between download and video upsert)
- `src/vidscope/ports/pipeline.py` — `IngestOutcome` to extend + `CreatorInfo` TypedDict to add
- `src/vidscope/adapters/ytdlp/downloader.py` — `YtdlpDownloader.download()` + existing `_extract_uploader_*` helpers from S01

### S01 foundation (must mirror exactly)
- `src/vidscope/adapters/sqlite/creator_repository.py` — `CreatorRepositorySQLite.upsert()` signature
- `src/vidscope/adapters/sqlite/unit_of_work.py` — `SqliteUnitOfWork.creators` property
- `src/vidscope/adapters/sqlite/video_repository.py` — `VideoRepository.upsert_by_platform_id(video, creator=None)` signature (D-03 write-through)
- `src/vidscope/domain/entities.py` — `Creator` dataclass shape to construct from `CreatorInfo`

### Architectural contracts
- `.importlinter` — 9 contracts (pipeline stage may only import from ports, domain — not from adapters)
- `.gsd/milestones/M006/slices/S01/S01-CONTEXT.md` — D-03 write-through cache enforcement rule
- `.gsd/DECISIONS.md` — D020 (hexagonal layer map), D019 (import-linter enforcement)

### Test patterns
- `tests/unit/pipeline/` — existing IngestStage test pattern to mirror
- `tests/unit/adapters/ytdlp/test_downloader.py` — existing YtdlpDownloader test pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `YtdlpDownloader._extract_uploader_thumbnail()` and `_extract_uploader_verified()` — private helpers added in S01-P04, reuse directly
- `SqliteUnitOfWork.creators: CreatorRepository` — already wired in S01, available inside `IngestStage.execute()`
- `VideoRepository.upsert_by_platform_id(video, creator=None)` — already accepts creator kwarg (S01-P03), just pass it

### Established Patterns
- `IngestStage.__init__` receives `downloader`, `storage`, `video_repository`, `config` — adding `unit_of_work` or accessing it via the existing `uow` parameter passed to `execute()` avoids constructor change
- Transaction: the runner passes a UoW to each stage's `execute(ctx, uow)` — S02 just uses `uow.creators` on the already-open UoW
- `IngestOutcome` is a dataclass in `ports/pipeline.py` — add `creator_info: CreatorInfo | None = None` as optional field (backward-compatible default)

### Integration Points
- `IngestStage.execute()` line ~97 — add creator upsert AFTER successful download, BEFORE `uow.videos.upsert_by_platform_id()`
- `YtdlpDownloader.download()` — add `creator_info=_extract_creator_info(info)` when building `IngestOutcome` return value

</code_context>

<specifics>
## Specific Ideas

- No specific UI or interaction requirements — S02 is a pure pipeline layer change, invisible to end users until S03 ships the CLI.
- The WARNING log when `uploader_id` is absent should include the video URL so the user can diagnose the source.
- `_extract_creator_info` should be a standalone private function (not a method) in `ytdlp_downloader.py` for testability — return `None` when `uploader_id` is absent or empty string.

</specifics>

<deferred>
## Deferred Ideas

- Creator metadata refresh on scheduled re-watch (periodic follower_count update without re-downloading video) — M009 territory (engagement signals).
- Creator deduplication across platforms (same person on YouTube + TikTok) — explicitly out of M006 (D-05 from S01 discussions).
- Typed error / exception class for "uploader missing" — rejected in D-02 (would block legitimate cases). If user feedback changes this, it's a one-line change in S02 that can be revisited.

</deferred>

---

*Phase: M006/S02*
*Context gathered: 2026-04-17*
