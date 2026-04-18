---
slice: S02
plan: P01
phase: M008/S02
plan_id: S02-P01
wave: 2
depends_on: [S01-P01]
requirements: [R047]
files_modified:
  - src/vidscope/pipeline/stages/visual_intelligence.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/pipeline/stages/metadata_extract.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/pipeline/stages/test_visual_intelligence.py
  - tests/unit/pipeline/stages/test_metadata_extract_stage.py
  - tests/integration/pipeline/__init__.py
  - tests/integration/pipeline/test_visual_intelligence_stage.py
autonomous: true
must_haves:
  truths:
    - "VisualIntelligenceStage exists at src/vidscope/pipeline/stages/visual_intelligence.py with name = StageName.VISUAL_INTELLIGENCE.value"
    - "Stage is_satisfied returns True when uow.frame_texts.has_any_for_video(ctx.video_id) is True"
    - "Stage execute runs OcrEngine.extract_text on every frame in uow.frames.list_for_video, persists FrameText rows via uow.frame_texts.add_many_for_frame"
    - "Stage execute feeds OCR text through LinkExtractor and appends ocr-sourced Link rows to uow.links with source='ocr' and position_ms=frame.timestamp_ms"
    - "Stage execute returns StageResult with skipped=True + message='OCR engine unavailable' when OcrEngine returns [] for every frame AND the underlying engine reports unavailable (detected via _unavailable flag OR by empty results when at least one frame exists)"
    - "container.build_container wires VisualIntelligenceStage between FramesStage and MetadataExtractStage (order: ingest, transcribe, frames, analyze, visual_intelligence, metadata_extract, index — 7 stages matching the StageName enum order)"
    - "MetadataExtractStage.is_satisfied no longer triggers on OCR-only links; only description or transcript links count toward satisfaction"
  artifacts:
    - path: "src/vidscope/pipeline/stages/visual_intelligence.py"
      provides: "VisualIntelligenceStage class implementing Stage protocol"
      contains: "class VisualIntelligenceStage"
    - path: "src/vidscope/pipeline/stages/__init__.py"
      provides: "VisualIntelligenceStage export"
      contains: "VisualIntelligenceStage"
    - path: "src/vidscope/infrastructure/container.py"
      provides: "Wired visual_intelligence_stage with RapidOcrEngine + RegexLinkExtractor"
      contains: "VisualIntelligenceStage"
  key_links:
    - from: "src/vidscope/pipeline/stages/visual_intelligence.py"
      to: "vidscope.ports.OcrEngine"
      via: "constructor injection"
      pattern: "ocr_engine: OcrEngine"
    - from: "src/vidscope/pipeline/stages/visual_intelligence.py"
      to: "vidscope.ports.LinkExtractor"
      via: "constructor injection"
      pattern: "link_extractor: LinkExtractor"
    - from: "src/vidscope/pipeline/stages/visual_intelligence.py"
      to: "uow.frame_texts.add_many_for_frame / uow.links.add_many_for_video"
      via: "write path in execute()"
      pattern: "uow.frame_texts.add_many_for_frame"
    - from: "src/vidscope/infrastructure/container.py"
      to: "VisualIntelligenceStage + RapidOcrEngine"
      via: "stages=[...] list argument to PipelineRunner"
      pattern: "visual_intelligence_stage"
---

<objective>
Livrer la pipeline stage centrale de M008 : `VisualIntelligenceStage`. Elle lit les frames déjà persistées par `FramesStage`, exécute l'`OcrEngine` sur chacune, persiste les `FrameText` via `FrameTextRepository`, puis fait passer le texte OCR à travers le `LinkExtractor` existant (M007) pour alimenter la table `links` avec `source='ocr'` et `position_ms=frame.timestamp_ms`. Le stage est inséré entre `FramesStage` et `MetadataExtractStage` dans l'ordre canonique — les liens OCR sont produits AVANT metadata_extract mais `MetadataExtractStage.is_satisfied` est ajusté pour ne pas se déclencher uniquement sur les liens `source='ocr'` (sinon metadata_extract skipperait à tort quand il y a OCR mais ni description ni transcript).

Dégradation gracieuse : si `OcrEngine` retourne `[]` pour toutes les frames ET que le projet détecte que la lib n'est pas installée, `execute` retourne `StageResult(skipped=True, message="OCR engine unavailable — rapidocr-onnxruntime not installed")`. Si OCR produit du texte sur certaines frames mais pas d'autres, c'est un SUCCÈS normal. Si OCR est disponible mais aucune frame n'a de texte détectable (cas fréquent pour du B-roll), c'est aussi un SUCCÈS (on persiste 0 rows).

Idempotence : `is_satisfied` vérifie `uow.frame_texts.has_any_for_video(ctx.video_id)` — si au moins un frame_text existe, on skip. Rejouer `vidscope add` sur une vidéo déjà traitée par M008 ne re-lance pas l'OCR.

Purpose: transformer les frames statiques en signal structuré réutilisable (recherche on-screen text + detection des URLs de type "link in bio"). C'est LE signal différenciant de M008.

Output: 1 nouvelle stage + 1 ajustement de MetadataExtractStage + wiring container + 15+ tests unitaires et integration.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M008/M008-ROADMAP.md
@.gsd/milestones/M008/M008-RESEARCH.md
@.gsd/milestones/M008/slices/S01/S01-P01-SUMMARY.md

<!-- Patterns to mirror -->
@src/vidscope/pipeline/stages/metadata_extract.py
@src/vidscope/pipeline/stages/frames.py
@src/vidscope/pipeline/stages/index.py
@src/vidscope/ports/pipeline.py
@src/vidscope/ports/link_extractor.py
@src/vidscope/ports/ocr_engine.py
@src/vidscope/ports/unit_of_work.py
@src/vidscope/infrastructure/container.py
@src/vidscope/domain/entities.py
</context>

<interfaces>
<!-- Contracts the executor will consume -->

From src/vidscope/pipeline/stages/metadata_extract.py (pattern to mirror):
```python
class MetadataExtractStage:
    name: str = StageName.METADATA_EXTRACT.value

    def __init__(self, *, link_extractor: LinkExtractor) -> None:
        self._extractor = link_extractor

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        if ctx.video_id is None:
            return False
        return uow.links.has_any_for_video(ctx.video_id)

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        ...
        persisted = uow.links.add_many_for_video(ctx.video_id, links)
        return StageResult(message=f"extracted {len(persisted)} link(s)")
```

From src/vidscope/ports/ocr_engine.py (from S01-P01):
```python
class OcrEngine(Protocol):
    def extract_text(self, image_path: str, *, min_confidence: float = 0.5) -> list[OcrLine]: ...

@dataclass(frozen=True, slots=True)
class OcrLine:
    text: str
    confidence: float
    bbox: str | None = None
```

From src/vidscope/ports/unit_of_work.py (from S01-P01):
```python
class UnitOfWork(Protocol):
    frames: FrameRepository
    frame_texts: FrameTextRepository
    links: LinkRepository
    videos: VideoRepository
    ...
```

From src/vidscope/ports/storage.py:
```python
class MediaStorage(Protocol):
    def resolve(self, key: str) -> Path: ...
```

From src/vidscope/domain/entities.py:
```python
@dataclass(frozen=True, slots=True)
class Frame:
    video_id: VideoId
    image_key: str
    timestamp_ms: int
    is_keyframe: bool = False
    id: int | None = None
    ...

@dataclass(frozen=True, slots=True)
class FrameText:
    video_id: VideoId
    frame_id: int
    text: str
    confidence: float
    bbox: str | None = None
    id: int | None = None
    ...

@dataclass(frozen=True, slots=True)
class Link:
    video_id: VideoId
    url: str
    normalized_url: str
    source: str
    position_ms: int | None = None
    ...
```
</interfaces>

<tasks>

<task id="T01-visual-intelligence-stage" type="auto" tdd="true">
  <name>T01: Implement VisualIntelligenceStage (OCR + LinkExtractor + persistence)</name>

  <read_first>
    - `src/vidscope/pipeline/stages/metadata_extract.py` (entire file, 138 lines) — the EXACT structural template. VisualIntelligenceStage follows the same is_satisfied/execute pattern with the same raising-on-missing-video_id contract.
    - `src/vidscope/pipeline/stages/frames.py` (entire file, 144 lines) — how a stage resolves `media_key` via MediaStorage and iterates (we'll iterate over frames, not media_key, but the MediaStorage.resolve pattern is identical).
    - `src/vidscope/ports/pipeline.py` lines 100-113 — `PipelineContext` fields + `StageResult` fields (skipped, message).
    - `src/vidscope/ports/ocr_engine.py` (from S01-P01) — OcrEngine protocol + OcrLine.
    - `src/vidscope/ports/storage.py` — MediaStorage.resolve returns Path.
    - `src/vidscope/domain/errors.py` lines 161-180 — `FrameExtractionError` is stage-labeled to FRAMES. We need a NEW error type OR we use `IndexingError`. Decision: raise no new stage-level DomainError for OCR — the stage catches all per-frame exceptions internally and returns an empty list. Only on structural failures (ctx.video_id is None, uow write failure) does it raise. For those, wrap as generic `DomainError` with `stage=StageName.VISUAL_INTELLIGENCE` via `RuntimeError → ... → StageCrashError` path. Since no `VisualIntelligenceError` exists and creating one requires a domain errors update, we'll use `IndexingError` with an explicit note — this matches the pattern where MetadataExtractStage raises IndexingError on missing video_id. (Accepted trade-off: the stage label will be `INDEX` in the message; the runner translates the stage name from `stage.name` anyway. See `_resolve_stage_phase` in runner.py.)

    WAIT — better approach: raise `IndexingError` ONLY for ctx.video_id missing (same as MetadataExtractStage), and let StorageError bubble up naturally from UoW writes (it's a DomainError so the runner catches it). NO new error class.

    - `src/vidscope/adapters/text/regex_link_extractor.py` — RegexLinkExtractor usage: `extractor.extract(text, source="description")` returns `list[RawLink]` where each has url/normalized_url/source/position_ms=None. We MUST override position_ms=frame.timestamp_ms for OCR-sourced links.
    - `src/vidscope/pipeline/stages/__init__.py` — add the new stage to `__all__` and import list.
    - `tests/unit/pipeline/stages/test_metadata_extract_stage.py` — look at fixture patterns used (FakeUoW, stubbed repositories).
  </read_first>

  <behavior>
    - Test 1 (is_satisfied true when frame_texts exist): `uow.frame_texts.has_any_for_video` returns True → is_satisfied returns True.
    - Test 2 (is_satisfied false when ctx.video_id None): returns False.
    - Test 3 (is_satisfied false when no frame_texts): returns False.
    - Test 4 (execute with no frames): returns StageResult(skipped=True) with message "no frames to OCR".
    - Test 5 (execute with 3 frames, all OCR returns []): persists 0 frame_texts, 0 links, returns StageResult with message="OCR produced no text for 3 frames" and skipped=False (ran successfully, empty result is valid).
    - Test 6 (execute with 2 frames, each returns 1 OcrLine, text contains no URL): persists 2 FrameText rows, 0 Link rows. message="extracted 2 text block(s), 0 link(s) across 2 frame(s)".
    - Test 7 (execute with 1 frame returning "Link in bio: example.com"): persists 1 FrameText, 1 Link with source='ocr' and position_ms=frame.timestamp_ms.
    - Test 8 (multiple frames multiple URLs): persists K FrameText, N Links where each OCR-sourced Link carries the correct timestamp_ms of its parent frame.
    - Test 9 (ctx.video_id is None): raises IndexingError with message containing "visual_intelligence stage requires ctx.video_id".
    - Test 10 (OCR engine marked unavailable AND zero frames produce text): returns StageResult(skipped=True, message matches "rapidocr-onnxruntime not installed").
    - Test 11 (MediaStorage.resolve of frame.image_key returns Path passed to extract_text): mock MediaStorage to return a known path, assert OcrEngine.extract_text is called with str(path).
    - Test 12 (link dedup across frames): if the same URL appears in two frames' OCR text, it's inserted twice (with different position_ms) because `LinkRepository.add_many_for_video` dedups by `(normalized_url, source)` within one call — so same source='ocr' same normalized_url → deduplicated. Expected: only ONE Link row stored. Accept this as correct behavior — document in the action.
  </behavior>

  <action>
  **Step A — Create `src/vidscope/pipeline/stages/visual_intelligence.py`:**

  ```python
  """VisualIntelligenceStage — sixth stage of the pipeline (M008/R047).

  Runs the :class:`~vidscope.ports.ocr_engine.OcrEngine` port on every
  :class:`Frame` already persisted by :class:`FramesStage`, writes
  :class:`FrameText` rows via :attr:`UnitOfWork.frame_texts`, and
  routes the OCR text through the :class:`~vidscope.ports.LinkExtractor`
  port (M007) to append ``source='ocr'`` rows to :attr:`UnitOfWork.links`
  carrying ``position_ms = frame.timestamp_ms``.

  Positioned between :class:`FramesStage` and
  :class:`MetadataExtractStage` in the canonical pipeline (see
  :class:`~vidscope.domain.StageName`).

  Resume-from-failure
  -------------------
  ``is_satisfied`` returns True when at least one
  :class:`FrameText` row exists for the video. Re-runs of
  ``vidscope add`` skip OCR entirely once it has succeeded.

  Graceful degradation
  --------------------
  When the underlying OCR engine is unavailable (``rapidocr-onnxruntime``
  not installed), :meth:`OcrEngine.extract_text` returns ``[]`` for every
  call. The stage then emits a SKIPPED StageResult with a message
  pointing at the optional install. This keeps the rest of the pipeline
  working on environments without the vision extra.
  """

  from __future__ import annotations

  import logging
  from pathlib import Path

  from vidscope.domain import (
      FrameText,
      IndexingError,
      Link,
      StageName,
  )
  from vidscope.ports import (
      LinkExtractor,
      MediaStorage,
      PipelineContext,
      StageResult,
      UnitOfWork,
  )
  from vidscope.ports.ocr_engine import OcrEngine

  _logger = logging.getLogger(__name__)

  __all__ = ["VisualIntelligenceStage"]


  class VisualIntelligenceStage:
      """Sixth stage — OCR every frame + extract on-screen URLs."""

      name: str = StageName.VISUAL_INTELLIGENCE.value

      def __init__(
          self,
          *,
          ocr_engine: OcrEngine,
          link_extractor: LinkExtractor,
          media_storage: MediaStorage,
          min_confidence: float = 0.5,
      ) -> None:
          self._ocr = ocr_engine
          self._extractor = link_extractor
          self._media_storage = media_storage
          self._min_confidence = min_confidence

      # ------------------------------------------------------------------
      # Stage protocol
      # ------------------------------------------------------------------

      def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
          """Return True when frame_texts already exist for this video."""
          if ctx.video_id is None:
              return False
          return uow.frame_texts.has_any_for_video(ctx.video_id)

      def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
          """Run OCR on each frame, persist text, extract + persist links."""
          if ctx.video_id is None:
              raise IndexingError(
                  "visual_intelligence stage requires ctx.video_id; "
                  "ingest must run first"
              )

          frames = uow.frames.list_for_video(ctx.video_id)
          if not frames:
              return StageResult(
                  skipped=True,
                  message="no frames to OCR — frames stage produced nothing",
              )

          total_text_blocks = 0
          all_ocr_links: list[Link] = []
          # Track frames that received at least one OcrLine — used
          # for SKIPPED detection when the engine is unavailable.
          frames_with_text = 0

          for frame in frames:
              if frame.id is None:
                  # Defensive: FramesStage persists via add_many which
                  # populates ids; a None here would be a contract
                  # violation upstream. Skip rather than fail.
                  _logger.warning(
                      "visual_intelligence: frame without id for video %s, "
                      "skipping",
                      ctx.video_id,
                  )
                  continue

              try:
                  resolved = self._media_storage.resolve(frame.image_key)
              except Exception as exc:  # noqa: BLE001
                  _logger.warning(
                      "visual_intelligence: failed to resolve %s for video %s: %s",
                      frame.image_key,
                      ctx.video_id,
                      exc,
                  )
                  continue
              frame_path = resolved if isinstance(resolved, Path) else Path(str(resolved))
              lines = self._ocr.extract_text(
                  str(frame_path), min_confidence=self._min_confidence
              )
              if not lines:
                  continue
              frames_with_text += 1

              # Persist the text blocks for this frame. One UoW-scoped
              # insert per frame is fine — frames are at most 30 per
              # video so worst case is 30 small inserts inside one
              # transaction.
              frame_texts = [
                  FrameText(
                      video_id=ctx.video_id,
                      frame_id=frame.id,
                      text=line.text,
                      confidence=line.confidence,
                      bbox=line.bbox,
                  )
                  for line in lines
              ]
              uow.frame_texts.add_many_for_frame(
                  frame.id, ctx.video_id, frame_texts
              )
              total_text_blocks += len(frame_texts)

              # Feed the concatenated text through LinkExtractor. Each
              # produced RawLink inherits position_ms from this frame.
              concatenated = " ".join(line.text for line in lines)
              for raw in self._extractor.extract(concatenated, source="ocr"):
                  all_ocr_links.append(
                      Link(
                          video_id=ctx.video_id,
                          url=raw["url"],
                          normalized_url=raw["normalized_url"],
                          source="ocr",
                          position_ms=frame.timestamp_ms,
                      )
                  )

          # Persist all OCR-sourced links in one batched insert. The
          # LinkRepository dedups by (normalized_url, source) within
          # the call — same URL across multiple frames becomes ONE
          # row (position_ms is the first-seen frame's timestamp).
          persisted_links = uow.links.add_many_for_video(
              ctx.video_id, all_ocr_links
          )

          # Graceful-degradation detection: if NO frame produced any
          # text, the OCR engine is either (a) unavailable/not installed
          # or (b) simply saw no text (valid B-roll case). We cannot
          # distinguish (a) from (b) purely from the result — the
          # OcrEngine port returns [] in both cases by contract. We
          # peek at a sentinel attribute (_unavailable) when present;
          # otherwise we report the empty result as a normal success.
          engine_marked_unavailable = getattr(self._ocr, "_unavailable", False)
          if frames_with_text == 0 and engine_marked_unavailable:
              return StageResult(
                  skipped=True,
                  message=(
                      "OCR engine unavailable — rapidocr-onnxruntime "
                      "not installed. Install with: uv sync --extra vision"
                  ),
              )

          if total_text_blocks == 0:
              return StageResult(
                  message=f"OCR produced no text for {len(frames)} frames"
              )

          return StageResult(
              message=(
                  f"extracted {total_text_blocks} text block(s), "
                  f"{len(persisted_links)} link(s) across {len(frames)} frame(s)"
              )
          )
  ```

  **Step B — Update `src/vidscope/pipeline/stages/__init__.py`:**

  1. Add import `from vidscope.pipeline.stages.visual_intelligence import VisualIntelligenceStage`.
  2. Add `"VisualIntelligenceStage"` to `__all__` in alphabetical order.

  **Step C — Tests:**

  Create `tests/unit/pipeline/stages/test_visual_intelligence.py`. Use the same FakeUoW / FakeRepository pattern already established for other stage tests. Structure:

  ```python
  """Unit tests for VisualIntelligenceStage."""

  from __future__ import annotations

  from dataclasses import dataclass, field
  from pathlib import Path
  from typing import Any
  from unittest.mock import MagicMock

  import pytest

  from vidscope.adapters.text import RegexLinkExtractor
  from vidscope.domain import (
      Frame,
      FrameText,
      IndexingError,
      Link,
      Platform,
      PlatformId,
      VideoId,
  )
  from vidscope.pipeline.stages import VisualIntelligenceStage
  from vidscope.ports import PipelineContext, StageResult
  from vidscope.ports.ocr_engine import OcrEngine, OcrLine


  # -- Fakes -----------------------------------------------------------------

  class _FakeOcrEngine:
      """Stub OcrEngine returning a deterministic per-image result."""

      def __init__(self, results: dict[str, list[OcrLine]] | None = None) -> None:
          self._results = results or {}
          self._unavailable = False
          self.calls: list[tuple[str, float]] = []

      def extract_text(
          self, image_path: str, *, min_confidence: float = 0.5
      ) -> list[OcrLine]:
          self.calls.append((image_path, min_confidence))
          return self._results.get(image_path, [])


  class _UnavailableOcrEngine(_FakeOcrEngine):
      def __init__(self) -> None:
          super().__init__()
          self._unavailable = True


  @dataclass
  class _FakeFrameTextRepo:
      rows: list[FrameText] = field(default_factory=list)
      next_id: int = 1

      def add_many_for_frame(
          self, frame_id: int, video_id: VideoId, texts: list[FrameText]
      ) -> list[FrameText]:
          stored = []
          for t in texts:
              ft = FrameText(
                  video_id=t.video_id,
                  frame_id=t.frame_id,
                  text=t.text,
                  confidence=t.confidence,
                  bbox=t.bbox,
                  id=self.next_id,
              )
              self.next_id += 1
              self.rows.append(ft)
              stored.append(ft)
          return stored

      def list_for_video(self, video_id: VideoId) -> list[FrameText]:
          return [r for r in self.rows if r.video_id == video_id]

      def has_any_for_video(self, video_id: VideoId) -> bool:
          return any(r.video_id == video_id for r in self.rows)

      def find_video_ids_by_text(self, query: str, *, limit: int = 50) -> list[VideoId]:
          return []


  @dataclass
  class _FakeFrameRepo:
      frames: list[Frame] = field(default_factory=list)

      def add_many(self, frames: list[Frame]) -> list[Frame]:
          self.frames.extend(frames)
          return list(frames)

      def list_for_video(self, video_id: VideoId) -> list[Frame]:
          return [f for f in self.frames if f.video_id == video_id]


  @dataclass
  class _FakeLinkRepo:
      rows: list[Link] = field(default_factory=list)
      next_id: int = 1

      def add_many_for_video(
          self, video_id: VideoId, links: list[Link]
      ) -> list[Link]:
          seen: set[tuple[str, str]] = set()
          added: list[Link] = []
          for link in links:
              key = (link.normalized_url, link.source)
              if key in seen:
                  continue
              seen.add(key)
              new = Link(
                  video_id=link.video_id,
                  url=link.url,
                  normalized_url=link.normalized_url,
                  source=link.source,
                  position_ms=link.position_ms,
                  id=self.next_id,
              )
              self.next_id += 1
              added.append(new)
              self.rows.append(new)
          return added

      def list_for_video(self, video_id: VideoId, *, source: str | None = None) -> list[Link]:
          out = [r for r in self.rows if r.video_id == video_id]
          if source is not None:
              out = [r for r in out if r.source == source]
          return out

      def has_any_for_video(self, video_id: VideoId) -> bool:
          return any(r.video_id == video_id for r in self.rows)

      def find_video_ids_with_any_link(self, *, limit: int = 50) -> list[VideoId]:
          return []


  @dataclass
  class _FakeUoW:
      frames: _FakeFrameRepo
      frame_texts: _FakeFrameTextRepo
      links: _FakeLinkRepo

      def __enter__(self) -> "_FakeUoW":
          return self

      def __exit__(self, *args: Any) -> None:
          pass


  class _FakeMediaStorage:
      def __init__(self, base: Path) -> None:
          self._base = base

      def resolve(self, key: str) -> Path:
          return self._base / key


  # -- Helpers ---------------------------------------------------------------

  def _ctx(video_id: int = 1) -> PipelineContext:
      c = PipelineContext(source_url="https://example.com/v1")
      c.video_id = VideoId(video_id)
      c.platform = Platform.YOUTUBE
      c.platform_id = PlatformId("abc")
      return c


  def _stage(
      engine: OcrEngine | None = None,
      tmp_path: Path | None = None,
  ) -> tuple[VisualIntelligenceStage, _FakeUoW]:
      engine = engine or _FakeOcrEngine()
      media = _FakeMediaStorage(tmp_path or Path("/tmp"))
      stage = VisualIntelligenceStage(
          ocr_engine=engine,
          link_extractor=RegexLinkExtractor(),
          media_storage=media,
      )
      uow = _FakeUoW(
          frames=_FakeFrameRepo(),
          frame_texts=_FakeFrameTextRepo(),
          links=_FakeLinkRepo(),
      )
      return stage, uow


  # -- Tests -----------------------------------------------------------------

  class TestIsSatisfied:
      def test_returns_false_when_video_id_missing(self) -> None:
          stage, uow = _stage()
          ctx = PipelineContext(source_url="x")
          assert stage.is_satisfied(ctx, uow) is False  # type: ignore[arg-type]

      def test_returns_false_when_no_frame_texts(self) -> None:
          stage, uow = _stage()
          assert stage.is_satisfied(_ctx(), uow) is False  # type: ignore[arg-type]

      def test_returns_true_when_frame_texts_exist(self) -> None:
          stage, uow = _stage()
          uow.frame_texts.rows.append(
              FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=0.9, id=1)
          )
          assert stage.is_satisfied(_ctx(), uow) is True  # type: ignore[arg-type]


  class TestExecuteContractViolations:
      def test_raises_indexing_error_when_video_id_missing(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          ctx = PipelineContext(source_url="x")
          with pytest.raises(IndexingError) as exc_info:
              stage.execute(ctx, uow)  # type: ignore[arg-type]
          assert "visual_intelligence" in str(exc_info.value)
          assert "video_id" in str(exc_info.value)


  class TestExecuteHappyPaths:
      def test_no_frames_returns_skipped(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert result.skipped is True
          assert "no frames" in result.message.lower()

      def test_all_frames_empty_ocr_returns_ok_zero(self, tmp_path: Path) -> None:
          engine = _FakeOcrEngine()  # no results for any path
          stage, uow = _stage(engine=engine, tmp_path=tmp_path)
          for i, ts in enumerate([0, 1000, 2000]):
              uow.frames.frames.append(
                  Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=ts, id=i + 1)
              )
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert result.skipped is False
          assert "no text" in result.message.lower()
          assert len(uow.frame_texts.rows) == 0
          assert len(uow.links.rows) == 0
          # Verify engine was called for each frame
          assert len(engine.calls) == 3

      def test_one_frame_with_text_no_url(self, tmp_path: Path) -> None:
          engine = _FakeOcrEngine(
              results={
                  str(tmp_path / "f/0.jpg"): [
                      OcrLine(text="Hello world", confidence=0.9),
                  ]
              }
          )
          stage, uow = _stage(engine=engine, tmp_path=tmp_path)
          uow.frames.frames.append(
              Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
          )
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert result.skipped is False
          assert len(uow.frame_texts.rows) == 1
          assert uow.frame_texts.rows[0].text == "Hello world"
          assert len(uow.links.rows) == 0

      def test_frame_with_link_persists_ocr_link(self, tmp_path: Path) -> None:
          engine = _FakeOcrEngine(
              results={
                  str(tmp_path / "f/0.jpg"): [
                      OcrLine(text="Link in bio: https://example.com", confidence=0.95),
                  ]
              }
          )
          stage, uow = _stage(engine=engine, tmp_path=tmp_path)
          uow.frames.frames.append(
              Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=2500, id=1)
          )
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert result.skipped is False
          assert len(uow.frame_texts.rows) == 1
          assert len(uow.links.rows) == 1
          link = uow.links.rows[0]
          assert link.source == "ocr"
          assert link.position_ms == 2500
          assert "example.com" in link.normalized_url

      def test_multiple_frames_multiple_links(self, tmp_path: Path) -> None:
          engine = _FakeOcrEngine(
              results={
                  str(tmp_path / "f/0.jpg"): [OcrLine(text="Visit promo.com now", confidence=0.9)],
                  str(tmp_path / "f/1.jpg"): [OcrLine(text="Also: https://shop.net/deal", confidence=0.85)],
              }
          )
          stage, uow = _stage(engine=engine, tmp_path=tmp_path)
          uow.frames.frames.append(Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=1000, id=1))
          uow.frames.frames.append(Frame(video_id=VideoId(1), image_key="f/1.jpg", timestamp_ms=3000, id=2))
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert result.skipped is False
          assert len(uow.frame_texts.rows) == 2
          # Each frame's links should carry its own timestamp
          timestamps = {link.position_ms for link in uow.links.rows}
          assert timestamps == {1000, 3000}

      def test_same_url_across_frames_deduplicated(self, tmp_path: Path) -> None:
          engine = _FakeOcrEngine(
              results={
                  str(tmp_path / "f/0.jpg"): [OcrLine(text="See example.com", confidence=0.9)],
                  str(tmp_path / "f/1.jpg"): [OcrLine(text="example.com again", confidence=0.9)],
              }
          )
          stage, uow = _stage(engine=engine, tmp_path=tmp_path)
          uow.frames.frames.append(Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=1000, id=1))
          uow.frames.frames.append(Frame(video_id=VideoId(1), image_key="f/1.jpg", timestamp_ms=2000, id=2))
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          # add_many_for_video dedups by (normalized_url, source) — one row only
          assert len(uow.links.rows) == 1


  class TestExecuteUnavailableEngine:
      def test_unavailable_engine_with_frames_returns_skipped(self, tmp_path: Path) -> None:
          engine = _UnavailableOcrEngine()
          stage, uow = _stage(engine=engine, tmp_path=tmp_path)
          uow.frames.frames.append(
              Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
          )
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert result.skipped is True
          assert "rapidocr" in result.message.lower()
          assert len(uow.frame_texts.rows) == 0


  class TestExecuteMediaResolutionErrors:
      def test_resolve_exception_is_skipped_per_frame(self, tmp_path: Path) -> None:
          class _BrokenStorage:
              def resolve(self, key: str) -> Path:
                  raise RuntimeError("disk unplugged")

          engine = _FakeOcrEngine()
          stage = VisualIntelligenceStage(
              ocr_engine=engine,
              link_extractor=RegexLinkExtractor(),
              media_storage=_BrokenStorage(),  # type: ignore[arg-type]
          )
          uow = _FakeUoW(
              frames=_FakeFrameRepo(),
              frame_texts=_FakeFrameTextRepo(),
              links=_FakeLinkRepo(),
          )
          uow.frames.frames.append(
              Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
          )
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          # No crash — just skipped frame
          assert result.skipped is False
          assert len(uow.frame_texts.rows) == 0
  ```
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/pipeline/stages/visual_intelligence.py`
    - `grep -q 'class VisualIntelligenceStage' src/vidscope/pipeline/stages/visual_intelligence.py` exit 0
    - `grep -q 'name: str = StageName.VISUAL_INTELLIGENCE.value' src/vidscope/pipeline/stages/visual_intelligence.py` exit 0
    - `grep -q '"VisualIntelligenceStage"' src/vidscope/pipeline/stages/__init__.py` exit 0
    - `uv run python -c "from vidscope.pipeline.stages import VisualIntelligenceStage; print(VisualIntelligenceStage.name)"` prints `visual_intelligence`
    - `uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py -x -q` exit 0 (≥ 10 tests green)
    - `uv run pytest tests/unit/pipeline -q` exit 0 (no regression on other stage tests)
    - `uv run lint-imports` exit 0 (pipeline-has-no-adapters still green — stage imports only ports)
    - `uv run mypy src` exit 0
    <automated>uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py -q</automated>
  </acceptance_criteria>
</task>

<task id="T02-metadata-extract-adjustment" type="auto" tdd="true">
  <name>T02: Adjust MetadataExtractStage.is_satisfied to ignore OCR-only links</name>

  <read_first>
    - `src/vidscope/pipeline/stages/metadata_extract.py` (entire file, 138 lines) — current `is_satisfied` checks `uow.links.has_any_for_video`. After M008/S02 wiring, `visual_intelligence` runs BEFORE `metadata_extract` and populates `links` with `source='ocr'`. If `metadata_extract` then skips because ANY link exists, it will never extract description/transcript links on a fresh video — bug.
    - `src/vidscope/ports/repositories.py` — `LinkRepository.list_for_video(video_id, *, source=None)` accepts a source filter. We can use it to count only non-ocr links.
    - `tests/unit/pipeline/test_metadata_extract_stage.py` — the existing tests; we MUST add new ones for the OCR-only case and preserve existing behavior.
  </read_first>

  <behavior>
    - Test 1 (existing behavior preserved): if description/transcript links exist (source ∈ {description, transcript}), is_satisfied returns True.
    - Test 2 (new — OCR-only case): if ONLY source='ocr' links exist, is_satisfied returns False (so the stage re-extracts from description + transcript).
    - Test 3 (mixed): if BOTH ocr-source and description-source exist, is_satisfied returns True.
    - Test 4 (no links at all): is_satisfied returns False (unchanged).
  </behavior>

  <action>
  **Step A — Update `MetadataExtractStage.is_satisfied` in `src/vidscope/pipeline/stages/metadata_extract.py`:**

  Replace the existing `is_satisfied` method with:

  ```python
  def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
      """Return True when at least one NON-OCR link exists for
      ``ctx.video_id``.

      Rationale: M008/S02's :class:`VisualIntelligenceStage` runs
      BEFORE this stage and populates ``links`` rows with
      ``source='ocr'``. If we checked ``has_any_for_video`` (any
      source), this stage would skip on a fresh video whenever OCR
      found a URL, and description/transcript links would never be
      extracted. The correct satisfaction check is "description or
      transcript links already exist" — both are this stage's
      outputs. OCR-sourced links are the responsibility of
      visual_intelligence and do not count.
      """
      if ctx.video_id is None:
          return False
      description_links = uow.links.list_for_video(ctx.video_id, source="description")
      if description_links:
          return True
      transcript_links = uow.links.list_for_video(ctx.video_id, source="transcript")
      return bool(transcript_links)
  ```

  Keep the rest of the file unchanged. Update the module docstring at the top (line 14+ "Resume-from-failure") to reflect the new condition:

  Replace the existing "Resume-from-failure" section:
  ```
  Resume-from-failure
  -------------------
  ``is_satisfied`` returns True when ``uow.links.has_any_for_video(video_id)``
  is True — re-runs of ``vidscope add <url>`` on an already-extracted
  video skip this stage entirely.
  ```

  with:
  ```
  Resume-from-failure
  -------------------
  ``is_satisfied`` returns True when at least one link with
  ``source in {'description', 'transcript'}`` exists for the video.
  OCR-sourced links (M008) are produced by :class:`VisualIntelligenceStage`
  which runs BEFORE this stage, so they must NOT count toward
  satisfaction — otherwise this stage would skip whenever OCR found a
  URL, and caption/transcript links would never be extracted.
  ```

  **Step B — Extend `tests/unit/pipeline/test_metadata_extract_stage.py`:**

  Add a new test class `TestIsSatisfiedOCRInteraction` near the existing is_satisfied tests. The existing test file already has fake repo patterns — mirror them. Tests:

  ```python
  class TestIsSatisfiedOCRInteraction:
      """M008/S02: OCR-only links must NOT satisfy metadata_extract."""

      def test_satisfied_when_description_link_exists(self) -> None:
          # build stage + fake uow with one source='description' link
          # assert is_satisfied == True
          ...

      def test_satisfied_when_transcript_link_exists(self) -> None:
          # build stage + fake uow with one source='transcript' link
          # assert is_satisfied == True
          ...

      def test_not_satisfied_when_only_ocr_links_exist(self) -> None:
          # build stage + fake uow with one source='ocr' link
          # assert is_satisfied == False
          ...

      def test_satisfied_when_ocr_and_description_coexist(self) -> None:
          # build stage + fake uow with source='ocr' AND source='description'
          # assert is_satisfied == True
          ...

      def test_not_satisfied_when_no_links(self) -> None:
          # empty uow.links → False (unchanged behaviour preserved)
          ...
  ```

  Use concrete Link instances via `Link(video_id=VideoId(1), url="...", normalized_url="...", source=..., position_ms=None, id=<N>)`. Re-use the `_FakeLinkRepo` pattern from the existing test file OR the one created in T01 — whichever is already in the test module.
  </action>

  <acceptance_criteria>
    - `grep -q 'source="description"' src/vidscope/pipeline/stages/metadata_extract.py` exit 0
    - `grep -q 'source="transcript"' src/vidscope/pipeline/stages/metadata_extract.py` exit 0
    - `uv run pytest tests/unit/pipeline/test_metadata_extract_stage.py -x -q` exit 0 (existing tests pass + new class green)
    - `uv run pytest tests/unit/pipeline -q` exit 0 (no regression)
    <automated>uv run pytest tests/unit/pipeline/test_metadata_extract_stage.py -q</automated>
  </acceptance_criteria>
</task>

<task id="T03-container-wiring-and-integration" type="auto">
  <name>T03: Wire VisualIntelligenceStage into container.build_container + integration test</name>

  <read_first>
    - `src/vidscope/infrastructure/container.py` (entire file, 250 lines) — specifically the `build_container` function (lines 137-250). Look at the stage instantiation block (lines 205-224) and the `PipelineRunner(stages=[...])` list at lines 226-237.
    - `src/vidscope/pipeline/stages/__init__.py` — confirm `VisualIntelligenceStage` is exported (from T01).
    - `src/vidscope/adapters/vision/__init__.py` (from S01-P01) — `RapidOcrEngine` + `HaarcascadeFaceCounter` exports.
    - `tests/integration/` — existing integration tests (test_ingest_live.py, test_mcp_server.py). Integration pattern uses real adapters, real DB (in-memory or tmp file), marker `@pytest.mark.integration`.
    - `tests/integration/conftest.py` — shared fixtures for integration tests.
  </read_first>

  <action>
  **Step A — Update `src/vidscope/infrastructure/container.py`:**

  1. Add imports near the top (after the existing adapter imports around line 51):

  ```python
  from vidscope.adapters.vision import RapidOcrEngine
  ```

  2. Update the stages import block (lines 56-63) to include `VisualIntelligenceStage`:

  ```python
  from vidscope.pipeline.stages import (
      AnalyzeStage,
      FramesStage,
      IndexStage,
      IngestStage,
      MetadataExtractStage,
      TranscribeStage,
      VisualIntelligenceStage,
  )
  ```

  3. In `build_container` (after `metadata_extract_stage = MetadataExtractStage(...)` at line 221-223), insert the vision wiring BEFORE it:

  ```python
      # M008/S02 — vision stage runs AFTER frames and BEFORE
      # metadata_extract. RapidOcrEngine is lazy-loaded: the ONNX
      # model (~50MB) downloads on the first OCR call, not here.
      # If rapidocr-onnxruntime is not installed, the engine
      # returns [] for every frame and the stage emits SKIPPED
      # (see VisualIntelligenceStage.execute).
      ocr_engine = RapidOcrEngine()
      visual_intelligence_stage = VisualIntelligenceStage(
          ocr_engine=ocr_engine,
          link_extractor=link_extractor,  # reuse the same instance
          media_storage=media_storage,
      )
  ```

  Note: `link_extractor = RegexLinkExtractor()` already exists at line 220. Move its declaration UP (before both metadata_extract_stage and the new visual_intelligence_stage) to make the sharing explicit. The updated block should read:

  ```python
      link_extractor = RegexLinkExtractor()

      # M008/S02 — vision stage runs AFTER frames and BEFORE
      # metadata_extract. RapidOcrEngine is lazy-loaded.
      ocr_engine = RapidOcrEngine()
      visual_intelligence_stage = VisualIntelligenceStage(
          ocr_engine=ocr_engine,
          link_extractor=link_extractor,
          media_storage=media_storage,
      )

      metadata_extract_stage = MetadataExtractStage(
          link_extractor=link_extractor,
      )
  ```

  4. Update the `PipelineRunner(stages=[...])` list to INSERT `visual_intelligence_stage` between `analyze_stage` and `metadata_extract_stage`:

  ```python
      pipeline_runner = PipelineRunner(
          stages=[
              ingest_stage,
              transcribe_stage,
              frames_stage,
              analyze_stage,
              visual_intelligence_stage,  # NEW — M008/S02
              metadata_extract_stage,
              index_stage,
          ],
          unit_of_work_factory=_uow_factory,
          clock=clock,
      )
  ```

  Note: the stages list MUST match the StageName enum order: `ingest, transcribe, frames, analyze, visual_intelligence, metadata_extract, index` — exactly 7 members in this exact order (matches the enum order enforced by `_resolve_stage_phase` in runner.py).

  **Step B — Create `tests/integration/pipeline/__init__.py`** (empty marker) and `tests/integration/pipeline/test_visual_intelligence_stage.py`:

  ```python
  """Integration tests for VisualIntelligenceStage.

  Uses the real SqliteUnitOfWork + in-memory engine + a stubbed
  OcrEngine (we don't want to depend on rapidocr being installed in
  the test env). Verifies the full persistence path: FrameText rows
  land in the DB with FK cascade, FTS5 rows exist, and OCR-sourced
  Link rows are written to the links table with source='ocr' and
  position_ms correctly set.
  """

  from __future__ import annotations

  from pathlib import Path

  import pytest
  from sqlalchemy import create_engine, text

  from vidscope.adapters.sqlite.schema import init_db
  from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
  from vidscope.adapters.text import RegexLinkExtractor
  from vidscope.domain import (
      Frame,
      Platform,
      PlatformId,
      Video,
      VideoId,
  )
  from vidscope.pipeline.stages import VisualIntelligenceStage
  from vidscope.ports import PipelineContext
  from vidscope.ports.ocr_engine import OcrEngine, OcrLine


  class _StubOcr:
      def __init__(self, mapping: dict[str, list[OcrLine]]) -> None:
          self._mapping = mapping
          self._unavailable = False

      def extract_text(
          self, image_path: str, *, min_confidence: float = 0.5
      ) -> list[OcrLine]:
          return [
              line for line in self._mapping.get(image_path, [])
              if line.confidence >= min_confidence
          ]


  class _LocalMediaStorage:
      def __init__(self, base: Path) -> None:
          self._base = base

      def resolve(self, key: str) -> Path:
          return self._base / key


  @pytest.mark.integration
  class TestVisualIntelligenceIntegration:
      def test_persists_frame_texts_and_ocr_links(self, tmp_path: Path) -> None:
          # 1. Build a real SQLite UoW.
          engine = create_engine("sqlite:///:memory:")
          init_db(engine)

          # 2. Seed the DB with a video + frames.
          with SqliteUnitOfWork(engine) as uow:
              video = uow.videos.add(
                  Video(
                      platform=Platform.YOUTUBE,
                      platform_id=PlatformId("test-id-1"),
                      url="https://youtube.com/shorts/test-id-1",
                  )
              )
              assert video.id is not None
              vid_id = video.id
              frame_a = Path("frames/a.jpg")
              frame_b = Path("frames/b.jpg")
              uow.frames.add_many(
                  [
                      Frame(video_id=vid_id, image_key=str(frame_a), timestamp_ms=1000),
                      Frame(video_id=vid_id, image_key=str(frame_b), timestamp_ms=3000),
                  ]
              )

          # 3. Build the stage with stubbed OcrEngine keyed by resolved paths.
          resolved_a = str(tmp_path / "frames/a.jpg")
          resolved_b = str(tmp_path / "frames/b.jpg")
          stub = _StubOcr(
              {
                  resolved_a: [OcrLine(text="Visit example.com for promo", confidence=0.9)],
                  resolved_b: [OcrLine(text="Follow @alice", confidence=0.9)],
              }
          )
          stage = VisualIntelligenceStage(
              ocr_engine=stub,
              link_extractor=RegexLinkExtractor(),
              media_storage=_LocalMediaStorage(tmp_path),
          )

          # 4. Execute the stage in its own UoW transaction.
          ctx = PipelineContext(source_url="https://youtube.com/shorts/test-id-1")
          ctx.video_id = vid_id
          ctx.platform = Platform.YOUTUBE
          with SqliteUnitOfWork(engine) as uow:
              result = stage.execute(ctx, uow)

          assert result.skipped is False

          # 5. Verify persisted rows (open a fresh UoW).
          with SqliteUnitOfWork(engine) as uow:
              texts = uow.frame_texts.list_for_video(vid_id)
              assert len(texts) == 2
              text_values = {t.text for t in texts}
              assert "Visit example.com for promo" in text_values
              assert "Follow @alice" in text_values

              ocr_links = uow.links.list_for_video(vid_id, source="ocr")
              assert len(ocr_links) == 1
              assert "example.com" in ocr_links[0].normalized_url
              assert ocr_links[0].position_ms == 1000

          # 6. Verify FTS5 sync on frame_texts_fts.
          with engine.begin() as conn:
              count = conn.execute(
                  text(
                      "SELECT count(*) FROM frame_texts_fts "
                      "WHERE video_id = :v"
                  ),
                  {"v": int(vid_id)},
              ).scalar()
              assert count == 2

      def test_is_satisfied_after_execute(self, tmp_path: Path) -> None:
          engine = create_engine("sqlite:///:memory:")
          init_db(engine)
          with SqliteUnitOfWork(engine) as uow:
              video = uow.videos.add(
                  Video(
                      platform=Platform.YOUTUBE,
                      platform_id=PlatformId("test-id-2"),
                      url="https://youtube.com/shorts/x",
                  )
              )
              assert video.id is not None
              vid_id = video.id
              uow.frames.add_many(
                  [Frame(video_id=vid_id, image_key="frames/x.jpg", timestamp_ms=0)]
              )

          stub = _StubOcr(
              {
                  str(tmp_path / "frames/x.jpg"): [
                      OcrLine(text="Any text", confidence=0.9)
                  ]
              }
          )
          stage = VisualIntelligenceStage(
              ocr_engine=stub,
              link_extractor=RegexLinkExtractor(),
              media_storage=_LocalMediaStorage(tmp_path),
          )
          ctx = PipelineContext(source_url="x")
          ctx.video_id = vid_id

          with SqliteUnitOfWork(engine) as uow:
              stage.execute(ctx, uow)

          with SqliteUnitOfWork(engine) as uow:
              assert stage.is_satisfied(ctx, uow) is True
  ```
  </action>

  <acceptance_criteria>
    - `grep -q 'from vidscope.adapters.vision import RapidOcrEngine' src/vidscope/infrastructure/container.py` exit 0
    - `grep -q 'VisualIntelligenceStage' src/vidscope/infrastructure/container.py` exit 0
    - `grep -q 'visual_intelligence_stage' src/vidscope/infrastructure/container.py` exit 0
    - `uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); names = c.pipeline_runner.stage_names; assert names == ('ingest','transcribe','frames','analyze','visual_intelligence','metadata_extract','index'), names; print('ok')"` prints `ok`
    - `test -f tests/integration/pipeline/test_visual_intelligence_stage.py`
    - `uv run pytest tests/integration/pipeline -m integration -q` exit 0 (both integration tests green)
    - `uv run pytest -q` exit 0 (no regression on the default, non-integration suite)
    - `uv run lint-imports` exit 0
    - `uv run mypy src` exit 0
    <automated>uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); assert c.pipeline_runner.stage_names == ('ingest','transcribe','frames','analyze','visual_intelligence','metadata_extract','index')"</automated>
  </acceptance_criteria>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| OCR text → LinkExtractor regex | OCR-extracted text (arbitrary user-generated content captured on-screen) is fed to the M007 regex extractor; malicious text could attempt to exploit regex behaviour |
| Pipeline stage ordering | VisualIntelligenceStage must run BEFORE MetadataExtractStage; a reordering bug would silently break OCR→links flow |
| ctx.video_id → DB writes | Stage writes FrameText and Link rows tagged with ctx.video_id; a stale or wrong video_id would attach OCR data to the wrong video |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-M008-S02-01 | **Denial of Service (D)** | `RegexLinkExtractor.extract` fed with adversarial OCR text (ReDoS attempt) | mitigate | M007's `RegexLinkExtractor` uses bounded patterns (`[^\s<>"'\`{}|\\^\[\]]+` with no catastrophic backtracking — documented in M007). OCR-text concatenation is bounded by the frame's text blocks (at most a few hundred chars per frame). No change needed in M008; inherits M007 protection. |
| T-M008-S02-02 | **Tampering (T)** | Frame-to-video mismatch: a bug in is_satisfied or ctx propagation assigns OCR text to the wrong video_id | mitigate | `FrameText` carries `video_id` as a required field (not optional); `VisualIntelligenceStage.execute` always uses `ctx.video_id` (raising IndexingError when None). Unit tests T01 assert video_id correctness on every persisted row. Integration test T03 creates a real video, runs the stage, and asserts `list_for_video(vid_id)` returns the exact rows. |
| T-M008-S02-03 | **Denial of Service (D)** | Per-frame OCR hang (underlying ONNX model bug) blocks the whole pipeline | accept | M008 runs single-threaded, no timeout wrapper on `OcrEngine.extract_text`. The research target is <20s for 30 frames; in the worst case the pipeline is blocked but the DB is transactional — partial work is rolled back. Adding a timeout requires async runtime changes deferred to M011 ops. Documented in M008-RESEARCH §1.6. |
| T-M008-S02-04 | **Information Disclosure (I)** | OCR errors logged via `_logger.warning(...)` may expose image paths or partial OCR content | mitigate | Stage logs ONLY: (a) "frame without id" warning (no content), (b) MediaStorage resolve failures (file path only, no content), (c) nothing for OCR successes. The OCR adapter itself is audited in S01-P01 threat model (T-M008-S01-05). |
| T-M008-S02-05 | **Elevation of Privilege (E)** | Stage reordering bug in container.py inserts visual_intelligence AFTER metadata_extract, causing OCR links to never reach the pipeline | mitigate | Acceptance criterion in T03 asserts exact stage ordering: `('ingest','transcribe','frames','analyze','visual_intelligence','metadata_extract','index')`. `_resolve_stage_phase` in runner.py also validates stage.name is a valid StageName enum member. Integration test T03 runs a real pipeline and asserts OCR links land correctly. |
| T-M008-S02-06 | **Tampering (T)** | LinkRepository.add_many_for_video deduplicates by (normalized_url, source) — across-frame duplicates in OCR lose the per-frame timestamp | accept | Design choice: one URL = one row per source. Per-frame granularity (multiple rows for the same URL at different timestamps) would bloat the table with low value. The position_ms reported is the FIRST-seen frame (insertion order). Documented as test_same_url_across_frames_deduplicated in T01. |

</threat_model>

<verification>
```bash
# Unit tests
uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py -x -q
uv run pytest tests/unit/pipeline/test_metadata_extract_stage.py -x -q

# Integration
uv run pytest tests/integration/pipeline -m integration -q

# Container wiring
uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); assert c.pipeline_runner.stage_names == ('ingest','transcribe','frames','analyze','visual_intelligence','metadata_extract','index'); print('ok')"

# Full suite
uv run pytest -q

# Quality gates
uv run ruff check src tests
uv run mypy src
uv run lint-imports
```
</verification>

<success_criteria>
- `VisualIntelligenceStage` implements Stage protocol with is_satisfied + execute + name='visual_intelligence'.
- Stage persists FrameText rows and OCR-sourced Link rows atomically within one UoW per stage invocation.
- MetadataExtractStage.is_satisfied no longer triggers on OCR-only links.
- Container wires the stage in canonical order between analyze and metadata_extract.
- 15+ unit tests + 2 integration tests green.
- Zero regressions on existing pipeline tests.
- All 10 import-linter contracts green.
- mypy + ruff + pytest quality gates green.
</success_criteria>

<output>
After completion, create `.gsd/milestones/M008/slices/S02/S02-P01-SUMMARY.md` following the standard summary template.
</output>
