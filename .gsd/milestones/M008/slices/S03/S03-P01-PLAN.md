---
slice: S03
plan: P01
phase: M008/S03
plan_id: S03-P01
wave: 3
depends_on: [S01-P01, S02-P01]
requirements: [R048, R049]
files_modified:
  - src/vidscope/pipeline/stages/visual_intelligence.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/pipeline/stages/test_visual_intelligence.py
  - tests/unit/adapters/sqlite/test_video_repository.py
  - tests/integration/pipeline/test_visual_intelligence_stage.py
autonomous: true
must_haves:
  truths:
    - "VisualIntelligenceStage copies the middle frame (by index order) to the canonical storage key 'videos/{platform}/{platform_id}/thumb.jpg' via MediaStorage.store"
    - "VisualIntelligenceStage updates videos.thumbnail_key to that canonical storage key"
    - "VisualIntelligenceStage invokes FaceCounter on every frame and computes ContentShape from the resulting face counts using the 40% threshold heuristic"
    - "VisualIntelligenceStage updates videos.content_shape to one of {talking_head, broll, mixed, unknown}"
    - "classify_content_shape(face_counts) helper returns UNKNOWN when the list is empty, BROLL when all counts are zero, TALKING_HEAD when >=40% of frames have >=1 face, MIXED otherwise"
    - "VideoRepository.update_visual_metadata(video_id, thumbnail_key, content_shape) persists both columns in one UPDATE"
    - "container.build_container instantiates HaarcascadeFaceCounter and injects it into VisualIntelligenceStage"
    - "is_satisfied returns True only when BOTH frame_texts exist AND videos.thumbnail_key is populated AND videos.content_shape is populated (compound check — all three must be present for resume-skip)"
  artifacts:
    - path: "src/vidscope/pipeline/stages/visual_intelligence.py"
      provides: "Extended VisualIntelligenceStage — thumbnail copy + content_shape classification"
      contains: "classify_content_shape"
    - path: "src/vidscope/adapters/sqlite/video_repository.py"
      provides: "update_visual_metadata method on VideoRepositorySQLite"
      contains: "update_visual_metadata"
    - path: "src/vidscope/ports/repositories.py"
      provides: "update_visual_metadata on VideoRepository Protocol"
      contains: "update_visual_metadata"
  key_links:
    - from: "src/vidscope/pipeline/stages/visual_intelligence.py"
      to: "MediaStorage.store(thumbnail_key, source_path)"
      via: "copy-middle-frame path in execute()"
      pattern: "thumb.jpg"
    - from: "src/vidscope/pipeline/stages/visual_intelligence.py"
      to: "FaceCounter.count_faces"
      via: "per-frame call in the face-count loop"
      pattern: "face_counter.count_faces"
    - from: "src/vidscope/pipeline/stages/visual_intelligence.py"
      to: "uow.videos.update_visual_metadata"
      via: "single UPDATE at end of execute()"
      pattern: "update_visual_metadata"
---

<objective>
Étendre `VisualIntelligenceStage` pour couvrir les deux dernières capacités de M008 : (R048) thumbnail canonique et (R049) classification `content_shape` par heuristique face-count. Le même stage qui fait l'OCR s'occupe maintenant aussi de :

1. **Thumbnail canonique** — copier la frame du milieu (par index d'ordre dans `list_for_video`, pas par timestamp) vers la clé storage stable `videos/{platform}/{platform_id}/thumb.jpg`. La thumbnail doit survivre à un nettoyage éventuel des frames temporaires (D-05 du contexte M008) → c'est une COPIE, pas un lien symbolique.

2. **Content shape classification** — invoquer `FaceCounter.count_faces` sur chaque frame, agréger les counts en une liste, et dériver `ContentShape` via la règle : ≥40% frames avec ≥1 visage = `TALKING_HEAD`, 0 visage partout = `BROLL`, autre ratio = `MIXED`, liste vide (aucune frame ou OpenCV indisponible) = `UNKNOWN`.

3. **Persistance** — une nouvelle méthode `VideoRepository.update_visual_metadata(video_id, thumbnail_key, content_shape)` écrit les deux colonnes `videos.thumbnail_key` et `videos.content_shape` en UPDATE unique.

4. **is_satisfied compound** — ajuster pour que la stage skip sur re-run uniquement quand TOUT (frame_texts ≥ 1, thumbnail_key non-null, content_shape non-null) est déjà en place. Une frame_texts sans thumbnail = la stage doit re-exécuter pour compléter la thumbnail.

**Décision clé** : fusionner OCR + thumbnail + face-count dans une SEULE stage (pas 3 stages séparées) car tous consomment les mêmes frames et la même passe disque. Cela évite de lire deux fois les mêmes JPGs. Le stage reste dans la plage des 20s de perf cible (OCR domine, face-count est ~10x plus rapide).

Purpose: livrer les deux requirements R048 + R049 en clôture de M008 avant la surface CLI/MCP.

Output: extension du stage existant + méthode repository + wiring container + 10+ tests unit + 2 integration.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M008/M008-ROADMAP.md
@.gsd/milestones/M008/M008-RESEARCH.md
@.gsd/milestones/M008/slices/S01/S01-P01-SUMMARY.md
@.gsd/milestones/M008/slices/S02/S02-P01-SUMMARY.md

@src/vidscope/pipeline/stages/visual_intelligence.py
@src/vidscope/adapters/sqlite/video_repository.py
@src/vidscope/ports/repositories.py
@src/vidscope/ports/storage.py
@src/vidscope/adapters/fs/local_media_storage.py
@src/vidscope/domain/entities.py
@src/vidscope/domain/values.py
@src/vidscope/infrastructure/container.py
</context>

<interfaces>
<!-- From S01-P01 (already delivered when this plan executes) -->

```python
# ContentShape enum (vidscope.domain.values)
class ContentShape(StrEnum):
    TALKING_HEAD = "talking_head"
    BROLL = "broll"
    MIXED = "mixed"
    UNKNOWN = "unknown"

# FaceCounter port (vidscope.ports.ocr_engine)
class FaceCounter(Protocol):
    def count_faces(self, image_path: str) -> int: ...

# HaarcascadeFaceCounter adapter (vidscope.adapters.vision)
class HaarcascadeFaceCounter:
    def __init__(self) -> None: ...
    def count_faces(self, image_path: str) -> int: ...
```

<!-- From S02-P01 (already delivered) -->

```python
class VisualIntelligenceStage:
    name: str = StageName.VISUAL_INTELLIGENCE.value
    def __init__(self, *, ocr_engine, link_extractor, media_storage, min_confidence=0.5) -> None: ...
    def is_satisfied(self, ctx, uow) -> bool: ...  # uses frame_texts.has_any_for_video
    def execute(self, ctx, uow) -> StageResult: ...
```

<!-- Existing VideoRepository.upsert_by_platform_id pattern -->

```python
class VideoRepository(Protocol):
    def upsert_by_platform_id(self, video: Video, creator: Creator | None = None) -> Video: ...
    def get(self, video_id: VideoId) -> Video | None: ...
```

<!-- MediaStorage.store pattern (from FramesStage usage) -->

```python
class MediaStorage(Protocol):
    def store(self, key: str, source_path: Path) -> str: ...  # returns the canonical key
    def resolve(self, key: str) -> Path: ...
```
</interfaces>

<tasks>

<task id="T01-classify-helper-and-repository-method" type="auto" tdd="true">
  <name>T01: Add classify_content_shape helper + VideoRepository.update_visual_metadata</name>

  <read_first>
    - `src/vidscope/ports/repositories.py` lines 67-141 — `VideoRepository` Protocol. Add the new method here, preserving docstring style and ordering.
    - `src/vidscope/adapters/sqlite/video_repository.py` — existing `VideoRepositorySQLite` implementation. The file has `upsert_by_platform_id`, `get`, `list_recent`, etc. Add `update_visual_metadata` as a new method mirroring the style.
    - `src/vidscope/adapters/sqlite/schema.py` (from S01-P01) — columns `videos.thumbnail_key` and `videos.content_shape` must already exist.
    - `src/vidscope/domain/values.py` — `ContentShape` enum (from S01-P01) is imported where needed.
    - `src/vidscope/domain/entities.py` — the `Video` dataclass doesn't have `thumbnail_key`/`content_shape` fields yet. We need to add them OR only update via the repository method. Decision: ADD both optional fields to the `Video` dataclass for consistency with M007's `description`/`music_track`/`music_artist` pattern (in-row columns, no side entity). This lets `ShowVideoUseCase` read them back without a separate fetch.
    - `tests/unit/adapters/sqlite/test_video_repository.py` — existing tests; mirror pattern.
  </read_first>

  <behavior>
    - Test 1 (Video fields): `Video(platform=..., platform_id=..., url="u")` has `thumbnail_key is None` and `content_shape is None` by default.
    - Test 2 (Video round-trip): instantiate with `thumbnail_key="videos/yt/abc/thumb.jpg"` and `content_shape="talking_head"`, read back intact. (Note: the domain field stores the string form; ContentShape enum conversion happens at the repository boundary.)
    - Test 3 (classify empty list): `classify_content_shape([])` returns `ContentShape.UNKNOWN`.
    - Test 4 (classify all zeros): `classify_content_shape([0, 0, 0])` returns `ContentShape.BROLL`.
    - Test 5 (classify ≥40%): `classify_content_shape([1, 0, 1, 0, 1])` returns `ContentShape.TALKING_HEAD` (3/5 = 60% ≥ 40%).
    - Test 6 (classify exactly 40%): `classify_content_shape([1, 0, 1, 0, 0])` returns `ContentShape.TALKING_HEAD` (2/5 = 40%).
    - Test 7 (classify <40%): `classify_content_shape([1, 0, 0, 0, 0])` returns `ContentShape.MIXED` (1/5 = 20%).
    - Test 8 (classify single frame with face): `classify_content_shape([1])` returns `ContentShape.TALKING_HEAD` (100%).
    - Test 9 (classify multi-face frames count as 1): `classify_content_shape([3, 0, 2, 0, 0])` — frames with ≥1 face = 2, ratio=0.4 → `TALKING_HEAD`.
    - Test 10 (repository update_visual_metadata): after update, `videos.get(vid_id).thumbnail_key == "videos/yt/abc/thumb.jpg"` and `video.content_shape == "talking_head"`.
    - Test 11 (repository update preserves other columns): title, description, music_track are untouched.
    - Test 12 (repository update on missing video): raises `StorageError` with "video N not found".
  </behavior>

  <action>
  **Step A — Add fields to `Video` entity in `src/vidscope/domain/entities.py`:**

  Extend the `Video` dataclass (around lines 50-90). After `music_artist: str | None = None`, add:

  ```python
      thumbnail_key: str | None = None
      content_shape: str | None = None
  ```

  Update the docstring section following the M007 metadata section (below "per R045" paragraph) to add:

  ```
  ``thumbnail_key`` is the MediaStorage key for the canonical
  thumbnail (copy of the middle frame, stored at
  ``videos/{platform}/{platform_id}/thumb.jpg``) per M008/R048.
  ``content_shape`` is the stringified ContentShape value (one of
  ``talking_head / broll / mixed / unknown``) per M008/R049. Both
  are populated by :class:`VisualIntelligenceStage` and are None
  until that stage completes successfully at least once. Stored as
  direct columns on the ``videos`` table — no side entity (same
  rationale as M007 D-01).
  ```

  **Step B — Create the helper `classify_content_shape` in `src/vidscope/pipeline/stages/visual_intelligence.py`** (will be used by execute() in T02). Add at the module level near the top of the file (after imports):

  ```python
  _TALKING_HEAD_THRESHOLD: float = 0.4


  def classify_content_shape(face_counts: list[int]) -> ContentShape:
      """Classify a video's visual form from a list of per-frame face counts.

      Rules (per M008 RESEARCH §2.4):

      - Empty list → :attr:`ContentShape.UNKNOWN` (no frames were
        processed, or OpenCV is not installed)
      - Every count is 0 → :attr:`ContentShape.BROLL`
      - ≥ 40% of frames have at least one face →
        :attr:`ContentShape.TALKING_HEAD`
      - Otherwise → :attr:`ContentShape.MIXED`

      A frame with 3 faces counts as a single "has-face" frame — we
      only measure presence, not intensity.
      """
      if not face_counts:
          return ContentShape.UNKNOWN
      frames_with_face = sum(1 for c in face_counts if c > 0)
      if frames_with_face == 0:
          return ContentShape.BROLL
      ratio = frames_with_face / len(face_counts)
      if ratio >= _TALKING_HEAD_THRESHOLD:
          return ContentShape.TALKING_HEAD
      return ContentShape.MIXED
  ```

  Add `ContentShape` to the imports at the top of the file (from `vidscope.domain`).

  **Step C — Add `update_visual_metadata` to `VideoRepository` Protocol in `src/vidscope/ports/repositories.py`:**

  Insert the method after `count` (around line 139):

  ```python
      def update_visual_metadata(
          self,
          video_id: VideoId,
          *,
          thumbnail_key: str | None,
          content_shape: str | None,
      ) -> None:
          """Update ``videos.thumbnail_key`` and ``videos.content_shape``
          for ``video_id`` in one UPDATE. Other columns are preserved
          (no wide row-rewrite).

          Raises
          ------
          StorageError
              When no video row matches ``video_id``.
          """
          ...
  ```

  **Step D — Implement in `src/vidscope/adapters/sqlite/video_repository.py`:**

  Add the method to `VideoRepositorySQLite`. Mirror the style of existing methods (try/except SQLAlchemyError → StorageError). Example:

  ```python
      def update_visual_metadata(
          self,
          video_id: VideoId,
          *,
          thumbnail_key: str | None,
          content_shape: str | None,
      ) -> None:
          try:
              result = self._conn.execute(
                  videos_table.update()
                  .where(videos_table.c.id == int(video_id))
                  .values(
                      thumbnail_key=thumbnail_key,
                      content_shape=content_shape,
                  )
              )
          except SQLAlchemyError as exc:
              raise StorageError(
                  f"update_visual_metadata failed for video {int(video_id)}: {exc}",
                  cause=exc,
              ) from exc
          if result.rowcount == 0:
              raise StorageError(
                  f"update_visual_metadata: video {int(video_id)} not found"
              )
  ```

  Also, ensure `_row_to_video` (or equivalent row-translation helper in the file) READS the new `thumbnail_key` and `content_shape` columns and passes them to the `Video(...)` constructor.

  **Step E — Tests:**

  1. `tests/unit/domain/test_entities.py` — add a test class `TestVideoVisualMetadata` with:
     - `test_defaults_none` — default `thumbnail_key is None` and `content_shape is None`.
     - `test_round_trip` — construction with both fields populated.
     - `test_is_frozen` — mutation raises FrozenInstanceError.

  2. `tests/unit/pipeline/stages/test_visual_intelligence.py` — add a top-level test module `TestClassifyContentShape` with the 7 classification tests from the behavior block (tests 3-9).

  3. `tests/unit/adapters/sqlite/test_video_repository.py` — add a test class `TestUpdateVisualMetadata` with the 3 repository tests (10-12).
  </action>

  <acceptance_criteria>
    - `grep -q 'thumbnail_key: str | None = None' src/vidscope/domain/entities.py` exit 0
    - `grep -q 'content_shape: str | None = None' src/vidscope/domain/entities.py` exit 0
    - `grep -q 'def classify_content_shape' src/vidscope/pipeline/stages/visual_intelligence.py` exit 0
    - `grep -q 'def update_visual_metadata' src/vidscope/ports/repositories.py` exit 0
    - `grep -q 'def update_visual_metadata' src/vidscope/adapters/sqlite/video_repository.py` exit 0
    - `uv run python -c "from vidscope.pipeline.stages.visual_intelligence import classify_content_shape; from vidscope.domain import ContentShape; assert classify_content_shape([]) == ContentShape.UNKNOWN; assert classify_content_shape([0,0]) == ContentShape.BROLL; assert classify_content_shape([1,0]) == ContentShape.TALKING_HEAD; assert classify_content_shape([1,0,0,0,0]) == ContentShape.MIXED; print('ok')"` prints `ok`
    - `uv run python -c "from vidscope.domain import Video, Platform, PlatformId; v = Video(platform=Platform.YOUTUBE, platform_id=PlatformId('x'), url='u', thumbnail_key='videos/yt/x/thumb.jpg', content_shape='talking_head'); print(v.thumbnail_key, v.content_shape)"` prints `videos/yt/x/thumb.jpg talking_head`
    - `uv run pytest tests/unit/domain/test_entities.py::TestVideoVisualMetadata -x -q` exit 0
    - `uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py::TestClassifyContentShape -x -q` exit 0
    - `uv run pytest tests/unit/adapters/sqlite/test_video_repository.py::TestUpdateVisualMetadata -x -q` exit 0
    - `uv run pytest -q` exit 0 (no regression)
    - `uv run mypy src` exit 0
    - `uv run lint-imports` exit 0
    <automated>uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py tests/unit/adapters/sqlite/test_video_repository.py -q</automated>
  </acceptance_criteria>
</task>

<task id="T02-extend-stage-with-thumbnail-and-face-count" type="auto" tdd="true">
  <name>T02: Extend VisualIntelligenceStage with thumbnail copy + face-count classification + compound is_satisfied</name>

  <read_first>
    - `src/vidscope/pipeline/stages/visual_intelligence.py` (from S02-P01) — current shape of execute(). We will ADD to it, not replace.
    - `src/vidscope/pipeline/stages/frames.py` lines 109-137 — the MediaStorage.store pattern used for persisting frames: build a key of shape `videos/{platform_segment}/{id_segment}/...`, call `media_storage.store(key, source_path)`. Copy this shape for thumbnails: `videos/{platform_segment}/{id_segment}/thumb.jpg`.
    - `src/vidscope/adapters/fs/local_media_storage.py` — to understand what `store(key, source_path)` does (it COPIES the file; resolve() returns the full path).
    - `src/vidscope/ports/storage.py` — MediaStorage.store signature.
    - `src/vidscope/ports/ocr_engine.py` (S01-P01) — `FaceCounter` Protocol to inject into the stage.
    - T01 above — `classify_content_shape` helper + `update_visual_metadata` method.
  </read_first>

  <behavior>
    - Test 1 (stage accepts face_counter via DI): constructor signature includes `face_counter: FaceCounter`.
    - Test 2 (thumbnail copy — odd-count frames): with 5 frames, thumbnail is copied from index 2 (middle).
    - Test 3 (thumbnail copy — even-count frames): with 4 frames, thumbnail is copied from index 2 (N//2).
    - Test 4 (thumbnail copy — single frame): with 1 frame, thumbnail is copied from that frame.
    - Test 5 (thumbnail key format): key equals `videos/{platform.value}/{platform_id}/thumb.jpg` with `.jpg` extension matching the source frame's suffix (fallback to `.jpg` if no suffix).
    - Test 6 (videos.thumbnail_key updated): after execute, `uow.videos.get(vid_id).thumbnail_key` equals the canonical key.
    - Test 7 (content_shape persisted): `uow.videos.get(vid_id).content_shape` equals the classified value.
    - Test 8 (FaceCounter called per frame): with 3 frames, `face_counter.count_faces` is called 3 times (with the resolved paths).
    - Test 9 (zero frames → no thumbnail, no update, returns SKIPPED): existing behavior from S02-P01 preserved, `update_visual_metadata` NOT called.
    - Test 10 (FaceCounter raises no effect): even if one call returns 0 (library missing), classification uses the remaining counts; if ALL return 0 we still land on BROLL (valid state).
    - Test 11 (compound is_satisfied — False when thumbnail_key is None even if frame_texts exist): simulates a half-completed run; stage must re-execute to finish.
    - Test 12 (compound is_satisfied — True when all three present): frame_texts exist AND thumbnail_key is populated AND content_shape is populated → skip.
    - Test 13 (is_satisfied — still False when frame_texts absent): mirrors S02-P01 behavior.
  </behavior>

  <action>
  **Step A — Update the stage in `src/vidscope/pipeline/stages/visual_intelligence.py`:**

  1. Add to the top imports:

  ```python
  from vidscope.domain import ContentShape  # already added in T01
  from vidscope.ports.ocr_engine import FaceCounter
  ```

  2. Extend `__init__` to accept `face_counter`:

  ```python
  def __init__(
      self,
      *,
      ocr_engine: OcrEngine,
      face_counter: FaceCounter,
      link_extractor: LinkExtractor,
      media_storage: MediaStorage,
      min_confidence: float = 0.5,
  ) -> None:
      self._ocr = ocr_engine
      self._face_counter = face_counter
      self._extractor = link_extractor
      self._media_storage = media_storage
      self._min_confidence = min_confidence
  ```

  3. Replace `is_satisfied` with a compound check:

  ```python
  def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
      """Return True when the stage's full output is in place:
      (a) at least one :class:`FrameText` row for the video,
      (b) ``videos.thumbnail_key`` is populated,
      (c) ``videos.content_shape`` is populated.

      Any missing piece forces re-execution. This guarantees a
      half-completed run (e.g. OCR succeeded but process died
      before face-count) eventually finishes on the next invocation.
      """
      if ctx.video_id is None:
          return False
      if not uow.frame_texts.has_any_for_video(ctx.video_id):
          return False
      video = uow.videos.get(ctx.video_id)
      if video is None:
          return False
      return (
          video.thumbnail_key is not None
          and video.content_shape is not None
      )
  ```

  4. Extend `execute`. Add a face-count loop that runs ALONGSIDE the OCR loop (same frame iteration — one pass over frames). At the END of execute (before returning StageResult), add thumbnail copy + update_visual_metadata. Full structure:

  ```python
  def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
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
      frames_with_text = 0
      face_counts: list[int] = []

      for frame in frames:
          if frame.id is None:
              _logger.warning(
                  "visual_intelligence: frame without id for video %s, skipping",
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
          path_str = str(frame_path)

          # Face count (R049) — one call per frame. Returns 0 on
          # any failure (missing cv2, corrupt image, etc.).
          face_counts.append(self._face_counter.count_faces(path_str))

          # OCR (R047) — same file, same pass.
          lines = self._ocr.extract_text(path_str, min_confidence=self._min_confidence)
          if not lines:
              continue
          frames_with_text += 1

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
          uow.frame_texts.add_many_for_frame(frame.id, ctx.video_id, frame_texts)
          total_text_blocks += len(frame_texts)

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

      persisted_links = uow.links.add_many_for_video(ctx.video_id, all_ocr_links)

      # --- R048: thumbnail copy from the middle frame -----------
      thumbnail_key: str | None = None
      if frames:
          middle_idx = len(frames) // 2
          middle_frame = frames[middle_idx]
          try:
              source_path = self._media_storage.resolve(middle_frame.image_key)
              source_path = (
                  source_path if isinstance(source_path, Path) else Path(str(source_path))
              )
              suffix = source_path.suffix or ".jpg"
              platform_segment = (
                  ctx.platform.value if ctx.platform else "unknown"
              )
              id_segment = str(ctx.platform_id or ctx.video_id)
              thumb_key = f"videos/{platform_segment}/{id_segment}/thumb{suffix}"
              thumbnail_key = self._media_storage.store(thumb_key, source_path)
          except Exception as exc:  # noqa: BLE001
              _logger.warning(
                  "visual_intelligence: thumbnail copy failed for video %s: %s",
                  ctx.video_id,
                  exc,
              )
              thumbnail_key = None

      # --- R049: content_shape classification --------------------
      shape = classify_content_shape(face_counts)

      # --- Persist both visual-metadata columns -----------------
      uow.videos.update_visual_metadata(
          ctx.video_id,
          thumbnail_key=thumbnail_key,
          content_shape=shape.value,
      )

      # --- Skipped-degradation signal (from S02-P01, preserved) --
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
              message=(
                  f"OCR produced no text for {len(frames)} frames; "
                  f"content_shape={shape.value}, thumbnail={'yes' if thumbnail_key else 'no'}"
              )
          )

      return StageResult(
          message=(
              f"extracted {total_text_blocks} text block(s), "
              f"{len(persisted_links)} link(s) across {len(frames)} frame(s); "
              f"content_shape={shape.value}, thumbnail={'yes' if thumbnail_key else 'no'}"
          )
      )
  ```

  **Step B — Extend tests in `tests/unit/pipeline/stages/test_visual_intelligence.py`:**

  1. Add a `_FakeFaceCounter` in the fakes section:

  ```python
  class _FakeFaceCounter:
      def __init__(self, results: dict[str, int] | None = None) -> None:
          self._results = results or {}
          self.calls: list[str] = []

      def count_faces(self, image_path: str) -> int:
          self.calls.append(image_path)
          return self._results.get(image_path, 0)
  ```

  2. Extend the `_FakeMediaStorage` to support `store`:

  ```python
  class _FakeMediaStorage:
      def __init__(self, base: Path) -> None:
          self._base = base
          self.stored: list[tuple[str, Path]] = []

      def resolve(self, key: str) -> Path:
          return self._base / key

      def store(self, key: str, source_path: Path) -> str:
          self.stored.append((key, source_path))
          return key
  ```

  3. Extend `_FakeVideoRepo` (create it if absent in the test module). It must expose `get(vid)` and `update_visual_metadata`:

  ```python
  @dataclass
  class _FakeVideoRepo:
      videos: dict[int, Video] = field(default_factory=dict)

      def add(self, video: Video) -> Video:
          new_id = VideoId(len(self.videos) + 1)
          stored = Video(
              platform=video.platform,
              platform_id=video.platform_id,
              url=video.url,
              id=new_id,
          )
          self.videos[int(new_id)] = stored
          return stored

      def get(self, video_id: VideoId) -> Video | None:
          return self.videos.get(int(video_id))

      def update_visual_metadata(
          self, video_id: VideoId, *, thumbnail_key: str | None, content_shape: str | None
      ) -> None:
          v = self.videos.get(int(video_id))
          if v is None:
              raise ValueError(f"video {video_id} not found")
          # Rebuild the frozen dataclass with the new columns
          self.videos[int(video_id)] = Video(
              platform=v.platform,
              platform_id=v.platform_id,
              url=v.url,
              id=v.id,
              thumbnail_key=thumbnail_key,
              content_shape=content_shape,
          )
  ```

  And extend `_FakeUoW` to include the `videos: _FakeVideoRepo` slot.

  4. Update the `_stage(...)` helper to accept and inject `face_counter`:

  ```python
  def _stage(
      engine: OcrEngine | None = None,
      face_counter: FaceCounter | None = None,
      tmp_path: Path | None = None,
  ) -> tuple[VisualIntelligenceStage, _FakeUoW]:
      engine = engine or _FakeOcrEngine()
      counter = face_counter or _FakeFaceCounter()
      media = _FakeMediaStorage(tmp_path or Path("/tmp"))
      stage = VisualIntelligenceStage(
          ocr_engine=engine,
          face_counter=counter,
          link_extractor=RegexLinkExtractor(),
          media_storage=media,
      )
      uow = _FakeUoW(
          frames=_FakeFrameRepo(),
          frame_texts=_FakeFrameTextRepo(),
          links=_FakeLinkRepo(),
          videos=_FakeVideoRepo(),
      )
      # Always seed the target video since the stage now calls
      # update_visual_metadata on it.
      uow.videos.videos[1] = Video(
          platform=Platform.YOUTUBE,
          platform_id=PlatformId("abc"),
          url="u",
          id=VideoId(1),
      )
      return stage, uow
  ```

  5. Add new test classes (each test from the behavior block):

  ```python
  class TestThumbnail:
      def test_middle_frame_copied_odd_count(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          for i, ts in enumerate([0, 1000, 2000, 3000, 4000]):
              uow.frames.frames.append(
                  Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=ts, id=i + 1)
              )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          stored_keys = [k for k, _ in stage._media_storage.stored]  # type: ignore[attr-defined]
          # 5 frames, middle_idx = 2 → f/2.jpg
          assert any(k.endswith("/thumb.jpg") for k in stored_keys)

      def test_middle_frame_copied_even_count(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          for i, ts in enumerate([0, 1000, 2000, 3000]):
              uow.frames.frames.append(
                  Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=ts, id=i + 1)
              )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          # N=4, middle_idx=2
          sources = [s for _, s in stage._media_storage.stored]  # type: ignore[attr-defined]
          assert any("2.jpg" in str(s) for s in sources)

      def test_single_frame_used_as_thumbnail(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          uow.frames.frames.append(
              Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=500, id=1)
          )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          sources = [s for _, s in stage._media_storage.stored]  # type: ignore[attr-defined]
          assert any("0.jpg" in str(s) for s in sources)

      def test_thumbnail_key_format(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          uow.frames.frames.append(
              Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=0, id=1)
          )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          stored_keys = [k for k, _ in stage._media_storage.stored]  # type: ignore[attr-defined]
          assert any(k == "videos/youtube/abc/thumb.jpg" for k in stored_keys)

      def test_videos_thumbnail_key_updated(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          uow.frames.frames.append(
              Frame(video_id=VideoId(1), image_key="f/0.jpg", timestamp_ms=0, id=1)
          )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          v = uow.videos.get(VideoId(1))
          assert v is not None
          assert v.thumbnail_key == "videos/youtube/abc/thumb.jpg"


  class TestContentShape:
      def test_no_frames_leaves_video_untouched(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          # No frames → skipped, content_shape not updated
          result = stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert result.skipped is True
          v = uow.videos.get(VideoId(1))
          assert v is not None
          assert v.content_shape is None

      def test_all_frames_have_faces_classified_talking_head(self, tmp_path: Path) -> None:
          counter = _FakeFaceCounter(
              {
                  str(tmp_path / f"f/{i}.jpg"): 1
                  for i in range(3)
              }
          )
          stage, uow = _stage(face_counter=counter, tmp_path=tmp_path)
          for i in range(3):
              uow.frames.frames.append(
                  Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
              )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          v = uow.videos.get(VideoId(1))
          assert v is not None
          assert v.content_shape == "talking_head"

      def test_no_faces_anywhere_classified_broll(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)  # default counter returns 0 for all
          for i in range(3):
              uow.frames.frames.append(
                  Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
              )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          v = uow.videos.get(VideoId(1))
          assert v is not None
          assert v.content_shape == "broll"

      def test_partial_face_presence_classified_mixed(self, tmp_path: Path) -> None:
          counter = _FakeFaceCounter({str(tmp_path / "f/0.jpg"): 1})
          stage, uow = _stage(face_counter=counter, tmp_path=tmp_path)
          for i in range(5):  # 1/5 = 20% < 40%
              uow.frames.frames.append(
                  Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
              )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          v = uow.videos.get(VideoId(1))
          assert v is not None
          assert v.content_shape == "mixed"

      def test_face_counter_called_per_frame(self, tmp_path: Path) -> None:
          counter = _FakeFaceCounter()
          stage, uow = _stage(face_counter=counter, tmp_path=tmp_path)
          for i in range(4):
              uow.frames.frames.append(
                  Frame(video_id=VideoId(1), image_key=f"f/{i}.jpg", timestamp_ms=i * 1000, id=i + 1)
              )
          stage.execute(_ctx(), uow)  # type: ignore[arg-type]
          assert len(counter.calls) == 4


  class TestCompoundIsSatisfied:
      def test_not_satisfied_when_frame_texts_missing(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          # video exists, no frame_texts
          assert stage.is_satisfied(_ctx(), uow) is False  # type: ignore[arg-type]

      def test_not_satisfied_when_thumbnail_key_is_none(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          uow.frame_texts.rows.append(
              FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=0.9, id=1)
          )
          # thumbnail_key still None on the video
          assert stage.is_satisfied(_ctx(), uow) is False  # type: ignore[arg-type]

      def test_satisfied_when_all_three_present(self, tmp_path: Path) -> None:
          stage, uow = _stage(tmp_path=tmp_path)
          uow.frame_texts.rows.append(
              FrameText(video_id=VideoId(1), frame_id=1, text="x", confidence=0.9, id=1)
          )
          uow.videos.update_visual_metadata(
              VideoId(1), thumbnail_key="videos/yt/abc/thumb.jpg", content_shape="mixed"
          )
          assert stage.is_satisfied(_ctx(), uow) is True  # type: ignore[arg-type]
  ```
  </action>

  <acceptance_criteria>
    - `grep -q 'face_counter: FaceCounter' src/vidscope/pipeline/stages/visual_intelligence.py` exit 0
    - `grep -q 'update_visual_metadata' src/vidscope/pipeline/stages/visual_intelligence.py` exit 0
    - `grep -q 'thumb.jpg' src/vidscope/pipeline/stages/visual_intelligence.py` exit 0 OR `grep -q 'thumb{suffix}' src/vidscope/pipeline/stages/visual_intelligence.py` exit 0
    - `uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py -x -q` exit 0 (≥ 20 tests including new classes)
    - `uv run pytest tests/unit/pipeline -q` exit 0 (no regression)
    - `uv run mypy src` exit 0
    <automated>uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py -q</automated>
  </acceptance_criteria>
</task>

<task id="T03-container-wiring-and-integration" type="auto">
  <name>T03: Wire HaarcascadeFaceCounter into container + extend integration test</name>

  <read_first>
    - `src/vidscope/infrastructure/container.py` — the existing wiring from S02-P01. We will ADD `face_counter = HaarcascadeFaceCounter()` and pass it to `VisualIntelligenceStage(...)`.
    - `src/vidscope/adapters/vision/__init__.py` — `HaarcascadeFaceCounter` export (from S01-P01).
    - `tests/integration/pipeline/test_visual_intelligence_stage.py` (from S02-P01) — extend with content_shape and thumbnail assertions.
  </read_first>

  <action>
  **Step A — Update `src/vidscope/infrastructure/container.py`:**

  1. Update the import from `vidscope.adapters.vision`:
  ```python
  from vidscope.adapters.vision import HaarcascadeFaceCounter, RapidOcrEngine
  ```

  2. In `build_container`, after `ocr_engine = RapidOcrEngine()` add:
  ```python
      face_counter = HaarcascadeFaceCounter()
  ```

  3. Update the `VisualIntelligenceStage(...)` constructor call to pass `face_counter=face_counter`:
  ```python
      visual_intelligence_stage = VisualIntelligenceStage(
          ocr_engine=ocr_engine,
          face_counter=face_counter,
          link_extractor=link_extractor,
          media_storage=media_storage,
      )
  ```

  **Step B — Extend `tests/integration/pipeline/test_visual_intelligence_stage.py`:**

  Add a new integration test class that exercises the thumbnail copy + content_shape update paths via the real `SqliteUnitOfWork` and `LocalMediaStorage`. Structure:

  ```python
  class _StubFaceCounter:
      def __init__(self, mapping: dict[str, int]) -> None:
          self._mapping = mapping

      def count_faces(self, image_path: str) -> int:
          return self._mapping.get(image_path, 0)


  @pytest.mark.integration
  class TestVisualIntelligenceIntegrationS03:
      def test_thumbnail_and_content_shape_persisted(self, tmp_path: Path) -> None:
          # Build engine + seed a video + 3 frames with REAL JPGs
          # on disk at tmp_path/frames/... so media_storage.store()
          # can copy them to the thumbnail key.
          engine = create_engine("sqlite:///:memory:")
          init_db(engine)

          # Write minimal "JPG" bytes (file existence + readability is what matters for the stage)
          frames_dir = tmp_path / "frames"
          frames_dir.mkdir(parents=True, exist_ok=True)
          jpg_bytes = b"\xff\xd8\xff\xe0fake-jpg"
          frame_paths = []
          for i in range(3):
              p = frames_dir / f"{i}.jpg"
              p.write_bytes(jpg_bytes)
              frame_paths.append(p)

          # Use a real LocalMediaStorage rooted at tmp_path.
          from vidscope.adapters.fs.local_media_storage import LocalMediaStorage  # noqa: PLC0415
          media = LocalMediaStorage(tmp_path)

          with SqliteUnitOfWork(engine) as uow:
              video = uow.videos.add(
                  Video(
                      platform=Platform.YOUTUBE,
                      platform_id=PlatformId("vid-42"),
                      url="https://youtube.com/shorts/vid-42",
                  )
              )
              assert video.id is not None
              vid_id = video.id
              uow.frames.add_many(
                  [
                      Frame(video_id=vid_id, image_key=f"frames/{i}.jpg", timestamp_ms=i * 1000)
                      for i in range(3)
                  ]
              )

          # Stub OcrEngine and FaceCounter — deterministic inputs
          stub_ocr = _StubOcr(
              {str(frame_paths[1]): [OcrLine(text="Visit example.com", confidence=0.9)]}
          )
          stub_face = _StubFaceCounter(
              {str(frame_paths[0]): 1, str(frame_paths[1]): 1, str(frame_paths[2]): 0}
          )
          stage = VisualIntelligenceStage(
              ocr_engine=stub_ocr,
              face_counter=stub_face,
              link_extractor=RegexLinkExtractor(),
              media_storage=media,
          )

          ctx = PipelineContext(source_url="x")
          ctx.video_id = vid_id
          ctx.platform = Platform.YOUTUBE
          ctx.platform_id = PlatformId("vid-42")

          with SqliteUnitOfWork(engine) as uow:
              result = stage.execute(ctx, uow)
          assert result.skipped is False

          # Assert persisted state
          with SqliteUnitOfWork(engine) as uow:
              v = uow.videos.get(vid_id)
              assert v is not None
              # 3 frames, 2/3 = 66.7% ≥ 40% → talking_head
              assert v.content_shape == "talking_head"
              assert v.thumbnail_key == "videos/youtube/vid-42/thumb.jpg"

          # Verify the thumbnail file actually exists on disk
          thumb_disk = tmp_path / "videos" / "youtube" / "vid-42" / "thumb.jpg"
          assert thumb_disk.exists()
          assert thumb_disk.read_bytes() == jpg_bytes

      def test_is_satisfied_after_full_execution(self, tmp_path: Path) -> None:
          # Same setup as above, but call is_satisfied after execute
          # and assert True.
          ...
  ```
  </action>

  <acceptance_criteria>
    - `grep -q 'HaarcascadeFaceCounter' src/vidscope/infrastructure/container.py` exit 0
    - `grep -q 'face_counter=face_counter' src/vidscope/infrastructure/container.py` exit 0
    - `uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); print('ok')"` prints `ok`
    - `uv run pytest tests/integration/pipeline -m integration -q` exit 0 (all integration tests pass including the new S03 class)
    - `uv run pytest -q` exit 0 (no regression)
    - `uv run lint-imports` exit 0
    - `uv run mypy src` exit 0
    <automated>uv run pytest tests/integration/pipeline -m integration -q</automated>
  </acceptance_criteria>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Middle-frame JPG → MediaStorage.store (thumbnail copy) | A frame file on disk is copied to a permanent storage key; path-traversal in the destination key would be a bug |
| FaceCounter → integer count → classify_content_shape | A malicious face counter (rogue implementation) could return `-1` or a very large int; the classifier must not be fooled |
| update_visual_metadata UPDATE statement | Writes to videos columns; must use parameterized binding (not string interpolation) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-M008-S03-01 | **Tampering (T)** | Thumbnail destination key built via f-string `f"videos/{platform}/{platform_id}/thumb.jpg"` — path traversal via `platform_id` containing `..` | mitigate | `ctx.platform` is a `Platform` enum (StrEnum with 3 closed values: instagram/tiktok/youtube) — no injection surface. `ctx.platform_id` is `PlatformId` (NewType str) populated from yt-dlp's canonical id field, which is alphanumeric by convention. Add a defensive check in T02: if `platform_id` contains `/` or `..`, log and skip the thumbnail copy. Documented in the stage's `execute` method. |
| T-M008-S03-02 | **Tampering (T)** | Malicious or buggy FaceCounter returning negative / giant int breaks `classify_content_shape` | mitigate | `classify_content_shape` uses `sum(1 for c in face_counts if c > 0)` — only tests `> 0`, so negative values count as zero. Giant positive values also count as one frame-with-face. The ratio calc `frames_with_face / len(face_counts)` is bounded [0, 1] by definition. No arithmetic overflow risk (Python ints are unbounded). Accept. |
| T-M008-S03-03 | **Denial of Service (D)** | 30 face_counter.count_faces calls on 30 large JPGs could accumulate a timing DoS | accept | Haarcascade is ~10x faster than OCR per frame (~10-50ms). 30 frames × 50ms = 1.5s worst case. Well within the <20s perf target. Documented in M008-RESEARCH §2.5. |
| T-M008-S03-04 | **Tampering (T)** | `update_visual_metadata` SQL UPDATE — injection risk | mitigate | Implementation uses SQLAlchemy Core `videos_table.update().values(thumbnail_key=..., content_shape=...)` — parameter binding is handled by the driver. No string concatenation. No raw SQL. Standard project pattern. |
| T-M008-S03-05 | **Information Disclosure (I)** | Thumbnail file stored at a deterministic path enables information correlation if the data/ directory is leaked | accept | R032: vidscope is a single-user local tool. Data/ is gitignored. Thumbnail paths follow the same shape as frame paths — same risk profile, already accepted. |
| T-M008-S03-06 | **Tampering (T)** | `is_satisfied` compound check depends on `videos.thumbnail_key is not None` — setting thumbnail_key to empty string "" (truthy Python value) would silently count as populated | mitigate | `update_visual_metadata` stores `None` explicitly when the copy fails (see T02 action). Empty string would only arise from a caller bug; defensive check in execute: if `thumbnail_key == ""`, treat as None before persisting. Acceptance criterion: test_thumbnail_key_is_none_when_copy_fails. |

</threat_model>

<verification>
```bash
# Unit tests
uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py -x -q
uv run pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q
uv run pytest tests/unit/domain/test_entities.py -x -q

# Integration
uv run pytest tests/integration/pipeline -m integration -q

# Full suite
uv run pytest -q

# Quality gates
uv run ruff check src tests
uv run mypy src
uv run lint-imports
```
</verification>

<success_criteria>
- VisualIntelligenceStage accepts `face_counter: FaceCounter` via DI.
- Stage copies the middle frame (index N//2) to `videos/{platform}/{platform_id}/thumb.jpg` via `MediaStorage.store`.
- Stage classifies content_shape via `classify_content_shape(face_counts)` heuristic (40% threshold).
- Stage persists both visual columns via `VideoRepository.update_visual_metadata` in a single UPDATE.
- `is_satisfied` is compound — requires frame_texts + thumbnail_key + content_shape all populated.
- `Video` dataclass carries `thumbnail_key` and `content_shape` fields (both `str | None = None` defaults).
- Container wires `HaarcascadeFaceCounter` and injects it into the stage.
- Integration test verifies thumbnail file exists on disk at the canonical path + videos row has the two columns populated.
- All 10 import-linter contracts green.
- Zero regression on existing tests.
</success_criteria>

<output>
After completion, create `.gsd/milestones/M008/slices/S03/S03-P01-SUMMARY.md` following the standard summary template.
</output>
