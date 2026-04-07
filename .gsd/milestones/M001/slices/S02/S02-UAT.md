# S02: Ingestion brick (yt-dlp) for Instagram, TikTok and YouTube — UAT

**Milestone:** M001
**Written:** 2026-04-07T12:19:55.338Z

## S02 UAT — Ingestion brick (yt-dlp) for YouTube / TikTok / Instagram

Target: confirm that `vidscope add <url>` actually downloads real public short-form videos and persists full metadata + media files, that the failure paths are clean, and that Instagram's current upstream auth requirement is surfaced clearly.

### Manual checks

1. **Fast-loop verification**
   - Run `bash scripts/verify-s02.sh --skip-integration`
   - Confirm: 10/10 green, no network touched

2. **Full verification with real networks**
   - Run `bash scripts/verify-s02.sh`
   - Confirm: 12/12 green (YouTube Short ✓, TikTok ✓, Instagram xfail, sandbox DB has ≥ 1 row)
   - Confirm the full run completes in under 60 seconds

3. **CLI happy path (YouTube Short)**
   - Export a clean VIDSCOPE_DATA_DIR
   - Run `python -m uv run vidscope add "https://www.youtube.com/shorts/34WNvQ1sIw4"`
   - Confirm: rich Panel titled "ingest OK" showing video id, platform youtube/<id>, title, author, duration <60s, clickable URL, run id
   - Run `python -m uv run vidscope status`
   - Confirm: row with phase=ingest, status=ok, video column populated

4. **CLI happy path (TikTok)**
   - Run `python -m uv run vidscope add "https://www.tiktok.com/@tiktok/video/7106594312292453675"` (or any public @tiktok video)
   - Confirm: ingest OK panel, status row in `vidscope status`

5. **CLI failure paths**
   - `python -m uv run vidscope add ""` → exit 1, "url is empty"
   - `python -m uv run vidscope add "https://vimeo.com/12345"` → exit 1, "unsupported platform URL"
   - `python -m uv run vidscope add "https://www.youtube.com/watch?v=doesnotexist12345"` → exit 1 with yt-dlp error text in the message and a FAILED row in `vidscope status`

6. **Integration tests directly**
   - Run `python -m uv run pytest tests/integration -m integration -v`
   - Confirm: 2 passed (YouTube, TikTok), 1 xfailed (Instagram) with the clear upstream error in the xfail reason

7. **Quality gates**
   - `python -m uv run pytest -q` → 243 passed, 3 deselected
   - `python -m uv run ruff check src tests` → All checks passed
   - `python -m uv run mypy src` → Success, no issues
   - `python -m uv run lint-imports` → 7 contracts kept, 0 broken

### Success criteria from the slice plan

- [x] `vidscope add <public-youtube-url>` downloads and persists the full metadata round-trip
- [x] Same command succeeds on a public TikTok video URL
- [ ] Same command succeeds on a public Instagram Reel URL — **blocked upstream** by Meta's authentication requirement (R025, M005)
- [x] Invalid URLs produce IngestError with exit 1 and actionable message + FAILED pipeline_runs row
- [x] Re-running `vidscope add` does not duplicate rows (upsert_by_platform_id) — verified manually + covered by test
- [x] `vidscope status` shows runs with correct timestamps and durations
- [x] Zero new dependencies on SQLAlchemy or third-party libs in domain/ports/pipeline/application (import-linter)
- [x] All four quality gates stay clean
- [x] R001 advanced from active to validated for YouTube + TikTok (Instagram deferred)

