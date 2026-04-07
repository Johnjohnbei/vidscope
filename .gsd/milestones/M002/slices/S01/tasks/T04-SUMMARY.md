---
id: T04
parent: S01
milestone: M002
key_files:
  - .importlinter
  - tests/architecture/test_layering.py
key_decisions:
  - vidscope.cli sits ABOVE vidscope.mcp in the layer stack, not as a sibling — CLI is the user-facing entry point and is allowed to delegate to MCP for `vidscope mcp serve`
  - mcp-has-no-adapters contract uses ignore_imports for the `vidscope.mcp.server -> vidscope.infrastructure.container` edge — that's the legitimate composition root path, not a violation
  - forbidden contracts are transitive in import-linter: declaring `vidscope.mcp` cannot import `vidscope.adapters.*` rejects ANY path, direct or indirect, unless explicitly whitelisted via ignore_imports
  - Any NEW direct `from vidscope.mcp.X import vidscope.adapters.Y` would still be rejected — the whitelist only covers the specific composition-root edge
duration: 
verification_result: passed
completed_at: 2026-04-07T17:16:22.797Z
blocker_discovered: false
---

# T04: Extended import-linter with the mcp layer and a new forbidden contract — 8 contracts now enforced (up from 7). Architecture test expected contracts list updated. 353 tests green.

**Extended import-linter with the mcp layer and a new forbidden contract — 8 contracts now enforced (up from 7). Architecture test expected contracts list updated. 353 tests green.**

## What Happened

Two changes to `.importlinter`:

**1. Added `vidscope.mcp` to the layers stack** between `vidscope.cli` and `vidscope.application`. First attempt used `vidscope.cli | vidscope.mcp` as siblings — that was wrong because it forbade the cli from importing mcp, which breaks `vidscope mcp serve` (the CLI needs to delegate to the mcp server package). Corrected to a plain vertical ordering: cli above mcp. The CLI can import downward (mcp, application, pipeline, adapters, ports, domain); mcp can only import downward (application, pipeline, adapters at its own level — but the forbidden contract below prevents direct adapter access).

**2. Added `mcp-has-no-adapters` forbidden contract**. Source: `vidscope.mcp`. Forbidden: every adapter sub-package (sqlite, fs, ytdlp, whisper, ffmpeg, heuristic). Whitelisted: `vidscope.mcp.server -> vidscope.infrastructure.container` because that's the legitimate path — the MCP server obtains a Container via the composition root, and the container transitively wires adapters. Without the whitelist, import-linter flags every indirect path through the container as a violation.

The key insight: forbidden contracts are transitive. When `mcp.server -> infrastructure.container -> adapters.ytdlp`, import-linter sees `mcp.server → ... → adapters.ytdlp` and flags it. `ignore_imports` lets us say "this specific edge is the legitimate path", and any NEW direct import from mcp to an adapter would still be rejected.

**Architecture test updated**: added `"MCP interface layer depends only on application and infrastructure"` to `EXPECTED_CONTRACTS`. The test subprocess-runs `lint-imports` and asserts every expected name is in the output with KEPT verdict.

**Final count**: 92 files analyzed, 331 dependencies, 8 contracts kept, 0 broken. 353 unit tests + 3 architecture tests green.

## Verification

Ran `python -m uv run lint-imports` → 8 kept, 0 broken. Ran `python -m uv run pytest tests/architecture -q` → 3 passed. Ran full suite → 353 passed, 3 deselected. Confirmed the new contract rejects any hypothetical direct `mcp → adapters` import while allowing the legitimate container path.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run lint-imports` | 0 | ✅ 8 contracts kept, 0 broken (92 files, 331 deps) | 2000ms |
| 2 | `python -m uv run pytest tests/architecture -q` | 0 | ✅ 3/3 architecture tests green with new contract in EXPECTED_CONTRACTS | 430ms |
| 3 | `python -m uv run pytest -q` | 0 | ✅ 353 passed, 3 deselected | 3170ms |

## Deviations

First attempt used `vidscope.cli | vidscope.mcp` sibling syntax which forbade CLI→MCP imports. Corrected to vertical ordering (cli above mcp) after observing that the `vidscope mcp serve` command needs the CLI to delegate to the MCP server. The architectural intent is preserved: MCP never imports CLI, which is the invariant that matters. CLI importing MCP is fine because CLI is the user-facing entry point and can orchestrate anything.

## Known Issues

None.

## Files Created/Modified

- `.importlinter`
- `tests/architecture/test_layering.py`
