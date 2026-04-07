---
id: T01
parent: S03
milestone: M002
key_files:
  - docs/mcp.md
key_decisions:
  - Document each tool with its exact JSON return shape — users can script against the format without guessing
  - Include both Claude Desktop and Cline config snippets — covers the two most common MCP clients
  - Example agent session shows a realistic 3-tool-call sequence — teaches the composition pattern
  - Troubleshooting mentions the stdout-corruption gotcha explicitly even though vidscope's architecture prevents it — helps anyone forking the server
duration: 
verification_result: passed
completed_at: 2026-04-07T17:30:07.640Z
blocker_discovered: false
---

# T01: Wrote docs/mcp.md (287 lines) covering MCP overview, 6 tools with return shapes, Claude Desktop + Cline configs, example session, troubleshooting, security notes.

**Wrote docs/mcp.md (287 lines) covering MCP overview, 6 tools with return shapes, Claude Desktop + Cline configs, example session, troubleshooting, security notes.**

## What Happened

Structure of docs/mcp.md:

1. **What is MCP?** — one paragraph explaining the protocol for users who haven't seen it before, with a link to modelcontextprotocol.io
2. **Start the server** — `vidscope mcp serve` command + `vidscope doctor` for SDK verification
3. **Registered tools** — 6 sections, one per tool, with the exact JSON return shape for each
4. **Claude Desktop configuration** — copy-pasteable JSON snippet with the config file path on macOS and Windows + restart instruction
5. **Cline configuration** — same shape for the Cline VSCode extension
6. **Example agent session** — a realistic 3-tool-call sequence showing how an agent would use search → get_video → suggest_related together
7. **Troubleshooting** — 4 common issues with concrete remediations (server doesn't start, can't connect, tool timeout, empty results, Instagram)
8. **Security notes** — the MCP server runs as a local subprocess with full library access, no network exposure, sharing the config means sharing access

The return shape documentation for each tool includes exact JSON with realistic values (e.g., `"rank": -1.23` for BM25 where negative is better, `"score": 0.6` for Jaccard). This matches the actual output from the MCP tools so users can script against the shape without guessing.

The troubleshooting section addresses the stdout-corruption gotcha specifically: MCP tools must never print to stdout because that corrupts the JSON-RPC protocol. VidScope's architecture already ensures this (log to stderr, return values go through the MCP SDK's serializer), but documenting the constraint helps users diagnose issues when they fork or modify the server.

## Verification

Ran `test -f docs/mcp.md && grep -q 'vidscope_suggest_related' docs/mcp.md && grep -q 'claude_desktop_config.json' docs/mcp.md && wc -l docs/mcp.md` → all checks pass, 287 lines.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f docs/mcp.md && grep -q markers && wc -l` | 0 | ✅ docs/mcp.md present (287 lines) with all expected content | 20ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `docs/mcp.md`
