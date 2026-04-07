---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T01: docs/mcp.md user-facing guide

Write docs/mcp.md covering: (1) what MCP is in one paragraph, (2) how to start the server (`vidscope mcp serve`), (3) complete list of 6 tools with their arguments and return shape, (4) Claude Desktop config snippet (JSON in `claude_desktop_config.json`), (5) Cline config snippet, (6) common troubleshooting (doctor check, stderr logs, stdin/stdout isolation). Include a real example session with 2-3 tool calls an agent would make.

## Inputs

- ``docs/cookies.md``
- ``docs/quickstart.md``

## Expected Output

- ``docs/mcp.md``

## Verification

test -f docs/mcp.md && grep -q 'vidscope_suggest_related' docs/mcp.md && grep -q 'claude_desktop_config.json' docs/mcp.md
