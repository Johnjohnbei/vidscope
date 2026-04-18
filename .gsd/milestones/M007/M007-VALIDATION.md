---
phase: M007
slug: rich-content-metadata
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase M007 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/ -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

### S01 — Domain + Storage

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| S01-domain | P01 | 1 | R043 | N/A | unit/domain | `pytest tests/unit/domain/test_entities.py -x -q` | ⬜ pending |
| S01-hashtag-repo | P01 | 1 | R043 | N/A | unit/adapter | `pytest tests/unit/adapters/test_hashtag_repository.py -x -q` | ⬜ pending |
| S01-mention-repo | P01 | 1 | R043 | N/A | unit/adapter | `pytest tests/unit/adapters/test_mention_repository.py -x -q` | ⬜ pending |
| S01-video-repo | P01 | 1 | R043 | N/A | unit/adapter | `pytest tests/unit/adapters/test_video_repository.py -x -q` | ⬜ pending |
| S01-schema | P01 | 1 | R043 | N/A | unit/adapter | `pytest tests/unit/adapters/test_schema.py -x -q` | ⬜ pending |
| S01-uow | P01 | 1 | R043 | N/A | unit/adapter | `pytest tests/unit/adapters/test_unit_of_work.py -x -q` | ⬜ pending |

### S02 — LinkExtractor

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| S02-corpus-gate | P02 | 1 | R044 | No URL false-positives ("hello.world") | unit/adapter | `pytest tests/unit/adapters/test_regex_link_extractor.py -x -q` | ⬜ pending |
| S02-normalizer | P02 | 1 | R044 | Strip UTM params, lowercase host | unit/adapter | `pytest tests/unit/adapters/test_url_normalizer.py -x -q` | ⬜ pending |
| S02-link-repo | P02 | 1 | R044 | N/A | unit/adapter | `pytest tests/unit/adapters/test_link_repository.py -x -q` | ⬜ pending |

### S03 — Pipeline wiring

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| S03-ingest | P03 | 2 | R043 | N/A | integration | `pytest tests/integration/test_ingest_stage.py -x -q` | ⬜ pending |
| S03-metadata-stage | P03 | 2 | R044 | N/A | unit/pipeline | `pytest tests/unit/pipeline/test_metadata_extract_stage.py -x -q` | ⬜ pending |
| S03-pipeline | P03 | 2 | R043,R044 | N/A | integration | `pytest tests/integration/test_pipeline_integration.py -x -q` | ⬜ pending |

### S04 — CLI + MCP

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| S04-search-facets | P04 | 3 | R046 | N/A | unit/app+CLI | `pytest tests/unit/application/ tests/unit/cli/ -x -q` | ⬜ pending |
| S04-links-cmd | P04 | 3 | R046 | N/A | CLI snapshot | `pytest tests/unit/cli/test_links_cmd.py -x -q` | ⬜ pending |
| S04-mcp | P04 | 3 | R046 | N/A | unit/mcp | `pytest tests/unit/mcp/ -x -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/link_corpus.json` — ≥100 strings (50 pos, 30 neg, 20 edge) — gate non-négociable S02
- [ ] Stubs test pour tous les nouveaux repos (S01 : hashtag, mention ; S02 : link)
- [ ] `tests/unit/pipeline/test_metadata_extract_stage.py` — stubs before S03 implementation

*Existing pytest infrastructure covers all phase requirements — no new framework needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| E2E live: `vidscope add <TikTok>` → hashtags/mentions/music/links persisted | R043, R044 | Requires real network + real TikTok URL | Run `verify-m007.sh` with real URL; assert `vidscope search --hashtag <tag>` returns video |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
