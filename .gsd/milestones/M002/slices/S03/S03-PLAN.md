# S03: Documentation, verify-m002.sh, and milestone closure

**Goal:** Close M002 with user-facing documentation (docs/mcp.md with Claude Desktop + Cline configuration snippets) and a milestone-level verification script (scripts/verify-m002.sh) that combines all quality gates + unit tests + MCP subprocess integration + a real end-to-end CLI demo exercising the suggestion engine on a sandboxed 2-video library.
**Demo:** After this: `bash scripts/verify-m002.sh` runs all quality gates, unit+integration tests, spawns the MCP server via subprocess, and confirms list_tools returns 6 tools. docs/mcp.md explains Claude Desktop / Cline integration.

## Tasks
- [x] **T01: Wrote docs/mcp.md (287 lines) covering MCP overview, 6 tools with return shapes, Claude Desktop + Cline configs, example session, troubleshooting, security notes.** — Write docs/mcp.md covering: (1) what MCP is in one paragraph, (2) how to start the server (`vidscope mcp serve`), (3) complete list of 6 tools with their arguments and return shape, (4) Claude Desktop config snippet (JSON in `claude_desktop_config.json`), (5) Cline config snippet, (6) common troubleshooting (doctor check, stderr logs, stdin/stdout isolation). Include a real example session with 2-3 tool calls an agent would make.
  - Estimate: 1h
  - Files: docs/mcp.md
  - Verify: test -f docs/mcp.md && grep -q 'vidscope_suggest_related' docs/mcp.md && grep -q 'claude_desktop_config.json' docs/mcp.md
- [x] **T02: Shipped scripts/verify-m002.sh — 10-step milestone gate with --skip-integration fast mode. Runs quality gates + unit tests + MCP subprocess tests + real `vidscope suggest` CLI demo seeding 2 videos. 10/10 green on dev machine.** — Create scripts/verify-m002.sh following the verify-m001.sh pattern. Steps: (1) uv sync, (2-5) quality gates, (6) vidscope --version, (7) help lists every command, (8) doctor has mcp check, (9) MCP subprocess integration tests, (10) real CLI demo: seed 2 videos via inline Python (no real network needed), then `vidscope suggest <id>` and assert non-empty output. Support --skip-integration. Summary message announces M002 readiness.
  - Estimate: 1h
  - Files: scripts/verify-m002.sh
  - Verify: bash scripts/verify-m002.sh --skip-integration
