# S01: Project socle, data layer and CLI skeleton — UAT

**Milestone:** M001
**Written:** 2026-04-07T11:42:21.877Z

## S01 UAT — Project socle, data layer, CLI skeleton

Target: confirm the VidScope socle is installable, the CLI dispatches correctly, the DB is created with every expected table, and the observability surface (`status`, `doctor`) already tells an operator what they need to know.

### Manual checks

1. **Fresh install**
   - Clone the repo
   - Run `python -m uv sync`
   - Confirm: no errors, `.venv/` populated, `uv.lock` present

2. **Help discoverability**
   - Run `python -m uv run vidscope --help`
   - Confirm: six subcommands visible (add, show, list, search, status, doctor) with a one-line description each
   - Confirm: `--version` shows `vidscope 0.1.0`

3. **Fresh-DB status**
   - Run `python -m uv run vidscope status`
   - Confirm: prints `videos: 0   pipeline runs: 0` and an empty-state hint
   - Confirm: exit code 0

4. **Doctor report**
   - Run `python -m uv run vidscope doctor`
   - Confirm: rich table with two rows (ffmpeg, yt-dlp), each showing status and version-or-error
   - If ffmpeg is missing: exit 2 with platform-specific install instructions
   - If ffmpeg is present: exit 0

5. **Ingest happy path (S01 skeleton)**
   - Run `python -m uv run vidscope add "https://www.youtube.com/watch?v=test"`
   - Confirm: rich panel showing URL, status=pending, run id, and the "S02-S06 will wire real ingest" message
   - Confirm: exit 0

6. **Status after add**
   - Run `python -m uv run vidscope status`
   - Confirm: `pipeline runs: 1`, color-coded table showing one row with phase=ingest, status=pending

7. **Error paths**
   - Run `python -m uv run vidscope add ""` → confirm `error: url is empty`, exit 1
   - Run `python -m uv run vidscope show 999` → confirm `error: no video with id 999`, exit 1

8. **Automated full verification**
   - Run `bash scripts/verify-s01.sh`
   - Confirm: `Total steps: 13, Failed: 0, ✓ S01 verification PASSED`

### Success criteria from the slice plan

- [x] `uv sync` installs runtime + dev deps cleanly on Windows from a fresh clone
- [x] `uv run vidscope --help` lists add, show, list, search, status as documented subcommands (doctor bonus)
- [x] Running any CLI command for the first time creates the SQLite DB with every table + FTS5 virtual table
- [x] `uv run vidscope status` on a fresh DB returns an empty-but-valid report, exit 0
- [x] `uv run vidscope add <url>` returns a typed placeholder and writes a `pipeline_runs` row with phase=ingest and status=pending
- [x] Startup checks emit clean structured errors when ffmpeg or yt-dlp is missing with install instructions
- [x] `uv run pytest` passes all tests (185/185)
- [x] `uv run ruff check src tests` and `uv run mypy src` are clean
- [x] R005 (persistent queryable DB) and R009 (cross-platform install) are provably advanced

