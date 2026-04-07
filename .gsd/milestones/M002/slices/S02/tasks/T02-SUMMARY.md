---
id: T02
parent: S02
milestone: M002
key_files:
  - src/vidscope/cli/commands/suggest.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/cli/test_app.py
key_decisions:
  - Score displayed as percentage (0-100%) not raw Jaccard [0, 1] — easier to read at a glance
  - Matched keywords column truncates at 5 items with ellipsis — prevents column bloat on narrow terminals
  - Empty-source case uses exit 1 (user error) because the user asked for a video that doesn't exist; empty-suggestions case is exit 0 because the library just doesn't have matches yet
duration: 
verification_result: passed
completed_at: 2026-04-07T17:24:42.208Z
blocker_discovered: false
---

# T02: Shipped `vidscope suggest <id>` CLI command wrapping SuggestRelatedUseCase with a rich table showing video_id/platform/title/score/matched_keywords. 14 CLI tests green.

**Shipped `vidscope suggest <id>` CLI command wrapping SuggestRelatedUseCase with a rich table showing video_id/platform/title/score/matched_keywords. 14 CLI tests green.**

## What Happened

New CLI subcommand follows the same pattern as every other command: acquire container → instantiate use case → call execute → render result. Handles three branches:

1. **Source not found** → `fail_user` with the exact reason from the use case ("no video with id X"), exits 1
2. **Empty suggestions** (source has no keywords, or no candidates match) → prints the source header + the dim reason, exits 0
3. **Has suggestions** → rich Table with 5 columns: id, platform, title, score (as percentage), matched keywords (comma-separated, truncated to 5 with ellipsis if more)

The score is displayed as a percentage (0-100%) which is friendlier than the raw [0, 1] Jaccard score. The matched keywords column is truncated to 5 items because more would blow the column width on narrow terminals.

Registered on the root Typer app as `suggest_command` via `app.command("suggest", ...)`. Also updated the `TestHelpAndVersion.test_help_lists_every_command` to include `suggest` and `mcp` in the expected command list — they were missing from the S01 update.

Added `TestSuggest` class with 2 tests:
- `test_missing_source_fails_with_user_error`: runs `suggest 999` on an empty library, asserts exit 1 and "no video with id 999" in output
- `test_help_shows_limit_option`: runs `suggest --help`, asserts `--limit` and `-n` are documented

Also added `TestMcp.test_mcp_subapp_lists_serve` to verify the mcp sub-application's serve command is visible (that check was missing after S01).

Updated `TestDoctor.test_runs_and_prints_a_table` to also assert `mcp` appears in the doctor output (4 checks now instead of 3).

Manual smoke of `vidscope suggest --help` confirms the Typer-generated help shows the argument (video_id with required tag) and the --limit option with range validation [1..100] and default 5.

**Quality gates**: 14 CLI tests green (12 existing + 2 new TestSuggest + the TestMcp addition covered the mcp check). Full suite gates come in T03 after the MCP tool registration.

## Verification

Ran `python -m uv run pytest tests/unit/cli -q` → 14 passed in 980ms. Ran `python -m uv run vidscope suggest --help` → Typer help shows video_id argument + --limit option with range [1..100] + default 5.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/cli -q` | 0 | ✅ 14/14 CLI tests green | 980ms |
| 2 | `python -m uv run vidscope suggest --help` | 0 | ✅ Typer help shows video_id + --limit/-n with range [1..100] | 500ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/cli/commands/suggest.py`
- `src/vidscope/cli/commands/__init__.py`
- `src/vidscope/cli/app.py`
- `tests/unit/cli/test_app.py`
