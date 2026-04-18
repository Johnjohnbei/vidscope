---
phase: 8
slug: visual-intelligence-frames
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase M008 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `python -m pytest tests/unit/domain/ tests/unit/adapters/vision/ -q` |
| **Full suite command** | `python -m pytest --tb=short -q` |
| **Estimated runtime** | ~25 seconds (OCR fixture tests may add ~5s) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/unit/domain/ tests/unit/adapters/vision/ -q`
- **After every plan wave:** Run `python -m pytest --tb=short -q`
- **Before `/gsd-verify-work`:** Full suite must be green (935+ tests)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| S01-01 | S01-P01 | 1 | R047 | — | N/A | unit | `pytest tests/unit/domain/test_frame_text.py -q` | ❌ W0 | ⬜ pending |
| S01-02 | S01-P01 | 1 | R047 | — | N/A | unit | `pytest tests/unit/adapters/vision/test_rapidocr_engine.py -q` | ❌ W0 | ⬜ pending |
| S01-03 | S01-P01 | 1 | R047 | — | N/A | unit | `pytest tests/unit/adapters/sqlite/test_frame_text_repository.py -q` | ❌ W0 | ⬜ pending |
| S02-01 | S02-P01 | 2 | R047 | — | N/A | integration | `pytest tests/integration/pipeline/test_visual_intelligence_stage.py -q` | ❌ W0 | ⬜ pending |
| S03-01 | S03-P01 | 3 | R048,R049 | — | N/A | unit | `pytest tests/unit/adapters/vision/test_face_counter.py -q` | ❌ W0 | ⬜ pending |
| S04-01 | S04-P01 | 4 | R047 | — | N/A | unit | `pytest tests/unit/cli/test_show_command.py -q` | ❌ W0 | ⬜ pending |
| S04-02 | S04-P01 | 4 | R047 | — | N/A | unit | `pytest tests/unit/mcp/test_frame_texts_tool.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/domain/test_frame_text.py` — FrameText entity invariants
- [ ] `tests/unit/adapters/vision/test_rapidocr_engine.py` — RapidOcrEngine with 5 fixture JPGs
- [ ] `tests/unit/adapters/vision/test_face_counter.py` — Haarcascade with 5 fixture JPGs
- [ ] `tests/unit/adapters/sqlite/test_frame_text_repository.py` — CRUD + FK + cascade
- [ ] `tests/integration/pipeline/test_visual_intelligence_stage.py` — stage with stubbed OcrEngine
- [ ] `tests/fixtures/vision/` — fixture JPGs (text_present.jpg, no_text.jpg, face_solo.jpg, face_none.jpg, face_multi.jpg)

*Existing infrastructure (conftest, FakeUoW patterns) covers shared fixtures — only new test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real OCR end-to-end on live video with on-screen link | R047 | Requires real network + `rapidocr-onnxruntime` installed | Run `verify-m008.sh` after M008 complete — check `frame_texts` rows + links row with `source='ocr'` |
| OCR performance < 20s on 30 frames | R047 | Benchmark depends on reference CPU | `pytest tests/benchmarks/test_ocr_perf.py` with `--benchmark-only` — document in SUMMARY.md |
| Doctor reports vision row | R047 | CLI integration | `vidscope doctor` — assert "vision" row present with model status |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
