"""VidScope MCP interface layer.

Exposes the existing :mod:`vidscope.application` use cases as Model
Context Protocol tools via FastMCP. An AI agent connected through
an MCP client (Claude Desktop, Cline, any stdio MCP client) can
drive the library: ingest URLs, search transcripts, inspect videos,
list recent entries, and check pipeline status.

This layer is a *new interface* on top of the proven M001 use cases,
not a new layer of business logic. Every tool is a ~5-line wrapper:
build a use case from the injected container, call execute, convert
the typed DTO to a JSON-serializable dict.

Import-linter enforces that ``vidscope.mcp`` never imports concrete
adapters directly — same rule as ``vidscope.cli``. See .importlinter.
"""

from __future__ import annotations

from vidscope.mcp.server import build_mcp_server, main

__all__ = ["build_mcp_server", "main"]
