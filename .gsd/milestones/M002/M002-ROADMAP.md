# M002: MCP server and related-video suggestions

## Vision
Turn the VidScope library from a CLI-only tool into something an AI agent can drive in conversation. Ship a Python MCP server (via the official `mcp` SDK) that exposes the existing M001 use cases as MCP tools: ingest a URL, search the library, get a video, list videos, get pipeline status, and suggest related videos. Also ship the related-video suggestion engine (R023) based on keyword overlap from the heuristic analyzer. No new business logic — just a new interface layer on top of the proven use cases.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | MCP server foundation with 5 read-only tools | high | — | ✅ | Starting `vidscope mcp serve` exposes 5 tools (ingest, search, get_video, list_videos, get_status) that an MCP client can call via JSON-RPC. A subprocess integration test confirms the server responds to list_tools. |
| S02 | Related-video suggestion engine + suggest tool + CLI suggest | medium | S01 | ✅ | `vidscope suggest <id>` returns N related videos from the library ranked by keyword overlap. Same logic exposed as `vidscope_suggest_related` MCP tool. |
| S03 | Documentation, verify-m002.sh, and milestone closure | low | S01, S02 | ✅ | `bash scripts/verify-m002.sh` runs all quality gates, unit+integration tests, spawns the MCP server via subprocess, and confirms list_tools returns 6 tools. docs/mcp.md explains Claude Desktop / Cline integration. |
