# S02: Related-video suggestion engine + suggest tool + CLI suggest

**Goal:** Ship the related-video suggestion engine (R023) as a new SuggestRelatedUseCase, add a `vidscope suggest <id>` CLI command, and register the `vidscope_suggest_related` MCP tool. The engine uses Jaccard similarity on analysis keyword sets — pure Python, zero deps, one cheap DB query per call. No embeddings (R026 stays deferred).
**Demo:** After this: `vidscope suggest <id>` returns N related videos from the library ranked by keyword overlap. Same logic exposed as `vidscope_suggest_related` MCP tool.

## Tasks
- [x] **T01: Shipped SuggestRelatedUseCase with Jaccard keyword overlap — 11 unit tests covering happy path, 6 edge cases, score ordering. Pure stdlib, zero deps.** — Create src/vidscope/application/suggest_related.py. SuggestRelatedUseCase takes a unit_of_work_factory. execute(video_id, limit=5) returns a SuggestRelatedResult DTO with: source_video (or None if not found), suggestions (tuple of Suggestion dataclasses with video_id, title, platform, score, matched_keywords). Algorithm: (1) open a UoW, (2) fetch source video + its latest analysis, (3) if source analysis is None OR keywords empty, return empty suggestions, (4) fetch all videos in the library up to a reasonable cap (500), (5) for each candidate != source, fetch its latest analysis, compute Jaccard = |intersection| / |union| on keyword sets, skip if score == 0, (6) sort descending by score, take top `limit`. Tests cover every branch.
  - Estimate: 1h30m
  - Files: src/vidscope/application/suggest_related.py, src/vidscope/application/__init__.py, tests/unit/application/test_suggest_related.py
  - Verify: python -m uv run pytest tests/unit/application/test_suggest_related.py -q
- [x] **T02: Shipped `vidscope suggest <id>` CLI command wrapping SuggestRelatedUseCase with a rich table showing video_id/platform/title/score/matched_keywords. 14 CLI tests green.** — Create src/vidscope/cli/commands/suggest.py with a suggest_command(video_id, limit=5) that builds a container, instantiates SuggestRelatedUseCase, renders results as a rich Table: columns video_id, platform, title, score (0-100 display), matched_keywords. Handles the empty-suggestions case with a clear message. Register on the root Typer app. Add to CliRunner tests.
  - Estimate: 1h
  - Files: src/vidscope/cli/commands/suggest.py, src/vidscope/cli/commands/__init__.py, src/vidscope/cli/app.py, tests/unit/cli/test_app.py
  - Verify: python -m uv run pytest tests/unit/cli -q && python -m uv run vidscope suggest --help
- [x] **T03: Registered `vidscope_suggest_related` as the 6th MCP tool + updated unit and subprocess tests. Server now exposes 6 tools, 17 MCP unit tests green, 2 subprocess integration tests green, 370 total unit tests green.** — Extend src/vidscope/mcp/server.py to register a 6th tool `vidscope_suggest_related(video_id, limit=5)` that wraps SuggestRelatedUseCase and converts the DTO to a JSON-serializable dict. Update unit tests in tests/unit/mcp/test_server.py to expect 6 tools and add tests for the new tool (empty library → empty suggestions, seeded library with overlapping videos → ranked results). Update the subprocess integration test in tests/integration/test_mcp_server.py to expect 6 tool names.
  - Estimate: 1h
  - Files: src/vidscope/mcp/server.py, tests/unit/mcp/test_server.py, tests/integration/test_mcp_server.py
  - Verify: python -m uv run pytest tests/unit/mcp -q && python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v
