---
phase: M011
slug: veille-workflow-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase M011 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/ -x -q` |
| **Full suite command** | `pytest -x` |
| **Estimated runtime** | ~30–60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x -q`
- **After every plan wave:** Run `pytest -x` + `lint-imports` + `mypy src/vidscope`
- **Before `/gsd-verify-work`:** Full suite must be green + `lint-imports` 11 contracts green + `verify-m011.sh` passes
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| S01-01 | S01 | 1 | R056 | — | TrackingStatus enum, no illegal transitions | unit | `pytest tests/unit/test_video_tracking.py -x` | ❌ W0 | ⬜ pending |
| S01-02 | S01 | 1 | R056 | — | VideoTracking entity frozen/immutable | unit | `pytest tests/unit/test_video_tracking.py -x` | ❌ W0 | ⬜ pending |
| S01-03 | S01 | 1 | R056 | — | VideoTrackingRepository CRUD + upsert + UNIQUE | unit | `pytest tests/unit/test_video_tracking_repository.py -x` | ❌ W0 | ⬜ pending |
| S01-04 | S01 | 1 | R056 | — | SetVideoTrackingUseCase with InMemory repo | unit | `pytest tests/unit/test_set_video_tracking.py -x` | ❌ W0 | ⬜ pending |
| S01-05 | S01 | 1 | R056 | — | Pipeline neutrality: re-ingest does NOT wipe tracking | unit | `pytest tests/unit/test_pipeline_neutrality.py -x` | ❌ W0 | ⬜ pending |
| S01-06 | S01 | 1 | R056 | — | vidscope review CLI CliRunner snapshot | unit | `pytest tests/unit/cli/test_review_cmd.py -x` | ❌ W0 | ⬜ pending |
| S02-01 | S02 | 2 | R057 | — | Tag domain entity + TagName normalization | unit | `pytest tests/unit/test_tag_repository.py -x` | ❌ W0 | ⬜ pending |
| S02-02 | S02 | 2 | R057 | — | Collection domain entity + UNIQUE name | unit | `pytest tests/unit/test_collection_repository.py -x` | ❌ W0 | ⬜ pending |
| S02-03 | S02 | 2 | R057 | — | 4 tag use cases (tag_video, untag, list_tags, list_video_tags) | unit | `pytest tests/unit/test_tag_use_cases.py -x` | ❌ W0 | ⬜ pending |
| S02-04 | S02 | 2 | R057 | — | 4 collection use cases (create, add, remove, list) | unit | `pytest tests/unit/test_collection_use_cases.py -x` | ❌ W0 | ⬜ pending |
| S02-05 | S02 | 2 | R057 | — | vidscope tag + collection CLI CliRunner snapshots | unit | `pytest tests/unit/cli/test_tags_cmd.py tests/unit/cli/test_collections_cmd.py -x` | ❌ W0 | ⬜ pending |
| S03-01 | S03 | 3 | R058 | SQL-inj | SearchFilters extended with 4 workflow fields | unit | `pytest tests/unit/test_search_videos.py -x` | ✅ extend | ⬜ pending |
| S03-02 | S03 | 3 | R058 | SQL-inj | Facet matrix: ≥50 combos of 3 facets from 11 | unit | `pytest tests/unit/test_search_facets_matrix.py -x` | ❌ W0 | ⬜ pending |
| S03-03 | S03 | 3 | R058 | SQL-inj | SQL-injection guard: fuzz facet values with metacharacters | unit | `pytest tests/unit/test_search_sql_injection.py -x` | ❌ W0 | ⬜ pending |
| S03-04 | S03 | 3 | R058 | — | MCP search tool exposes new facets | unit | `pytest tests/unit/test_mcp_search.py -x` | ✅ extend | ⬜ pending |
| S04-01 | S04 | 4 | R059 | — | JSON exporter: schema validation + round-trip | unit | `pytest tests/unit/test_export_json.py -x` | ❌ W0 | ⬜ pending |
| S04-02 | S04 | 4 | R059 | — | Markdown exporter: YAML frontmatter parseable by yaml.safe_load | unit | `pytest tests/unit/test_export_markdown.py -x` | ❌ W0 | ⬜ pending |
| S04-03 | S04 | 4 | R059 | — | CSV exporter: stdlib csv round-trip | unit | `pytest tests/unit/test_export_csv.py -x` | ❌ W0 | ⬜ pending |
| S04-04 | S04 | 4 | R059 | — | ExportLibraryUseCase with fixture DB (5 videos) | unit | `pytest tests/unit/test_export_library.py -x` | ❌ W0 | ⬜ pending |
| S04-05 | S04 | 4 | R059 | — | vidscope export CLI CliRunner snapshot | unit | `pytest tests/unit/cli/test_export_cmd.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_video_tracking.py` — domain entity + enum stubs (R056)
- [ ] `tests/unit/test_video_tracking_repository.py` — SQLite adapter test stubs (R056)
- [ ] `tests/unit/test_set_video_tracking.py` — use case stubs (R056)
- [ ] `tests/unit/test_pipeline_neutrality.py` — regression guard stubs (R056)
- [ ] `tests/unit/cli/test_review_cmd.py` — CLI snapshot stubs (R056)
- [ ] `tests/unit/test_tag_repository.py` — tag adapter stubs (R057)
- [ ] `tests/unit/test_collection_repository.py` — collection adapter stubs (R057)
- [ ] `tests/unit/test_tag_use_cases.py` — tag use case stubs (R057)
- [ ] `tests/unit/test_collection_use_cases.py` — collection use case stubs (R057)
- [ ] `tests/unit/cli/test_tags_cmd.py` — tags CLI stubs (R057)
- [ ] `tests/unit/cli/test_collections_cmd.py` — collections CLI stubs (R057)
- [ ] `tests/unit/test_search_facets_matrix.py` — facet matrix stubs (R058)
- [ ] `tests/unit/test_search_sql_injection.py` — SQL injection guard stubs (R058)
- [ ] `tests/unit/test_export_json.py` — JSON export stubs (R059)
- [ ] `tests/unit/test_export_markdown.py` — Markdown export stubs (R059)
- [ ] `tests/unit/test_export_csv.py` — CSV export stubs (R059)
- [ ] `tests/unit/test_export_library.py` — ExportLibraryUseCase stubs (R059)
- [ ] `tests/unit/cli/test_export_cmd.py` — export CLI stubs (R059)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `verify-m011.sh` E2E: ingest 3 videos → tag → collection → search → export → parse | R056/R057/R058/R059 | Requires live DB + file system | Run `bash verify-m011.sh` and confirm exit code 0 |
| Import-linter 11 contracts green | Architecture | Integration of all contracts | `lint-imports` in project root |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
