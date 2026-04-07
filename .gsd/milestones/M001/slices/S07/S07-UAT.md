# S07: Cookie-based authentication for Instagram (and other gated content) — UAT

**Milestone:** M001
**Written:** 2026-04-07T13:57:47.832Z

## S07 UAT — Cookie-based authentication for Instagram

Target: confirm that the cookies feature is plumbed end-to-end and that Instagram public Reels can be ingested by a user who provides their browser cookies once.

### Manual checks (no cookies needed)

1. **Fast verification**
   - Run `bash scripts/verify-s07.sh --skip-integration`
   - Confirm: 10/10 steps green, including the misconfigured-cookies fail-fast test

2. **Doctor includes cookies row**
   - Run `python -m uv run vidscope doctor`
   - Confirm: third row labeled `cookies` with status `ok` and detail `not configured (optional)`
   - Confirm: ffmpeg and yt-dlp rows still present

3. **Misconfigured cookies fail-fast**
   - Run `VIDSCOPE_COOKIES_FILE=/does-not-exist.txt python -m uv run vidscope status`
   - Confirm: exits with non-zero code and a typed error message about the cookies file
   - Verify the error mentions "cookies file not found"

4. **Default behavior unchanged**
   - Without setting any cookies env var, run `python -m uv run vidscope add "https://www.tiktok.com/@tiktok/video/7106594312292453675"`
   - Confirm: TikTok ingest succeeds (cookies are optional, didn't break the existing path)

5. **Integration tests reordered**
   - Run `python -m uv run pytest tests/integration -m integration --collect-only -q`
   - Confirm: collection order is Instagram → TikTok → YouTube
   - Run `python -m uv run pytest tests/integration -m integration -v`
   - Confirm: Instagram xfails first with the "requires cookie-based authentication" message, then TikTok and YouTube pass

### Manual checks (with real Instagram cookies — if you have them)

6. **Export cookies from your browser**
   - Follow `docs/cookies.md` step-by-step
   - Save the file as `cookies.txt` somewhere safe

7. **Configure vidscope to use them**
   - Either drop the file at `<data_dir>/cookies.txt` or set `VIDSCOPE_COOKIES_FILE=/path/to/cookies.txt`
   - Run `python -m uv run vidscope doctor`
   - Confirm: the cookies row now shows `configured at <path>` in green

8. **Real Instagram ingest**
   - Run `python -m uv run vidscope add "https://www.instagram.com/reel/<some-public-reel-id>/"`
   - Confirm: ingest OK panel with title, author, duration

9. **Integration test passes Instagram**
   - With cookies still configured, run `python -m uv run pytest tests/integration -m integration -v`
   - Confirm: all three tests pass (no xfail on Instagram)

10. **Full verification**
    - Run `bash scripts/verify-s07.sh`
    - Confirm: 11/11 steps green, summary message "R001 validated for all three platforms"

### Quality gates

- [x] `pytest -q` → 260 unit tests + 3 architecture tests pass, 3 integration deselected by default
- [x] `ruff check src tests` → All checks passed
- [x] `mypy src` → no issues on 52 source files
- [x] `lint-imports` → 7 contracts kept, 0 broken
- [x] yt_dlp still imported in exactly one file (`src/vidscope/adapters/ytdlp/downloader.py`)
- [x] R025 plumbing complete and verified end-to-end
- [x] R001 path exists for Instagram (conditional on user-provided cookies)

