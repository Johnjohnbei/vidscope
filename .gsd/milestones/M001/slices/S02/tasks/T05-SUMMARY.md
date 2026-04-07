---
id: T05
parent: S02
milestone: M001
key_files:
  - src/vidscope/cli/commands/add.py
key_decisions:
  - Explicit fork on RunStatus with a defensive fail_system fallback for unexpected values — if the use case ever returns a status the CLI doesn't know, the operator sees a loud system error with exit 2 instead of silent wrong rendering
  - SKIPPED path plumbed in T05 even though it's not reachable until S06 — adding it now costs 10 lines and guarantees the display is ready the moment is_satisfied lights up
  - Shared _render_result_panel helper for OK and SKIPPED paths — single source of truth for field formatting, em-dash fallback, and label alignment
  - Aligned labels (padding after `platform:` / `title:` etc.) so values line up vertically — small readability win for operators scanning the panel
  - Clickable URL via `[link=...]...[/link]` rich markup — zero regression on non-supporting terminals, cheap win on modern ones
  - _MISSING module constant so the em-dash can be reused by other CLI commands rendering similar panels in later slices
duration: 
verification_result: passed
completed_at: 2026-04-07T12:05:19.188Z
blocker_discovered: false
---

# T05: Polished the CLI `add` command: explicit OK / SKIPPED / unexpected-status rendering with aligned rich panels, clickable URL via [link] markup, and fail_system fallback for defensive catch-all — 240 tests still green.

**Polished the CLI `add` command: explicit OK / SKIPPED / unexpected-status rendering with aligned rich panels, clickable URL via [link] markup, and fail_system fallback for defensive catch-all — 240 tests still green.**

## What Happened

T05 is the polish task that completes what T04 started. T04 moved the add command to the real `IngestVideoUseCase` signature; T05 refines the display with three concrete improvements.

**Status-based rendering fork.** The command now explicitly handles each `RunStatus` value:

- `OK`: green-bordered panel titled "ingest OK", rendered via `_render_result_panel`
- `SKIPPED`: yellow-bordered panel titled "already ingested (skipped)". This path is not reachable in S02 (D025: `IngestStage.is_satisfied()` always returns False) but the plumbing is here so the moment S06 wires probe-before-download, the display lights up without any CLI change.
- `FAILED`: unchanged, routed through `fail_user(result.message)` → exit 1
- Anything else (PENDING, RUNNING): `fail_system(f"unexpected ingest result status: ...")` → exit 2. This is a defensive catch-all that should never fire in practice, but if it does, the operator sees the exact status value and can investigate via `vidscope status`.

**Shared `_render_result_panel` helper.** OK and SKIPPED paths differ only in title and border color, so the panel rendering lives in one helper taking `title` and `border_style` as keyword arguments. The helper centralizes the em-dash fallback logic for missing fields — every `None` or empty field shows `—` instead of `None` so the panel stays aligned and readable.

**Aligned labels.** The previous layout had `video id:`, `platform:`, `title:` on their own lines but unaligned values because the labels were different lengths. I added explicit padding so the values align vertically:

```
video id: 42
platform:  youtube/abc123
title:     Fake CLI Video
author:    Fake Channel
duration:  120.5s
url:       https://www.youtube.com/watch?v=abc123
run id:    7
```

This is a small thing but it matters — operators scan this panel looking for specific fields, and a misaligned layout slows that scan.

**Clickable URL.** The URL line uses `[link={url}]{url}[/link]` rich markup. Terminals that support OSC 8 escape sequences (Windows Terminal, iTerm2, modern gnome-terminal) render the URL as a clickable hyperlink. Terminals that don't just show the plain URL — zero regression.

**Extracted `_MISSING = "—"` constant** so the em-dash appears once at the top of the module instead of being duplicated in seven format strings. Future slices that render similar panels (show, list, search results) can import this if they want consistent missing-field display.

**Tests unchanged.** The 11 CLI tests all still pass because the output strings they look for ("ingest OK", "Fake CLI Video", "Fake Author", "youtube") are all still present in the new format. I explicitly did NOT add tests for the SKIPPED path because there's no way to trigger it today — that test belongs in S06 alongside the `is_satisfied` implementation, marked explicitly as exercising S06's wiring.

**Quality gates after T05:**
- `pytest` → 240/240 passed in 1.47s
- `ruff check` → All checks passed (zero new issues)
- `mypy src` → Success, no issues on 52 files
- `lint-imports` → 7/7 contracts kept

**Manual smoke:** `vidscope add "https://vimeo.com/12345"` still surfaces the unsupported-platform error cleanly with exit 1. `vidscope --help` still lists six commands.

## Verification

Ran `python -m uv run pytest tests/unit/cli -q` → 11 passed. Ran `python -m uv run pytest tests/unit -q` → 240 passed in 1.47s. Ran `python -m uv run ruff check src tests` → All checks passed. Ran `python -m uv run mypy src` → Success, 52 files. Ran `python -m uv run lint-imports` → 7 contracts kept. Ran `python -m uv run vidscope add "https://vimeo.com/12345"` → exit 1 with "unsupported platform URL" message. Ran `python -m uv run vidscope --help` → all six commands visible.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (240/240) | 1470ms |
| 2 | `python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — all 4 gates clean | 2000ms |
| 3 | `python -m uv run vidscope add 'https://vimeo.com/12345'` | 1 | ✅ pass — unsupported platform rejected cleanly | 800ms |

## Deviations

Most of the T05 scope (use case wiring + basic rendering) was absorbed into T04 because the test suite wouldn't compile otherwise. T05 ended up being a pure polish task: explicit status fork, SKIPPED-path plumbing for S06, aligned labels, clickable URL. All incremental improvements on code that was already functional.

## Known Issues

None. The SKIPPED path is plumbed but not exercised in S02 because `IngestStage.is_satisfied()` currently always returns False (D025). S06 will flip it and the CLI display is already ready.

## Files Created/Modified

- `src/vidscope/cli/commands/add.py`
