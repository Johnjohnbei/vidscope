# M008 — Visual intelligence on frames

## Vision
M001 extracts up to 30 frames per video but they sit on disk unused. M008 turns them into structured signal: OCR text (captures on-screen links/CTA/handles), a canonical thumbnail, and a talking-head vs B-roll classification. OCR is the headline feature — "link in bio" and promo codes live on screen, not in audio. The extractor is **local, CPU-only, zero-cost** (D010 principle): `rapidocr-onnxruntime` ships a ~50 MB ONNX model that handles FR+EN reliably. Results feed the same `LinkExtractor` shipped in M007, so OCR-discovered URLs land in the exact same `links` table.

## Slice Overview

| ID | Slice | Risk | Depends | Done when |
|----|-------|------|---------|-----------|
| S01 | OCR port + rapidocr adapter + FrameText entity | medium | M001 (frames), M007/S02 (LinkExtractor) | `FrameText` entity, `OcrEngine` Protocol, `RapidOcrEngine` adapter with lazy model load, `frame_texts` table, `doctor` reports model availability. |
| S02 | VisualIntelligenceStage runs OCR on every frame + persists text + feeds LinkExtractor | medium | S01 | New pipeline stage after `FramesStage`, idempotent (skips frames already processed), extracted text rows feed LinkExtractor → new `links` rows with `source='ocr'` and `position_ms=frame.timestamp_ms`. |
| S03 | Canonical thumbnail + face-count classifier | low | S01 | `video.thumbnail_key` populated at `videos/{id}/thumb.jpg` (copy of middle frame), `video.content_shape ENUM {talking_head, broll, mixed, unknown}` based on OpenCV haarcascade face-count per frame. |
| S04 | CLI + MCP surface | low | S02, S03 | `vidscope show <id>` displays on-screen text snippets + thumbnail path + content_shape, `vidscope search --on-screen-text "promo"` facet, MCP tool `vidscope_get_frame_texts`. |

## Layer Architecture

| Slice | Layer | New/Changed files |
|-------|-------|-------------------|
| S01 | domain | `entities.py` (+FrameText), `values.py` (+content_shape enum) |
| S01 | ports | `ocr_engine.py` (Protocol), `frame_text_repository.py` |
| S01 | adapters/vision | **new submodule** `adapters/vision/rapidocr_engine.py`, `adapters/vision/haarcascade_face_counter.py` |
| S01 | adapters/sqlite | `frame_text_repository.py`, `migrations/006_frame_texts.py`, `schema.py` (+frame_texts, +videos.thumbnail_key, +videos.content_shape) |
| S01 | infrastructure | `container.py` (lazy-instantiated RapidOcrEngine), `doctor.py` (vision row) |
| S02 | pipeline | `visual_intelligence_stage.py` **new**, `runner.py` (insert after FramesStage), `ingest_stage.py` unchanged |
| S02 | application | `use_cases/add_video.py` (wire new stage) |
| S03 | pipeline | `visual_intelligence_stage.py` (extended: thumbnail copy + face-count → content_shape) |
| S04 | application | `use_cases/get_video.py` (include frame texts), `use_cases/search_videos.py` (+on-screen-text facet via FTS5) |
| S04 | cli | `videos.py` (show), `main.py` (search facet) |
| S04 | mcp | `tools/frames.py` |
| S04 | adapters/sqlite | `migrations/007_fts_frame_texts.py` — FTS5 table for on-screen text |

## Test Strategy

| Test kind | Scope | Tooling |
|-----------|-------|---------|
| Domain unit | FrameText invariants, content_shape enum exhaustiveness | pytest |
| Adapter unit — OCR | RapidOcrEngine against 5 fixture JPGs (known text), lazy model load, timeout handling, low-confidence filtering | pytest |
| Adapter unit — face count | Haarcascade against 5 fixture JPGs (solo face / no face / multi face / edge case), consistent with OpenCV determinism | pytest |
| Adapter unit — repo | SqlFrameTextRepository CRUD, FK to frames, cascade on frame delete | pytest |
| Pipeline integration | VisualIntelligenceStage with stubbed OcrEngine, verify frame_texts persisted + links table receives source='ocr' rows | pytest |
| Integration — real OCR | One real JPG with embedded "Link in bio: example.com", verify end-to-end extraction → links table with source='ocr' | pytest (skip if model unavailable) |
| Content-shape unit | Face-count heuristic: ≥ 40% frames with ≥ 1 face = talking_head; 0 faces any frame = broll; mixed otherwise | pytest |
| CLI snapshot | `vidscope show <id>` includes on-screen text section + thumbnail path | pytest + CliRunner |
| Architecture | 9+ contracts green + new contract `vision-adapter-is-self-contained` | lint-imports |
| Performance | OCR on 30 frames must complete in < 20 s on reference CPU, documented in slice SUMMARY | pytest-benchmark |
| E2E live | `verify-m008.sh`: `vidscope add <Reel with on-screen text>` → assert frame_texts rows + new links row with source='ocr' + video.thumbnail_key populated + content_shape ∈ {talking_head, broll, mixed} | bash + real network |

## Requirements Mapping

- Closes R047 (OCR + frame_texts), R048 (canonical thumbnail), R049 (content_shape).
- Feeds M007's link extraction from a new source.
- Graceful degradation: if `rapidocr-onnxruntime` not installed, VisualIntelligenceStage emits SKIPPED status and the rest of the pipeline is unaffected. Doctor reports the status.

## Out of Scope (explicit)

- No object/brand detection (YOLO/CLIP) — OCR is the 80% signal; object detection is a future additive milestone.
- No face recognition / identity — only face *count* (no biometric template stored).
- No GPU path — ONNX CPU only in M008. A `VisionBackend` seam could be added later if needed.
- No image-captioning LLMs (Florence-2, LLaVA) — out of the zero-cost scope (D010).
