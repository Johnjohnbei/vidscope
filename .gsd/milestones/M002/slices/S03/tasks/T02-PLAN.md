---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T02: scripts/verify-m002.sh milestone gate

Create scripts/verify-m002.sh following the verify-m001.sh pattern. Steps: (1) uv sync, (2-5) quality gates, (6) vidscope --version, (7) help lists every command, (8) doctor has mcp check, (9) MCP subprocess integration tests, (10) real CLI demo: seed 2 videos via inline Python (no real network needed), then `vidscope suggest <id>` and assert non-empty output. Support --skip-integration. Summary message announces M002 readiness.

## Inputs

- ``scripts/verify-m001.sh``

## Expected Output

- ``scripts/verify-m002.sh``

## Verification

bash scripts/verify-m002.sh --skip-integration
