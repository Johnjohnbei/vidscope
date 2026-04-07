---
id: T01
parent: S01
milestone: M001
key_files:
  - pyproject.toml
  - uv.lock
  - .python-version
key_decisions:
  - Use `python -m uv` everywhere instead of mutating PATH — reproducible across sessions
  - Specifiers as `>=X.Y,<X+1` (compatible-release) so uv can pick up patch/minor updates without plan changes
  - Keep dev deps in `[dependency-groups].dev` (uv modern format) rather than `[project.optional-dependencies].dev` — the latter is deprecated for uv-managed projects
duration: 
verification_result: passed
completed_at: 2026-04-07T10:43:21.143Z
blocker_discovered: false
---

# T01: Installed uv toolchain, pinned Python 3.13, declared runtime + dev deps with compatible-release specifiers, and committed uv.lock.

**Installed uv toolchain, pinned Python 3.13, declared runtime + dev deps with compatible-release specifiers, and committed uv.lock.**

## What Happened

uv 0.11.3 was already present in the user-site packages of the system Python 3.13 (shipped by a prior `pip install --user uv`) but its Scripts directory wasn't on PATH. Rather than modify the system PATH, I used `python -m uv` throughout — that's the safest cross-session invocation and avoids leaking any env changes outside the repo.

Pinned the interpreter to 3.13 via `uv python pin 3.13` (creates `.python-version`). Added the six runtime dependencies with `uv add typer sqlalchemy yt-dlp faster-whisper rich platformdirs` — uv picked current versions and auto-created the `.venv`. Added the four dev deps with `uv add --dev pytest pytest-cov ruff mypy`; uv placed them under `[dependency-groups].dev` (the modern format) rather than `[project.optional-dependencies]`, so I removed the now-empty `[project.optional-dependencies].dev = []` block and the leftover bootstrap comment.

Loosened the version specifiers from exact `>=X.Y.Z` to compatible-release `>=X.Y,<X+1` ranges per the plan (don't pin exact versions, allow patch/minor upgrades). Then `uv sync` to regenerate the lockfile against the relaxed specifiers — resolution completed in 19ms, no version changes needed, only vidscope itself was rebuilt.

Verified the end-state by importing every runtime dep from inside the uv-managed venv: `import typer, sqlalchemy, yt_dlp, faster_whisper, platformdirs, rich` → `ok`. The 979-line `uv.lock` and the 5-byte `.python-version` are now on disk alongside the updated pyproject.toml.

## Verification

Ran `python -m uv --version` → uv 0.11.3. Ran `python -m uv sync` → resolved 49 packages, built vidscope. Ran `python -m uv run python -c "import typer, sqlalchemy, yt_dlp, faster_whisper, platformdirs, rich; print('ok')"` → `ok`. Confirmed `uv.lock`, `.python-version`, and updated `pyproject.toml` all exist on disk.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv --version` | 0 | ✅ pass | 150ms |
| 2 | `python -m uv sync` | 0 | ✅ pass | 900ms |
| 3 | `python -m uv run python -c "import typer, sqlalchemy, yt_dlp, faster_whisper, platformdirs, rich; print('ok')"` | 0 | ✅ pass | 600ms |

## Deviations

uv was installed via system pip `--user` (0.11.3), not via the official standalone installer. Its binary lives at `~/AppData/Local/Packages/.../Python313/Scripts/uv.exe` and isn't on PATH, so every uv command goes through `python -m uv`. This works identically to a PATH-resolved `uv` and avoids modifying the user's environment. Documented here so future tasks know to prefer `python -m uv` over bare `uv`.

## Known Issues

None. The dependency set is complete and importable. Whisper/yt-dlp transcription and ingestion are exercised only in later slices, so their runtime behavior is not yet proven — just their importability.

## Files Created/Modified

- `pyproject.toml`
- `uv.lock`
- `.python-version`
