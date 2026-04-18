---
slice: S01
plan: P01
phase: M008/S01
plan_id: S01-P01
wave: 1
depends_on: []
requirements: [R047, R048, R049]
files_modified:
  - src/vidscope/domain/values.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/ocr_engine.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/adapters/vision/__init__.py
  - src/vidscope/adapters/vision/rapidocr_engine.py
  - src/vidscope/adapters/vision/haarcascade_face_counter.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/frame_text_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/infrastructure/startup.py
  - src/vidscope/cli/commands/doctor.py
  - pyproject.toml
  - .importlinter
  - tests/fixtures/vision/__init__.py
  - tests/fixtures/vision/generate_fixtures.py
  - tests/unit/domain/test_entities.py
  - tests/unit/domain/test_values.py
  - tests/unit/adapters/vision/__init__.py
  - tests/unit/adapters/vision/test_rapidocr_engine.py
  - tests/unit/adapters/vision/test_face_counter.py
  - tests/unit/adapters/sqlite/test_frame_text_repository.py
  - tests/unit/adapters/sqlite/test_schema.py
  - tests/unit/infrastructure/test_startup.py
autonomous: true
must_haves:
  truths:
    - "FrameText frozen dataclass carries video_id, frame_id, text, confidence, optional bbox, optional id and created_at"
    - "ContentShape StrEnum exposes exactly four values: talking_head, broll, mixed, unknown"
    - "StageName enum exposes VISUAL_INTELLIGENCE = 'visual_intelligence' between ANALYZE and METADATA_EXTRACT"
    - "OcrEngine Protocol exists with extract_text(image_path, *, min_confidence=0.5) -> list[OcrLine]"
    - "FrameTextRepository Protocol exists with add_many_for_frame, list_for_video, has_any_for_video"
    - "FaceCounter Protocol exists with count_faces(image_path) -> int"
    - "RapidOcrEngine adapter implements OcrEngine with lazy model load and graceful degradation when rapidocr_onnxruntime is not installed"
    - "HaarcascadeFaceCounter adapter implements FaceCounter with graceful degradation when opencv is not installed (returns 0)"
    - "frame_texts SQLite table exists with FK cascade on frames.id and videos.id"
    - "frame_texts_fts FTS5 virtual table exists with tokenize = 'unicode61 remove_diacritics 2'"
    - "videos table carries thumbnail_key TEXT and content_shape VARCHAR(32) columns, idempotent on upgraded DBs"
    - "SqliteUnitOfWork exposes uow.frame_texts attribute typed as FrameTextRepository"
    - "vidscope doctor prints a vision row reporting rapidocr-onnxruntime availability"
    - "vision-adapter-is-self-contained import-linter contract is declared and green"
    - "pyproject.toml declares [project.optional-dependencies] vision = rapidocr-onnxruntime + opencv-python-headless"
  artifacts:
    - path: "src/vidscope/ports/ocr_engine.py"
      provides: "OcrEngine Protocol + OcrLine dataclass + FaceCounter Protocol"
      contains: "class OcrEngine(Protocol)"
    - path: "src/vidscope/adapters/vision/rapidocr_engine.py"
      provides: "RapidOcrEngine implementing OcrEngine with lazy model load"
      contains: "class RapidOcrEngine"
    - path: "src/vidscope/adapters/vision/haarcascade_face_counter.py"
      provides: "HaarcascadeFaceCounter implementing FaceCounter"
      contains: "class HaarcascadeFaceCounter"
    - path: "src/vidscope/adapters/sqlite/frame_text_repository.py"
      provides: "FrameTextRepositorySQLite — CRUD + FTS5 sync"
      contains: "class FrameTextRepositorySQLite"
    - path: "src/vidscope/adapters/sqlite/schema.py"
      provides: "frame_texts Table + _ensure_* upgrade helpers + frame_texts_fts FTS5 DDL + videos.thumbnail_key + videos.content_shape"
      contains: "frame_texts = Table"
    - path: ".importlinter"
      provides: "vision-adapter-is-self-contained contract"
      contains: "vision-adapter-is-self-contained"
  key_links:
    - from: "src/vidscope/adapters/sqlite/unit_of_work.py"
      to: "vidscope.adapters.sqlite.frame_text_repository.FrameTextRepositorySQLite"
      via: "import + assignment in __enter__"
      pattern: "FrameTextRepositorySQLite"
    - from: "src/vidscope/adapters/vision/rapidocr_engine.py"
      to: "rapidocr_onnxruntime.RapidOCR"
      via: "lazy import inside _get_engine() with ImportError guard"
      pattern: "from rapidocr_onnxruntime import RapidOCR"
    - from: "src/vidscope/adapters/sqlite/frame_text_repository.py"
      to: "frame_texts_fts virtual table"
      via: "INSERT INTO frame_texts_fts (frame_text_id, video_id, text) after parent INSERT"
      pattern: "frame_texts_fts"
    - from: "src/vidscope/infrastructure/startup.py"
      to: "rapidocr_onnxruntime module presence"
      via: "check_vision() importlib.util.find_spec"
      pattern: "check_vision"
---

<objective>
Poser toutes les fondations pures + adapters auto-contenus pour M008 — sans pipeline, sans use case, sans CLI facet. Ce plan livre : (1) le port `OcrEngine` + `FaceCounter` dans `ports/ocr_engine.py` ; (2) l'entité `FrameText` (frozen dataclass slots) + l'enum `ContentShape` + `StageName.VISUAL_INTELLIGENCE` ; (3) le port `FrameTextRepository` + son exposition dans `UnitOfWork` ; (4) le sous-module `vidscope.adapters.vision` avec `RapidOcrEngine` (lazy model load + dégradation gracieuse) et `HaarcascadeFaceCounter` ; (5) le schéma SQLite — nouvelle table `frame_texts`, FTS5 `frame_texts_fts`, colonnes `videos.thumbnail_key` + `videos.content_shape`, helpers `_ensure_*` idempotents ; (6) `FrameTextRepositorySQLite` avec synchronisation FTS5 manuelle (pattern `SearchIndexSQLite`) ; (7) le contrat `.importlinter` `vision-adapter-is-self-contained` + ajout de `vidscope.adapters.vision` aux `forbidden_modules` des contrats existants ; (8) doctor check `vision` qui reporte l'état d'installation ; (9) fixtures JPG synthétiques pour les tests unitaires (Pillow). Tous les 9+ contrats import-linter restent verts. La couche domaine reste pure, le nouvel adapter `vision` reste isolé.

Purpose: établir tous les interfaces et adapters nécessaires à S02 (VisualIntelligenceStage) et S03 (content_shape + thumbnail). Aucun pipeline ne sera wiré ici — le stage S02 dépendra exclusivement des ports et des adapters livrés par ce plan.

Output: 3 nouveaux sous-modules (`adapters/vision/`, `ports/ocr_engine.py`, `frame_text_repository.py`) + schema étendu + doctor check + fixtures + 40+ tests unitaires verts.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/STATE.md
@.gsd/REQUIREMENTS.md
@.gsd/milestones/M008/M008-ROADMAP.md
@.gsd/milestones/M008/M008-RESEARCH.md
@.gsd/milestones/M008/M008-VALIDATION.md

<!-- Existing patterns to mirror -->
@src/vidscope/domain/entities.py
@src/vidscope/domain/values.py
@src/vidscope/ports/link_extractor.py
@src/vidscope/ports/repositories.py
@src/vidscope/ports/unit_of_work.py
@src/vidscope/adapters/sqlite/schema.py
@src/vidscope/adapters/sqlite/hashtag_repository.py
@src/vidscope/adapters/sqlite/link_repository.py
@src/vidscope/adapters/sqlite/unit_of_work.py
@src/vidscope/infrastructure/startup.py
@src/vidscope/cli/commands/doctor.py
@.importlinter
@pyproject.toml
</context>

<interfaces>
<!-- Key types and patterns the executor MUST replicate exactly -->

From src/vidscope/ports/link_extractor.py (LinkExtractor pattern to mirror for OcrEngine):
```python
@runtime_checkable
class LinkExtractor(Protocol):
    def extract(self, text: str, *, source: str) -> list[RawLink]:
        ...
```

From src/vidscope/domain/entities.py (Hashtag pattern to mirror for FrameText):
```python
@dataclass(frozen=True, slots=True)
class Hashtag:
    video_id: VideoId
    tag: str
    id: int | None = None
    created_at: datetime | None = None
```

From src/vidscope/domain/values.py (StrEnum pattern for ContentShape):
```python
class Language(StrEnum):
    FRENCH = "fr"
    ENGLISH = "en"
    UNKNOWN = "unknown"
```

From src/vidscope/adapters/sqlite/schema.py (table + _ensure_* pattern):
```python
links = Table(
    "links",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    ...
)

def _ensure_videos_metadata_columns(conn: Connection) -> None:
    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
    if "description" not in cols:
        conn.execute(text("ALTER TABLE videos ADD COLUMN description TEXT"))
```

From src/vidscope/adapters/sqlite/link_repository.py (repository pattern to mirror for FrameTextRepositorySQLite):
```python
class LinkRepositorySQLite:
    def __init__(self, connection: Connection) -> None:
        self._conn = connection
    def add_many_for_video(self, video_id: VideoId, links: list[Link]) -> list[Link]:
        ...
```

From .importlinter (contract pattern to replicate for vision):
```
[importlinter:contract:text-adapter-is-self-contained]
name = text adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.text
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    ...
```
</interfaces>

<tasks>

<task id="T01-domain-extensions" type="auto" tdd="true">
  <name>T01: Add FrameText entity + ContentShape enum + StageName.VISUAL_INTELLIGENCE + __init__ re-exports</name>

  <read_first>
    - `src/vidscope/domain/entities.py` (entire file, 348 lines) — mirror the `Hashtag` dataclass pattern (lines 266-287) and the `Link` pattern (lines 316-347). Confirm `datetime` is imported on line 22.
    - `src/vidscope/domain/values.py` (entire file, 116 lines) — the `StageName` StrEnum is on lines 84-96. The `Language` StrEnum on lines 71-81 is the exact pattern for `ContentShape`.
    - `src/vidscope/domain/__init__.py` (entire file, 88 lines) — `__all__` is grouped by concern (entities / errors / values / helpers) with `noqa: RUF022`.
    - `src/vidscope/pipeline/runner.py` lines 312-325 — `_resolve_stage_phase()` raises `StageCrashError` if the stage's `name` is not in the `StageName` enum. This is why the new member MUST exist before S02 wires the stage.
    - `tests/unit/domain/test_entities.py` — the existing tests for `TestHashtag`, `TestMention`, `TestLink` — mirror the same class + method structure for `TestFrameText`.
    - `tests/unit/domain/test_values.py` — the existing tests for `Language`, `Platform`, `StageName` — mirror for `ContentShape` and add a test for the new `StageName.VISUAL_INTELLIGENCE` member.
  </read_first>

  <behavior>
    - Test 1 (FrameText): `FrameText(video_id=VideoId(1), frame_id=5, text="Link in bio", confidence=0.92)` constructs with defaults (`bbox=None`, `id=None`, `created_at=None`).
    - Test 2 (FrameText): all kwargs round-trip.
    - Test 3 (FrameText): frozen — `ft.text = "x"` raises `FrozenInstanceError`.
    - Test 4 (FrameText): uses slots — `hasattr(ft, "__dict__") is False`.
    - Test 5 (FrameText): equality by fields — two FrameText with same fields are ==.
    - Test 6 (ContentShape): exhaustive — `{s.value for s in ContentShape} == {"talking_head", "broll", "mixed", "unknown"}`.
    - Test 7 (ContentShape): string values are lowercase snake_case, never hyphenated, never uppercase.
    - Test 8 (StageName): `StageName.VISUAL_INTELLIGENCE.value == "visual_intelligence"`, and the ordered list is `[ingest, transcribe, frames, analyze, visual_intelligence, metadata_extract, index]` (7 members).
  </behavior>

  <action>
  **Step A — `src/vidscope/domain/values.py`:**

  1. Add `ContentShape` StrEnum AFTER the `Language` StrEnum (insert a new block around line 82, before `class StageName`):

  ```python
  class ContentShape(StrEnum):
      """High-level classification of a video's visual form.

      Computed by M008 :class:`VisualIntelligenceStage` from a
      face-count heuristic over extracted frames. Persisted as a
      string column on the ``videos`` table (per M008 RESEARCH §5.1
      — direct column, no side entity).

      - ``TALKING_HEAD`` — ≥ 40% of frames show at least one face
      - ``BROLL`` — zero frames show a face
      - ``MIXED`` — between the two
      - ``UNKNOWN`` — no frames were processed or OpenCV unavailable
      """

      TALKING_HEAD = "talking_head"
      BROLL = "broll"
      MIXED = "mixed"
      UNKNOWN = "unknown"
  ```

  2. In the `StageName` StrEnum, add `VISUAL_INTELLIGENCE = "visual_intelligence"` BETWEEN `ANALYZE` and `METADATA_EXTRACT`. The final enum MUST be exactly (7 members, in this order):

  ```python
  class StageName(StrEnum):
      """Discrete stage of the ingestion pipeline.

      Each stage writes exactly one :class:`PipelineRun` row. The order of
      this enum declaration is the canonical execution order.
      """

      INGEST = "ingest"
      TRANSCRIBE = "transcribe"
      FRAMES = "frames"
      ANALYZE = "analyze"
      VISUAL_INTELLIGENCE = "visual_intelligence"
      METADATA_EXTRACT = "metadata_extract"
      INDEX = "index"
  ```

  3. Update `__all__` (lines 26-35) to include `"ContentShape"` in alphabetical order (between `"CreatorId"` and `"Language"`).

  **Step B — `src/vidscope/domain/entities.py`:**

  1. Add `FrameText` dataclass at the end of the file (after `Link`, around line 348). Use the exact same frozen+slots pattern as `Hashtag` and `Link`:

  ```python
  @dataclass(frozen=True, slots=True)
  class FrameText:
      """A block of OCR-extracted text for a single frame (M008/R047).

      Stored in the ``frame_texts`` side table keyed by ``(frame_id,
      id)`` with FK cascade on both ``frames.id`` and ``videos.id``.
      ``video_id`` is denormalised on the row (also present via
      ``frames.video_id``) so the FTS5 ``frame_texts_fts`` virtual
      table can filter by ``video_id`` without a JOIN — same pattern
      as the existing ``search_index`` table.

      ``confidence`` is the OCR engine's score in ``[0.0, 1.0]``;
      rows below the engine's min_confidence threshold (default 0.5)
      are discarded before insertion — the dataclass itself does not
      validate the range (responsibility of the adapter — pattern
      mirrors :class:`Hashtag` which does not canonicalise).

      ``bbox`` is an optional JSON-serialised string of the 4 corner
      points ``[[x1,y1], ..., [x4,y4]]`` from RapidOCR. Stored for
      potential future visualisation; NOT exposed in CLI/MCP v1. The
      dataclass holds it opaquely as ``str | None``.

      ``id`` is ``None`` until the repository persists the row; the
      repository returns a new instance with ``id`` populated.
      """

      video_id: VideoId
      frame_id: int
      text: str
      confidence: float
      bbox: str | None = None
      id: int | None = None
      created_at: datetime | None = None
  ```

  2. Update `__all__` (lines 35-48) to include `"FrameText"` in alphabetical order (between `"Frame"` and `"Hashtag"`).

  **Step C — `src/vidscope/domain/__init__.py`:**

  1. Add `FrameText` to the imports from `.entities` (alphabetical) and to the `# entities` section of `__all__`.
  2. Add `ContentShape` to the imports from `.values` and to the `# values` section of `__all__`.

  **Step D — `tests/unit/domain/test_entities.py`:**

  Add a new `TestFrameText` class at the end of the file. Mirror the existing `TestHashtag` / `TestLink` structure. Include tests for: construction with defaults, full round-trip including bbox, frozen (FrozenInstanceError on mutation), slots (no __dict__), equality by fields, confidence field accepts floats outside [0, 1] (dataclass doesn't validate — adapter's job).

  Ensure `FrameText` is imported at the top of the file alongside `Hashtag`, `Link`, etc.

  **Step E — `tests/unit/domain/test_values.py`:**

  1. Add a `TestContentShape` class with two tests:
     - `test_content_shape_exhaustive`: assert `{s.value for s in ContentShape} == {"talking_head", "broll", "mixed", "unknown"}`.
     - `test_content_shape_members_are_snake_case`: assert every value matches `^[a-z_]+$`.

  2. In the existing `TestStageName` class, add `test_stage_name_has_visual_intelligence`: assert `StageName.VISUAL_INTELLIGENCE.value == "visual_intelligence"` AND assert `[s.value for s in StageName] == ["ingest", "transcribe", "frames", "analyze", "visual_intelligence", "metadata_extract", "index"]` (exact 7-element list in this order).

  Ensure `ContentShape` is imported at the top of the file.
  </action>

  <acceptance_criteria>
    - `grep -q 'class ContentShape(StrEnum):' src/vidscope/domain/values.py` exit 0
    - `grep -q 'VISUAL_INTELLIGENCE = "visual_intelligence"' src/vidscope/domain/values.py` exit 0
    - `grep -q 'class FrameText:' src/vidscope/domain/entities.py` exit 0
    - `grep -q '"FrameText"' src/vidscope/domain/entities.py` exit 0
    - `grep -q '"FrameText"' src/vidscope/domain/__init__.py` exit 0
    - `grep -q '"ContentShape"' src/vidscope/domain/__init__.py` exit 0
    - `uv run python -c "from vidscope.domain import StageName; assert [s.value for s in StageName] == ['ingest','transcribe','frames','analyze','visual_intelligence','metadata_extract','index']"` exit 0
    - `uv run python -c "from vidscope.domain import ContentShape; assert {s.value for s in ContentShape} == {'talking_head','broll','mixed','unknown'}"` exit 0
    - `uv run python -c "from vidscope.domain import FrameText, VideoId; ft = FrameText(video_id=VideoId(1), frame_id=5, text='hello', confidence=0.9); print(ft.text, ft.bbox)"` prints `hello None`
    - `uv run pytest tests/unit/domain/test_entities.py::TestFrameText -x -q` exit 0
    - `uv run pytest tests/unit/domain/test_values.py::TestContentShape -x -q` exit 0
    - `uv run pytest tests/unit/domain -q` exit 0 (no regression)
    - `uv run mypy src` exit 0
    - `uv run lint-imports` exit 0 (domain-is-pure still green)
    <automated>uv run pytest tests/unit/domain -q</automated>
  </acceptance_criteria>
</task>

<task id="T02-ports-ocr-engine-and-repository" type="auto" tdd="true">
  <name>T02: Create OcrEngine + FaceCounter + FrameTextRepository ports + wire in UnitOfWork</name>

  <read_first>
    - `src/vidscope/ports/link_extractor.py` (entire file, 55 lines) — the exact Protocol + TypedDict pattern to replicate for `OcrEngine`.
    - `src/vidscope/ports/repositories.py` lines 472-522 — `LinkRepository` Protocol with `add_many_for_video`, `list_for_video`, `has_any_for_video` — mirror for `FrameTextRepository`.
    - `src/vidscope/ports/unit_of_work.py` (entire file, 99 lines) — `UnitOfWork` Protocol exposes each repository as a class attribute.
    - `src/vidscope/ports/__init__.py` (entire file, 85 lines) — __all__ list to extend.
    - `.importlinter` lines 120-135 — `ports-are-pure` contract forbids stdlib-external imports in `vidscope.ports`. No third-party imports in new port files.
    - `src/vidscope/domain/__init__.py` — confirm `FrameText` is re-exported (from T01).
  </read_first>

  <behavior>
    - Test 1: `OcrEngine` Protocol is runtime_checkable; a dummy class with `extract_text(self, image_path, *, min_confidence=0.5) -> list[OcrLine]` is an instance.
    - Test 2: `FaceCounter` Protocol is runtime_checkable; a dummy class with `count_faces(self, image_path) -> int` is an instance.
    - Test 3: `FrameTextRepository` Protocol is runtime_checkable and exposes `add_many_for_frame`, `list_for_video`, `has_any_for_video`.
    - Test 4: `OcrLine` is a frozen dataclass with `text: str`, `confidence: float`, `bbox: str | None = None`.
  </behavior>

  <action>
  **Step A — Create `src/vidscope/ports/ocr_engine.py`:**

  ```python
  """OCR + face-count ports (M008/R047, R049).

  Both Protocols are pure — implementations must not raise on I/O
  failures during normal operation (missing file, corrupt JPEG),
  they return an empty list / zero instead. This keeps the
  :class:`VisualIntelligenceStage` simple: no per-frame exception
  handling, one pass over frames.

  :class:`OcrEngine` implementations may raise :class:`OCRUnavailableError`
  from a constructor or the first call ONLY when the underlying
  library is not installed. The stage catches that error and
  returns a SKIPPED :class:`StageResult`. See M008 RESEARCH §1.4.
  """

  from __future__ import annotations

  from dataclasses import dataclass
  from typing import Protocol, runtime_checkable

  __all__ = ["FaceCounter", "OcrEngine", "OcrLine"]


  @dataclass(frozen=True, slots=True)
  class OcrLine:
      """One line of OCR-extracted text.

      ``text`` is the raw string as reported by the engine — no
      canonicalisation. ``confidence`` is the engine's score in
      ``[0.0, 1.0]``; callers filter on a threshold before
      persisting. ``bbox`` is an opaque JSON string of the 4
      corner points (format: ``'[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]'``)
      or ``None`` when the engine does not expose bounding boxes.
      """

      text: str
      confidence: float
      bbox: str | None = None


  @runtime_checkable
  class OcrEngine(Protocol):
      """OCR engine port. Default implementation:
      :class:`~vidscope.adapters.vision.RapidOcrEngine`.
      """

      def extract_text(
          self, image_path: str, *, min_confidence: float = 0.5
      ) -> list[OcrLine]:
          """Return OCR lines above ``min_confidence`` found in
          the image at ``image_path``.

          Returns an empty list when no text is detected, when the
          file is missing or corrupt, or when the underlying OCR
          library is not installed. Never raises in normal
          operation — the stage interprets an empty list as "no
          on-screen text" and moves on.
          """
          ...


  @runtime_checkable
  class FaceCounter(Protocol):
      """Face-count port. Default implementation:
      :class:`~vidscope.adapters.vision.HaarcascadeFaceCounter`.
      """

      def count_faces(self, image_path: str) -> int:
          """Return the number of faces detected in the image at
          ``image_path``.

          Returns ``0`` when no face is detected, when the file is
          missing or corrupt, or when OpenCV is not installed. Never
          raises in normal operation.
          """
          ...
  ```

  **Step B — Extend `src/vidscope/ports/repositories.py`:**

  1. Add `FrameText` to the `from vidscope.domain import (...)` block (alphabetical, between `Frame` and `Hashtag`).
  2. Add `"FrameTextRepository"` to `__all__` (alphabetical, between `"FrameRepository"` and `"HashtagRepository"`).
  3. At the END of the file, add:

  ```python
  @runtime_checkable
  class FrameTextRepository(Protocol):
      """Persistence for :class:`~vidscope.domain.entities.FrameText`.

      Side table keyed by ``(frame_id, id)`` with FK cascade on
      ``frames.id`` AND ``videos.id`` (denormalised). The repository
      owns the FTS5 sync: every insert into ``frame_texts`` also
      inserts into ``frame_texts_fts``, every delete cascades
      through both. Pattern mirrors :class:`SearchIndex`.
      """

      def add_many_for_frame(
          self,
          frame_id: int,
          video_id: VideoId,
          texts: list[FrameText],
      ) -> list[FrameText]:
          """Insert every text row for ``frame_id`` atomically.

          Empty ``texts`` is a no-op. Returns the persisted entities
          with ``id`` populated. The adapter MUST also sync each
          inserted row into ``frame_texts_fts``.
          """
          ...

      def list_for_video(self, video_id: VideoId) -> list[FrameText]:
          """Return every frame text for ``video_id`` ordered by
          ``frame_id`` asc then ``id`` asc. Empty list on miss —
          never raises.
          """
          ...

      def has_any_for_video(self, video_id: VideoId) -> bool:
          """Return ``True`` when at least one frame text exists for
          ``video_id``. Used by
          :meth:`VisualIntelligenceStage.is_satisfied`.
          """
          ...

      def find_video_ids_by_text(
          self, query: str, *, limit: int = 50
      ) -> list[VideoId]:
          """Return up to ``limit`` distinct video ids whose
          on-screen text matches ``query`` via FTS5 MATCH on
          ``frame_texts_fts``.

          ``query`` is passed through to FTS5 as-is (callers MUST
          ensure it is a valid FTS5 query string — a bare word is
          always valid). Empty list on miss — never raises.
          """
          ...
  ```

  **Step C — Update `src/vidscope/ports/unit_of_work.py`:**

  1. Add `FrameTextRepository` to the import block (alphabetical).
  2. Add `frame_texts: FrameTextRepository` attribute on `UnitOfWork` Protocol (place between `frames` and `analyses` — alphabetical is not required, but grouping with `frames` is semantically clean).

  **Step D — Update `src/vidscope/ports/__init__.py`:**

  1. Add `from vidscope.ports.ocr_engine import FaceCounter, OcrEngine, OcrLine` to the imports.
  2. Add `FrameTextRepository` to the import from `vidscope.ports.repositories`.
  3. Add `"FaceCounter"`, `"FrameTextRepository"`, `"OcrEngine"`, `"OcrLine"` to `__all__` in alphabetical order.

  **Step E — Tests in `tests/unit/ports/test_ocr_engine.py` (create new file) + extend `tests/unit/ports/test_repositories.py` if it exists, else inline in the new file:**

  Create `tests/unit/ports/` directory if needed (include `__init__.py`). Write `tests/unit/ports/test_ocr_engine.py`:

  ```python
  """Unit tests for the OCR + face-count ports."""

  from __future__ import annotations

  from dataclasses import FrozenInstanceError

  import pytest

  from vidscope.ports import FaceCounter, OcrEngine, OcrLine


  class TestOcrLine:
      def test_defaults(self) -> None:
          line = OcrLine(text="hello", confidence=0.9)
          assert line.text == "hello"
          assert line.confidence == 0.9
          assert line.bbox is None

      def test_full_round_trip(self) -> None:
          line = OcrLine(
              text="Link in bio",
              confidence=0.95,
              bbox="[[0,0],[10,0],[10,5],[0,5]]",
          )
          assert line.bbox == "[[0,0],[10,0],[10,5],[0,5]]"

      def test_is_frozen(self) -> None:
          line = OcrLine(text="x", confidence=0.5)
          with pytest.raises(FrozenInstanceError):
              line.text = "y"  # type: ignore[misc]


  class _StubOcrEngine:
      def extract_text(
          self, image_path: str, *, min_confidence: float = 0.5
      ) -> list[OcrLine]:
          return []


  class _StubFaceCounter:
      def count_faces(self, image_path: str) -> int:
          return 0


  class TestOcrEngineProtocol:
      def test_stub_satisfies_protocol(self) -> None:
          engine: OcrEngine = _StubOcrEngine()
          assert isinstance(engine, OcrEngine)
          assert engine.extract_text("x.jpg") == []


  class TestFaceCounterProtocol:
      def test_stub_satisfies_protocol(self) -> None:
          counter: FaceCounter = _StubFaceCounter()
          assert isinstance(counter, FaceCounter)
          assert counter.count_faces("x.jpg") == 0
  ```

  Also add a `FrameTextRepository` runtime_checkable test in `tests/unit/ports/test_ocr_engine.py` (or create `tests/unit/ports/test_repositories.py`): verify a stub class with the 4 methods passes `isinstance(stub, FrameTextRepository)`.
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/ports/ocr_engine.py`
    - `grep -q 'class OcrEngine(Protocol):' src/vidscope/ports/ocr_engine.py` exit 0
    - `grep -q 'class FaceCounter(Protocol):' src/vidscope/ports/ocr_engine.py` exit 0
    - `grep -q 'class OcrLine:' src/vidscope/ports/ocr_engine.py` exit 0
    - `grep -q 'class FrameTextRepository(Protocol):' src/vidscope/ports/repositories.py` exit 0
    - `grep -q 'frame_texts: FrameTextRepository' src/vidscope/ports/unit_of_work.py` exit 0
    - `grep -q '"OcrEngine"' src/vidscope/ports/__init__.py` exit 0
    - `grep -q '"FrameTextRepository"' src/vidscope/ports/__init__.py` exit 0
    - `uv run python -c "from vidscope.ports import OcrEngine, FaceCounter, OcrLine, FrameTextRepository; print('ok')"` prints `ok`
    - `uv run pytest tests/unit/ports/test_ocr_engine.py -x -q` exit 0
    - `uv run mypy src` exit 0
    - `uv run lint-imports` exit 0 (ports-are-pure still green — no third-party imports in new port file)
    <automated>uv run pytest tests/unit/ports -q</automated>
  </acceptance_criteria>
</task>

<task id="T03-vision-adapters-and-contracts" type="auto" tdd="true">
  <name>T03: Create vidscope.adapters.vision submodule (RapidOcrEngine + HaarcascadeFaceCounter) + import-linter contract</name>

  <read_first>
    - `src/vidscope/adapters/text/__init__.py` — the minimal __init__ pattern for a self-contained adapter submodule.
    - `src/vidscope/adapters/text/regex_link_extractor.py` (entire file, 139 lines) — pattern for a pure adapter (no I/O, one class, docstring-heavy).
    - `src/vidscope/adapters/whisper/` — read the `__init__.py` and main adapter to understand the LAZY MODEL LOAD pattern. The `FasterWhisperTranscriber` uses `_model = None` then `_load_model()` on first `transcribe()` call.
    - `src/vidscope/ports/ocr_engine.py` (from T02) — the OcrEngine / FaceCounter Protocols to implement.
    - `.importlinter` (entire file, 199 lines) — specifically the `text-adapter-is-self-contained` contract (lines 82-99) which is the EXACT template for the new `vision-adapter-is-self-contained` contract.
    - `.gsd/milestones/M008/M008-RESEARCH.md` §1.2 (rapidocr 1.4.x API), §1.3 (lazy load pattern), §1.4 (graceful degradation), §2.3 (OpenCV detectMultiScale API).
    - `tests/fixtures/` — check whether any Pillow-generated fixture pattern already exists (unlikely; we'll create one).
  </read_first>

  <behavior>
    - Test 1 (RapidOcrEngine init): `RapidOcrEngine()` constructs without importing rapidocr_onnxruntime (lazy — `_engine is None` after init).
    - Test 2 (RapidOcrEngine lazy import): when rapidocr_onnxruntime is NOT installed, `engine.extract_text("any.jpg")` returns `[]` (not raises).
    - Test 3 (RapidOcrEngine missing file): `engine.extract_text("/nonexistent/path.jpg")` returns `[]`.
    - Test 4 (RapidOcrEngine with stubbed engine): given a monkeypatched `_engine` returning `([[[0,0],[10,0],[10,5],[0,5]], "Hello", 0.95], [...])`, `extract_text` returns a list of `OcrLine` with correct text/confidence/bbox.
    - Test 5 (RapidOcrEngine confidence filter): items with confidence < `min_confidence` are filtered out.
    - Test 6 (RapidOcrEngine None result): when `_engine(image_path)` returns `(None, 0.0)`, `extract_text` returns `[]`.
    - Test 7 (HaarcascadeFaceCounter init): `HaarcascadeFaceCounter()` constructs without importing cv2 (lazy).
    - Test 8 (HaarcascadeFaceCounter missing cv2): when cv2 is NOT available, `count_faces("any.jpg")` returns `0`.
    - Test 9 (HaarcascadeFaceCounter missing file): `count_faces("/nonexistent.jpg")` returns `0`.
    - Test 10 (HaarcascadeFaceCounter with stubbed cascade): given a monkeypatched `_cascade` returning a numpy-like array of shape (2, 4), `count_faces` returns `2`.
    - Architecture: `uv run lint-imports` reports 10 contracts green (new `vision-adapter-is-self-contained`).
  </behavior>

  <action>
  **Step A — Create `src/vidscope/adapters/vision/__init__.py`:**

  ```python
  """Vision adapter submodule for M008 (R047, R049).

  Exports a :class:`RapidOcrEngine` (OcrEngine port) and a
  :class:`HaarcascadeFaceCounter` (FaceCounter port). Both adapters
  lazy-load their heavy deps (``rapidocr_onnxruntime``, ``cv2``) so
  importing this package is cheap and safe even when the optional
  ``[vision]`` extra is not installed.

  Import-linter contract ``vision-adapter-is-self-contained`` forbids
  this package from importing any other adapter, infrastructure,
  application, pipeline, CLI, or MCP module.
  """

  from __future__ import annotations

  from vidscope.adapters.vision.haarcascade_face_counter import (
      HaarcascadeFaceCounter,
  )
  from vidscope.adapters.vision.rapidocr_engine import RapidOcrEngine

  __all__ = ["HaarcascadeFaceCounter", "RapidOcrEngine"]
  ```

  **Step B — Create `src/vidscope/adapters/vision/rapidocr_engine.py`:**

  ```python
  """RapidOCR-based OcrEngine adapter (M008/R047).

  Wraps ``rapidocr-onnxruntime 1.4.x`` (CPU-only, ONNX) behind the
  :class:`~vidscope.ports.ocr_engine.OcrEngine` protocol. Lazy-loads
  the ONNX model on the first :meth:`extract_text` call so
  constructor is cheap (~0ms, no network). Gracefully degrades when
  the library is not installed — returns ``[]`` instead of raising.

  See M008 RESEARCH §1.2 for the v1.4.x return-tuple shape.
  """

  from __future__ import annotations

  import json
  import logging
  from pathlib import Path
  from typing import Any

  from vidscope.ports.ocr_engine import OcrLine

  _logger = logging.getLogger(__name__)

  __all__ = ["RapidOcrEngine"]


  class RapidOcrEngine:
      """OcrEngine implementation backed by rapidocr-onnxruntime 1.4.x."""

      def __init__(self) -> None:
          # Lazy: do NOT import or instantiate rapidocr here. The
          # ONNX model (~50 MB) downloads on first RapidOCR() call.
          self._engine: Any | None = None
          self._unavailable: bool = False

      def _get_engine(self) -> Any | None:
          """Return the underlying RapidOCR instance or ``None`` if
          unavailable. Caches the failure to avoid repeated
          ImportError on every frame.
          """
          if self._unavailable:
              return None
          if self._engine is not None:
              return self._engine
          try:
              from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
          except ImportError:
              _logger.info(
                  "rapidocr-onnxruntime not installed — OCR disabled. "
                  "Install with: uv sync --extra vision"
              )
              self._unavailable = True
              return None
          self._engine = RapidOCR()
          return self._engine

      def extract_text(
          self, image_path: str, *, min_confidence: float = 0.5
      ) -> list[OcrLine]:
          """Run OCR on ``image_path`` and return filtered lines.

          Returns ``[]`` when: (a) rapidocr is not installed,
          (b) the file does not exist, (c) no text was detected,
          or (d) all detected text was below ``min_confidence``.
          """
          if not Path(image_path).exists():
              _logger.debug("OCR skipped: file missing %s", image_path)
              return []

          engine = self._get_engine()
          if engine is None:
              return []

          try:
              result, _elapse = engine(image_path)
          except Exception as exc:  # noqa: BLE001 — library internals
              _logger.warning(
                  "rapidocr failed on %s: %s (continuing with empty result)",
                  image_path,
                  exc,
              )
              return []

          if result is None:
              return []

          lines: list[OcrLine] = []
          for item in result:
              # v1.4.x shape: [[bbox_4pts], text, confidence]
              if len(item) < 3:
                  continue
              bbox_raw, text_raw, conf_raw = item[0], item[1], item[2]
              try:
                  confidence = float(conf_raw)
              except (TypeError, ValueError):
                  continue
              if confidence < min_confidence:
                  continue
              text = str(text_raw).strip()
              if not text:
                  continue
              # Serialise bbox as JSON so the value remains opaque
              # in the domain (OcrLine.bbox: str | None).
              try:
                  bbox = json.dumps(
                      [[float(p[0]), float(p[1])] for p in bbox_raw]
                  )
              except (TypeError, ValueError, IndexError):
                  bbox = None
              lines.append(OcrLine(text=text, confidence=confidence, bbox=bbox))
          return lines
  ```

  **Step C — Create `src/vidscope/adapters/vision/haarcascade_face_counter.py`:**

  ```python
  """OpenCV Haarcascade-based FaceCounter adapter (M008/R049).

  Wraps ``cv2.CascadeClassifier`` with the bundled
  ``haarcascade_frontalface_default.xml`` behind the
  :class:`~vidscope.ports.ocr_engine.FaceCounter` protocol. Lazy-
  loads ``cv2`` on first :meth:`count_faces` call. Gracefully
  degrades when ``opencv-python-headless`` is not installed or the
  cascade file cannot be located — returns ``0``.

  See M008 RESEARCH §2.3 for the detectMultiScale API.
  """

  from __future__ import annotations

  import logging
  from pathlib import Path
  from typing import Any

  _logger = logging.getLogger(__name__)

  __all__ = ["HaarcascadeFaceCounter"]


  class HaarcascadeFaceCounter:
      """FaceCounter implementation backed by OpenCV haarcascade."""

      def __init__(self) -> None:
          self._cascade: Any | None = None
          self._cv2: Any | None = None
          self._unavailable: bool = False

      def _load(self) -> tuple[Any, Any] | None:
          """Return (cv2 module, cascade instance) or ``None``."""
          if self._unavailable:
              return None
          if self._cv2 is not None and self._cascade is not None:
              return self._cv2, self._cascade
          try:
              import cv2  # noqa: PLC0415
          except ImportError:
              _logger.info(
                  "opencv-python-headless not installed — face count disabled. "
                  "Install with: uv sync --extra vision"
              )
              self._unavailable = True
              return None
          try:
              cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
              cascade = cv2.CascadeClassifier(cascade_path)
              if cascade.empty():
                  _logger.warning("haarcascade file empty at %s", cascade_path)
                  self._unavailable = True
                  return None
          except (AttributeError, OSError) as exc:
              _logger.warning("failed to load haarcascade: %s", exc)
              self._unavailable = True
              return None
          self._cv2 = cv2
          self._cascade = cascade
          return cv2, cascade

      def count_faces(self, image_path: str) -> int:
          """Return the number of frontal faces in the image, or
          ``0`` when any step fails.
          """
          if not Path(image_path).exists():
              return 0
          loaded = self._load()
          if loaded is None:
              return 0
          cv2, cascade = loaded
          try:
              img = cv2.imread(image_path)
              if img is None:
                  return 0
              gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
              faces = cascade.detectMultiScale(
                  gray,
                  scaleFactor=1.1,
                  minNeighbors=5,
                  minSize=(30, 30),
              )
          except Exception as exc:  # noqa: BLE001 — library internals
              _logger.warning(
                  "haarcascade failed on %s: %s (continuing with 0)",
                  image_path,
                  exc,
              )
              return 0
          # detectMultiScale returns np.ndarray shape (N, 4) or empty tuple
          try:
              return int(len(faces))
          except TypeError:
              return 0
  ```

  **Step D — Update `.importlinter`:**

  1. Add a new contract after the `text-adapter-is-self-contained` block (after line 99):

  ```ini
  [importlinter:contract:vision-adapter-is-self-contained]
  name = vision adapter does not import other adapters
  type = forbidden
  source_modules =
      vidscope.adapters.vision
  forbidden_modules =
      vidscope.adapters.sqlite
      vidscope.adapters.fs
      vidscope.adapters.ytdlp
      vidscope.adapters.whisper
      vidscope.adapters.ffmpeg
      vidscope.adapters.heuristic
      vidscope.adapters.llm
      vidscope.adapters.text
      vidscope.infrastructure
      vidscope.application
      vidscope.pipeline
      vidscope.cli
      vidscope.mcp
  ```

  2. Update existing contracts to include `vidscope.adapters.vision` in their `forbidden_modules` — specifically:
     - `text-adapter-is-self-contained` (add `vidscope.adapters.vision` after `vidscope.adapters.llm`)
     - `llm-never-imports-other-adapters` (add `vidscope.adapters.vision`)
     - `sqlite-never-imports-fs` (add `vidscope.adapters.vision`) — and rename its `name` comment to indicate vision is also forbidden.
     - `fs-never-imports-sqlite` (add `vidscope.adapters.vision`)

  Verify all existing contracts remain green after edits.

  **Step E — Create tests:**

  1. `tests/unit/adapters/vision/__init__.py` — empty file.

  2. `tests/unit/adapters/vision/test_rapidocr_engine.py`:

  ```python
  """Unit tests for RapidOcrEngine — library-absent + stubbed paths."""

  from __future__ import annotations

  from pathlib import Path
  from typing import Any

  import pytest

  from vidscope.adapters.vision import RapidOcrEngine
  from vidscope.ports import OcrLine


  class TestRapidOcrEngineLazy:
      def test_init_does_not_load_engine(self) -> None:
          engine = RapidOcrEngine()
          # The underlying rapidocr engine is lazy: None until first call.
          assert engine._engine is None  # noqa: SLF001
          assert engine._unavailable is False  # noqa: SLF001

      def test_extract_text_missing_file_returns_empty(self) -> None:
          engine = RapidOcrEngine()
          assert engine.extract_text("/nonexistent/path.jpg") == []

      def test_extract_text_when_library_missing_returns_empty(
          self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
      ) -> None:
          # Force the ImportError path.
          engine = RapidOcrEngine()
          engine._unavailable = True  # noqa: SLF001
          jpg = tmp_path / "f.jpg"
          jpg.write_bytes(b"not-a-real-jpg-but-exists")
          assert engine.extract_text(str(jpg)) == []


  class _StubEngine:
      """Mimics rapidocr_onnxruntime.RapidOCR.__call__ return shape."""

      def __init__(self, result: Any) -> None:
          self._result = result

      def __call__(self, image_path: str) -> tuple[Any, float]:
          return self._result, 0.01


  class TestRapidOcrEngineParsing:
      def _with_stub(self, result: Any, tmp_path: Path) -> tuple[RapidOcrEngine, str]:
          jpg = tmp_path / "f.jpg"
          jpg.write_bytes(b"fake-jpg-file")
          engine = RapidOcrEngine()
          engine._engine = _StubEngine(result)  # noqa: SLF001
          return engine, str(jpg)

      def test_none_result_returns_empty(self, tmp_path: Path) -> None:
          engine, path = self._with_stub(None, tmp_path)
          assert engine.extract_text(path) == []

      def test_single_line_parsed(self, tmp_path: Path) -> None:
          stub_result = [
              [
                  [[0, 0], [10, 0], [10, 5], [0, 5]],
                  "Link in bio",
                  0.95,
              ]
          ]
          engine, path = self._with_stub(stub_result, tmp_path)
          lines = engine.extract_text(path)
          assert len(lines) == 1
          assert lines[0].text == "Link in bio"
          assert lines[0].confidence == 0.95
          assert lines[0].bbox is not None

      def test_confidence_filter_drops_low_conf(self, tmp_path: Path) -> None:
          stub_result = [
              [[[0, 0], [10, 0], [10, 5], [0, 5]], "Hello", 0.9],
              [[[0, 0], [10, 0], [10, 5], [0, 5]], "Noise", 0.3],
          ]
          engine, path = self._with_stub(stub_result, tmp_path)
          lines = engine.extract_text(path, min_confidence=0.5)
          assert len(lines) == 1
          assert lines[0].text == "Hello"

      def test_empty_text_dropped(self, tmp_path: Path) -> None:
          stub_result = [
              [[[0, 0], [10, 0], [10, 5], [0, 5]], "   ", 0.9],
          ]
          engine, path = self._with_stub(stub_result, tmp_path)
          assert engine.extract_text(path) == []

      def test_bbox_is_json_string(self, tmp_path: Path) -> None:
          stub_result = [
              [[[1, 2], [3, 4], [5, 6], [7, 8]], "X", 0.9],
          ]
          engine, path = self._with_stub(stub_result, tmp_path)
          import json  # noqa: PLC0415
          lines = engine.extract_text(path)
          parsed = json.loads(lines[0].bbox or "null")
          assert parsed == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]

      def test_engine_exception_returns_empty(self, tmp_path: Path) -> None:
          class _Boom:
              def __call__(self, image_path: str) -> Any:
                  raise RuntimeError("boom")
          jpg = tmp_path / "f.jpg"
          jpg.write_bytes(b"x")
          engine = RapidOcrEngine()
          engine._engine = _Boom()  # noqa: SLF001
          assert engine.extract_text(str(jpg)) == []

      def test_returns_ocr_line_instances(self, tmp_path: Path) -> None:
          stub_result = [[[[0, 0], [1, 0], [1, 1], [0, 1]], "X", 0.9]]
          engine, path = self._with_stub(stub_result, tmp_path)
          lines = engine.extract_text(path)
          assert all(isinstance(line, OcrLine) for line in lines)
  ```

  3. `tests/unit/adapters/vision/test_face_counter.py`:

  ```python
  """Unit tests for HaarcascadeFaceCounter."""

  from __future__ import annotations

  from pathlib import Path
  from typing import Any

  import pytest

  from vidscope.adapters.vision import HaarcascadeFaceCounter


  class TestHaarcascadeLazy:
      def test_init_does_not_load(self) -> None:
          counter = HaarcascadeFaceCounter()
          assert counter._cv2 is None  # noqa: SLF001
          assert counter._cascade is None  # noqa: SLF001

      def test_missing_file_returns_zero(self) -> None:
          counter = HaarcascadeFaceCounter()
          assert counter.count_faces("/nonexistent.jpg") == 0

      def test_library_missing_returns_zero(
          self, tmp_path: Path
      ) -> None:
          jpg = tmp_path / "f.jpg"
          jpg.write_bytes(b"x")
          counter = HaarcascadeFaceCounter()
          counter._unavailable = True  # noqa: SLF001
          assert counter.count_faces(str(jpg)) == 0


  class _StubCascade:
      def __init__(self, face_count: int) -> None:
          self._count = face_count
      def empty(self) -> bool:
          return False
      def detectMultiScale(self, *args: Any, **kwargs: Any) -> list[tuple[int, int, int, int]]:
          return [(0, 0, 10, 10)] * self._count


  class _StubCv2:
      """Minimal cv2 mock exposing imread + cvtColor + COLOR_BGR2GRAY."""
      COLOR_BGR2GRAY = 42
      def imread(self, path: str) -> Any:
          return object() if Path(path).exists() else None
      def cvtColor(self, img: Any, code: int) -> Any:
          return img


  class TestHaarcascadeCounting:
      def _prime(
          self,
          counter: HaarcascadeFaceCounter,
          face_count: int,
          tmp_path: Path,
      ) -> str:
          jpg = tmp_path / "f.jpg"
          jpg.write_bytes(b"x")
          counter._cv2 = _StubCv2()  # noqa: SLF001
          counter._cascade = _StubCascade(face_count)  # noqa: SLF001
          return str(jpg)

      def test_counts_single_face(self, tmp_path: Path) -> None:
          counter = HaarcascadeFaceCounter()
          path = self._prime(counter, 1, tmp_path)
          assert counter.count_faces(path) == 1

      def test_counts_multiple_faces(self, tmp_path: Path) -> None:
          counter = HaarcascadeFaceCounter()
          path = self._prime(counter, 3, tmp_path)
          assert counter.count_faces(path) == 3

      def test_no_faces(self, tmp_path: Path) -> None:
          counter = HaarcascadeFaceCounter()
          path = self._prime(counter, 0, tmp_path)
          assert counter.count_faces(path) == 0

      def test_cv2_exception_returns_zero(self, tmp_path: Path) -> None:
          jpg = tmp_path / "f.jpg"
          jpg.write_bytes(b"x")

          class _Boom:
              def empty(self) -> bool:
                  return False
              def detectMultiScale(self, *args: Any, **kwargs: Any) -> Any:
                  raise RuntimeError("boom")

          counter = HaarcascadeFaceCounter()
          counter._cv2 = _StubCv2()  # noqa: SLF001
          counter._cascade = _Boom()  # noqa: SLF001
          assert counter.count_faces(str(jpg)) == 0

      def test_imread_none_returns_zero(self, tmp_path: Path) -> None:
          jpg = tmp_path / "f.jpg"
          jpg.write_bytes(b"x")

          class _Cv2Fails:
              COLOR_BGR2GRAY = 42
              def imread(self, path: str) -> Any:
                  return None
              def cvtColor(self, img: Any, code: int) -> Any:
                  return img

          counter = HaarcascadeFaceCounter()
          counter._cv2 = _Cv2Fails()  # noqa: SLF001
          counter._cascade = _StubCascade(5)  # noqa: SLF001
          assert counter.count_faces(str(jpg)) == 0
  ```
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/adapters/vision/__init__.py`
    - `test -f src/vidscope/adapters/vision/rapidocr_engine.py`
    - `test -f src/vidscope/adapters/vision/haarcascade_face_counter.py`
    - `grep -q 'class RapidOcrEngine:' src/vidscope/adapters/vision/rapidocr_engine.py` exit 0
    - `grep -q 'class HaarcascadeFaceCounter:' src/vidscope/adapters/vision/haarcascade_face_counter.py` exit 0
    - `grep -q 'vision-adapter-is-self-contained' .importlinter` exit 0
    - `grep -q 'vidscope.adapters.vision' .importlinter` exit 0
    - `uv run python -c "from vidscope.adapters.vision import RapidOcrEngine, HaarcascadeFaceCounter; e = RapidOcrEngine(); c = HaarcascadeFaceCounter(); print('ok')"` prints `ok`
    - `uv run python -c "from vidscope.adapters.vision import RapidOcrEngine; e = RapidOcrEngine(); assert e.extract_text('/no/such/file.jpg') == []"` exit 0
    - `uv run pytest tests/unit/adapters/vision -x -q` exit 0 (≥ 15 tests green)
    - `uv run lint-imports` exit 0 with `vision-adapter-is-self-contained` contract green and all prior contracts still green
    - `uv run mypy src` exit 0
    - `uv run ruff check src tests` exit 0
    <automated>uv run pytest tests/unit/adapters/vision -q && uv run lint-imports</automated>
  </acceptance_criteria>
</task>

<task id="T04-sqlite-schema-and-repository" type="auto" tdd="true">
  <name>T04: Add frame_texts table + frame_texts_fts + videos.thumbnail_key/content_shape + FrameTextRepositorySQLite + UnitOfWork wiring</name>

  <read_first>
    - `src/vidscope/adapters/sqlite/schema.py` (entire file, 419 lines) — the exact Table + Index + _ensure_* pattern. Note lines 390-414 (`_ensure_videos_metadata_columns`) for adding nullable columns, and lines 332-339 + 357-359 (`_FTS5_CREATE_SQL` + `_create_fts5`) for FTS5 virtual tables.
    - `src/vidscope/adapters/sqlite/link_repository.py` (entire file, 153 lines) — the EXACT repository pattern to replicate for `FrameTextRepositorySQLite`: `add_many_*` with dedup + payload build + INSERT, `list_for_video` with mappings().all(), `has_any_for_video` with func.count. Our extra twist: also INSERT INTO frame_texts_fts for each row.
    - `src/vidscope/adapters/sqlite/search_index.py` — the FTS5 write pattern. The existing SearchIndexSQLite uses raw SQL `INSERT INTO search_index (video_id, source, text) VALUES (...)` — copy this idiom for `frame_texts_fts`.
    - `src/vidscope/adapters/sqlite/unit_of_work.py` (entire file, 138 lines) — where to add `self.frame_texts = FrameTextRepositorySQLite(self._connection)` in `__enter__`.
    - `src/vidscope/ports/repositories.py` (from T02) — the `FrameTextRepository` Protocol to implement.
    - `src/vidscope/domain/entities.py` (from T01) — `FrameText` entity.
    - `tests/unit/adapters/sqlite/test_link_repository.py` — mirror for `test_frame_text_repository.py`.
    - `tests/unit/adapters/sqlite/conftest.py` — how the in-memory engine is built for repository tests.
  </read_first>

  <behavior>
    - Schema tests: `videos.thumbnail_key` and `videos.content_shape` columns are present. `frame_texts` table exists with columns `id`, `video_id`, `frame_id`, `text`, `confidence`, `bbox`, `created_at`. `frame_texts_fts` FTS5 virtual table exists.
    - Schema upgrade: running `init_db` twice on the same engine is a no-op. On a pre-M008 DB (simulate by creating an older `videos` schema without thumbnail_key and without frame_texts), `init_db` adds the columns and creates the tables without data loss.
    - FK cascade: deleting a frame cascades to its frame_texts rows. Deleting a video cascades to all its frames AND frame_texts.
    - Repository `add_many_for_frame` inserts rows into frame_texts AND into frame_texts_fts.
    - Repository `list_for_video` returns rows ordered by `frame_id` then `id`.
    - Repository `has_any_for_video` returns True when at least one row exists.
    - Repository `find_video_ids_by_text` returns distinct video ids matching an FTS5 query (case-insensitive + diacritic-insensitive thanks to tokenizer).
  </behavior>

  <action>
  **Step A — Extend `src/vidscope/adapters/sqlite/schema.py`:**

  1. Add two columns to the `videos` Table (between the existing `music_artist` column at line 108 and the end of the Table constructor at line 109):

  ```python
      Column("thumbnail_key", Text, nullable=True),
      Column("content_shape", String(32), nullable=True),
  ```

  2. Add a new `frame_texts` Table definition AFTER `frames` (around line 141):

  ```python
  frame_texts = Table(
      "frame_texts",
      metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column(
          "video_id",
          Integer,
          ForeignKey("videos.id", ondelete="CASCADE"),
          nullable=False,
      ),
      Column(
          "frame_id",
          Integer,
          ForeignKey("frames.id", ondelete="CASCADE"),
          nullable=False,
      ),
      Column("text", Text, nullable=False),
      Column("confidence", Float, nullable=False),
      Column("bbox", Text, nullable=True),
      Column(
          "created_at",
          DateTime(timezone=True),
          nullable=False,
          default=_utc_now,
      ),
  )
  Index("idx_frame_texts_video_id", frame_texts.c.video_id)
  Index("idx_frame_texts_frame_id", frame_texts.c.frame_id)
  ```

  3. Add `"frame_texts"` to the `__all__` list at the top.

  4. Add a new FTS5 DDL constant after `_FTS5_CREATE_SQL` (after line 339):

  ```python
  _FTS5_FRAME_TEXTS_SQL = """
  CREATE VIRTUAL TABLE IF NOT EXISTS frame_texts_fts USING fts5(
      frame_text_id UNINDEXED,
      video_id UNINDEXED,
      text,
      tokenize = 'unicode61 remove_diacritics 2'
  )
  """
  ```

  5. Update `init_db` (lines 342-354) to call the new helpers:

  ```python
  def init_db(engine: Engine) -> None:
      """Create every table and the FTS5 virtual tables. Idempotent.

      Safe to call on every startup — :meth:`MetaData.create_all` uses
      ``CREATE TABLE IF NOT EXISTS`` under the hood, and the FTS5 DDL
      plus the ``_ensure_*`` helpers both guard themselves against
      double-execution on upgraded DBs.
      """
      metadata.create_all(engine)
      with engine.begin() as conn:
          _create_fts5(conn)
          _create_frame_texts_fts(conn)
          _ensure_videos_creator_id(conn)
          _ensure_videos_metadata_columns(conn)
          _ensure_videos_visual_columns(conn)
          _ensure_frame_texts_table(conn)
  ```

  6. Add the new helper functions at the end of the `_ensure_*` block (after `_ensure_videos_metadata_columns`):

  ```python
  def _create_frame_texts_fts(conn: Connection) -> None:
      """Execute the frame_texts_fts FTS5 DDL on an existing connection."""
      conn.execute(text(_FTS5_FRAME_TEXTS_SQL))


  def _ensure_videos_visual_columns(conn: Connection) -> None:
      """Add M008 visual columns on upgraded databases. Idempotent.

      M008/S01 adds two nullable columns on ``videos``:
      ``thumbnail_key`` (storage key for the canonical thumbnail) and
      ``content_shape`` (one of ``talking_head / broll / mixed /
      unknown``). On fresh installs the Core ``metadata.create_all``
      path declares the columns inline; on pre-M008 databases we must
      explicitly ALTER.
      """
      cols = {
          row[1]
          for row in conn.execute(text("PRAGMA table_info(videos)"))
      }
      if "thumbnail_key" not in cols:
          conn.execute(text("ALTER TABLE videos ADD COLUMN thumbnail_key TEXT"))
      if "content_shape" not in cols:
          conn.execute(
              text("ALTER TABLE videos ADD COLUMN content_shape VARCHAR(32)")
          )


  def _ensure_frame_texts_table(conn: Connection) -> None:
      """Create frame_texts table on upgraded databases. Idempotent.

      Fresh installs get the table via ``metadata.create_all``; pre-M008
      databases hit this path.
      """
      tables = {
          row[0]
          for row in conn.execute(
              text("SELECT name FROM sqlite_master WHERE type='table'")
          )
      }
      if "frame_texts" in tables:
          return
      conn.execute(
          text(
              "CREATE TABLE frame_texts ("
              "id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE, "
              "frame_id INTEGER NOT NULL REFERENCES frames(id) ON DELETE CASCADE, "
              "text TEXT NOT NULL, "
              "confidence REAL NOT NULL, "
              "bbox TEXT, "
              "created_at DATETIME NOT NULL"
              ")"
          )
      )
      conn.execute(
          text(
              "CREATE INDEX IF NOT EXISTS idx_frame_texts_video_id "
              "ON frame_texts(video_id)"
          )
      )
      conn.execute(
          text(
              "CREATE INDEX IF NOT EXISTS idx_frame_texts_frame_id "
              "ON frame_texts(frame_id)"
          )
      )
  ```

  **Step B — Create `src/vidscope/adapters/sqlite/frame_text_repository.py`:**

  ```python
  """SQLite implementation of :class:`FrameTextRepository`.

  Uses SQLAlchemy Core for the ``frame_texts`` table and raw SQL for
  the ``frame_texts_fts`` virtual table (FTS5 is not part of Core's
  DDL vocabulary). Every ``add_many_for_frame`` call writes to BOTH
  tables in the same transaction.
  """

  from __future__ import annotations

  from datetime import UTC, datetime
  from typing import Any, cast

  from sqlalchemy import func, select, text
  from sqlalchemy.engine import Connection
  from sqlalchemy.exc import SQLAlchemyError

  from vidscope.adapters.sqlite.schema import frame_texts as frame_texts_table
  from vidscope.domain import FrameText, VideoId
  from vidscope.domain.errors import StorageError

  __all__ = ["FrameTextRepositorySQLite"]


  class FrameTextRepositorySQLite:
      """Repository for :class:`FrameText` backed by SQLite + FTS5."""

      def __init__(self, connection: Connection) -> None:
          self._conn = connection

      # ------------------------------------------------------------------
      # Writes
      # ------------------------------------------------------------------

      def add_many_for_frame(
          self,
          frame_id: int,
          video_id: VideoId,
          texts: list[FrameText],
      ) -> list[FrameText]:
          """INSERT frame_texts rows + sync frame_texts_fts. No-op on
          empty input."""
          if not texts:
              return []
          try:
              now = datetime.now(UTC)
              payloads: list[dict[str, Any]] = []
              for t in texts:
                  payloads.append(
                      {
                          "video_id": int(video_id),
                          "frame_id": int(frame_id),
                          "text": t.text,
                          "confidence": float(t.confidence),
                          "bbox": t.bbox,
                          "created_at": now,
                      }
                  )
              result = self._conn.execute(
                  frame_texts_table.insert().values(payloads)
              )
              if result.rowcount is None or result.rowcount == 0:
                  raise StorageError(
                      f"add_many_for_frame: insert acknowledged but no rows "
                      f"written for frame {int(frame_id)}"
                  )
          except StorageError:
              raise
          except SQLAlchemyError as exc:
              raise StorageError(
                  f"add_many_for_frame failed for frame {int(frame_id)}: {exc}",
                  cause=exc,
              ) from exc

          # Re-query the inserted rows to capture their ids + sync FTS5.
          inserted = self._list_by_frame(frame_id)
          # Sync into frame_texts_fts. Use raw SQL — FTS5 is not a Core
          # Table so we cannot use insert().values().
          for row in inserted:
              if row.id is None:
                  continue
              self._conn.execute(
                  text(
                      "INSERT INTO frame_texts_fts "
                      "(frame_text_id, video_id, text) "
                      "VALUES (:frame_text_id, :video_id, :text)"
                  ),
                  {
                      "frame_text_id": int(row.id),
                      "video_id": int(row.video_id),
                      "text": row.text,
                  },
              )
          return inserted

      # ------------------------------------------------------------------
      # Reads
      # ------------------------------------------------------------------

      def _list_by_frame(self, frame_id: int) -> list[FrameText]:
          rows = (
              self._conn.execute(
                  select(frame_texts_table)
                  .where(frame_texts_table.c.frame_id == int(frame_id))
                  .order_by(frame_texts_table.c.id.asc())
              )
              .mappings()
              .all()
          )
          return [_row_to_frame_text(row) for row in rows]

      def list_for_video(self, video_id: VideoId) -> list[FrameText]:
          rows = (
              self._conn.execute(
                  select(frame_texts_table)
                  .where(frame_texts_table.c.video_id == int(video_id))
                  .order_by(
                      frame_texts_table.c.frame_id.asc(),
                      frame_texts_table.c.id.asc(),
                  )
              )
              .mappings()
              .all()
          )
          return [_row_to_frame_text(row) for row in rows]

      def has_any_for_video(self, video_id: VideoId) -> bool:
          count = self._conn.execute(
              select(func.count())
              .select_from(frame_texts_table)
              .where(frame_texts_table.c.video_id == int(video_id))
          ).scalar()
          return bool(count and int(count) > 0)

      def find_video_ids_by_text(
          self, query: str, *, limit: int = 50
      ) -> list[VideoId]:
          """FTS5 MATCH on frame_texts_fts. Returns distinct video ids."""
          if not query.strip():
              return []
          try:
              rows = self._conn.execute(
                  text(
                      "SELECT DISTINCT video_id FROM frame_texts_fts "
                      "WHERE frame_texts_fts MATCH :q "
                      "LIMIT :lim"
                  ),
                  {"q": query, "lim": int(limit)},
              ).all()
          except SQLAlchemyError as exc:
              # Malformed FTS5 query — treat as no-match. This mirrors
              # SearchIndexSQLite behaviour on bad queries.
              raise StorageError(
                  f"find_video_ids_by_text failed for query {query!r}: {exc}",
                  cause=exc,
              ) from exc
          return [VideoId(int(row[0])) for row in rows]


  # ---------------------------------------------------------------------------
  # Row <-> entity translation
  # ---------------------------------------------------------------------------


  def _row_to_frame_text(row: Any) -> FrameText:
      data = cast("dict[str, Any]", dict(row))
      return FrameText(
          id=int(data["id"]) if data.get("id") is not None else None,
          video_id=VideoId(int(data["video_id"])),
          frame_id=int(data["frame_id"]),
          text=str(data["text"]),
          confidence=float(data["confidence"]),
          bbox=(
              str(data["bbox"])
              if data.get("bbox") is not None
              else None
          ),
          created_at=_ensure_utc(data.get("created_at")),
      )


  def _ensure_utc(value: datetime | None) -> datetime | None:
      if value is None:
          return None
      if value.tzinfo is None:
          return value.replace(tzinfo=UTC)
      return value.astimezone(UTC)
  ```

  **Step C — Update `src/vidscope/adapters/sqlite/unit_of_work.py`:**

  1. Add import:
  ```python
  from vidscope.adapters.sqlite.frame_text_repository import (
      FrameTextRepositorySQLite,
  )
  ```

  2. Add import from `vidscope.ports`:
  ```python
  from vidscope.ports import (
      ...,
      FrameTextRepository,
      ...,
  )
  ```

  3. Add `self.frame_texts: FrameTextRepository` as a typed slot in `__init__` (after `self.frames`).

  4. In `__enter__`, add `self.frame_texts = FrameTextRepositorySQLite(self._connection)` (after the `FrameRepositorySQLite` line).

  **Step D — Tests:**

  1. `tests/unit/adapters/sqlite/test_frame_text_repository.py`:

  Mirror the structure of `tests/unit/adapters/sqlite/test_link_repository.py`. Tests:
  - `test_add_many_inserts_rows` — insert 2 rows, verify list_for_video returns 2.
  - `test_add_many_syncs_fts` — insert, then raw SQL SELECT * FROM frame_texts_fts WHERE video_id=? returns 2 rows.
  - `test_empty_list_is_noop` — add_many_for_frame with [] returns [].
  - `test_list_for_video_empty` — returns [] when no rows.
  - `test_list_for_video_ordered` — insert from 2 different frame_ids, verify ordered by frame_id then id.
  - `test_has_any_for_video_true_false` — False before, True after insert.
  - `test_find_video_ids_by_text_bare_word` — insert "Link in bio", search "link" returns matching video_id.
  - `test_find_video_ids_by_text_case_insensitive` — search "LINK" returns matching video_id.
  - `test_find_video_ids_by_text_diacritic_insensitive` — insert "prömo", search "promo" returns match (tokenizer remove_diacritics 2).
  - `test_find_video_ids_by_text_no_match` — returns [].
  - `test_cascade_on_frame_delete` — insert frame_texts, delete parent frame, verify frame_texts rows gone.
  - `test_cascade_on_video_delete` — insert frame_texts, delete parent video, verify frame_texts rows AND frame_texts_fts rows gone (for the FTS, verify via raw SQL count). NOTE: DELETE on the parent videos row cascades to frames AND to frame_texts via FK; the FTS5 sync on delete is a known gap — document it as "accept" in the threat model but DO NOT add a trigger. The initial frame_texts_fts rows remain until a subsequent insert pattern overwrites — this is consistent with how SearchIndexSQLite handles deletions (it doesn't).

  Use the existing `engine` / `connection` fixture from `tests/unit/adapters/sqlite/conftest.py` and insert a parent `videos` row + `frames` row before testing the frame_texts repository.

  2. Extend `tests/unit/adapters/sqlite/test_schema.py`:
  - `test_videos_has_thumbnail_key_column` — PRAGMA table_info returns a row with name="thumbnail_key".
  - `test_videos_has_content_shape_column` — same for content_shape.
  - `test_frame_texts_table_exists` — sqlite_master query returns frame_texts.
  - `test_frame_texts_fts_exists` — sqlite_master query returns frame_texts_fts as a virtual table.
  - `test_init_db_is_idempotent_on_m008_columns` — call init_db twice, no error.
  </action>

  <acceptance_criteria>
    - `grep -q 'frame_texts = Table' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '"thumbnail_key"' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '"content_shape"' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'frame_texts_fts' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '_ensure_videos_visual_columns' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '_ensure_frame_texts_table' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'class FrameTextRepositorySQLite' src/vidscope/adapters/sqlite/frame_text_repository.py` exit 0
    - `grep -q 'FrameTextRepositorySQLite(self._connection)' src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `grep -q 'self.frame_texts:' src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `uv run python -c "from sqlalchemy import create_engine; from vidscope.adapters.sqlite.schema import init_db; e = create_engine('sqlite:///:memory:'); init_db(e); init_db(e); print('idempotent')"` prints `idempotent`
    - `uv run pytest tests/unit/adapters/sqlite/test_frame_text_repository.py -x -q` exit 0 (≥ 10 tests green)
    - `uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q` exit 0 (no regression + new M008 assertions)
    - `uv run pytest tests/unit/adapters/sqlite -q` exit 0 (no regression)
    - `uv run lint-imports` exit 0 (sqlite-never-imports-fs contract still green; vision contract green)
    - `uv run mypy src` exit 0
    <automated>uv run pytest tests/unit/adapters/sqlite -q</automated>
  </acceptance_criteria>
</task>

<task id="T05-pyproject-doctor-fixtures" type="auto">
  <name>T05: Add [vision] extra to pyproject + uv override + doctor check_vision + fixture JPGs generator</name>

  <read_first>
    - `pyproject.toml` (entire file, 191 lines) — specifically the `[project]`, `dependencies`, and `[dependency-groups]` sections. There is NO existing `[project.optional-dependencies]` section — we will create it.
    - `src/vidscope/infrastructure/startup.py` (entire file, 387 lines) — the `CheckResult` dataclass and existing `check_*` functions to mirror. See `check_ffmpeg` (lines 114-172), `check_ytdlp` (lines 175-206), and `check_cookies` (lines 209-263) for patterns.
    - `src/vidscope/cli/commands/doctor.py` (entire file, 48 lines) — the CLI renderer; it iterates over the list from `run_all_checks()`. No changes needed in doctor.py — just add check_vision() and include it in run_all_checks().
    - `.gsd/milestones/M008/M008-RESEARCH.md` §1.1 for the exact uv `override-dependencies` syntax and the opencv conflict explanation.
    - `tests/unit/infrastructure/test_startup.py` (if exists) — mirror pattern for new test.
  </read_first>

  <action>
  **Step A — Update `pyproject.toml`:**

  1. After the `dependencies = [...]` block (line 34), add:

  ```toml
  [project.optional-dependencies]
  vision = [
      "rapidocr-onnxruntime>=1.4.4,<2",
      "opencv-python-headless>=4.8,<5",
  ]
  ```

  2. After `[tool.hatch.build.targets.wheel]` block (around line 49) — or anywhere coherent in the file, add a new `[tool.uv]` section:

  ```toml
  # ---------------------------------------------------------------------------
  # uv
  # ---------------------------------------------------------------------------
  [tool.uv]
  # rapidocr-onnxruntime declares opencv-python as a hard dep, but
  # vidscope prefers opencv-python-headless (no Qt, smaller, server-
  # friendly). Force uv to treat opencv-python-headless as the
  # provider of the cv2 namespace. See M008 RESEARCH §1.1.
  override-dependencies = [
      "opencv-python-headless>=4.8,<5",
  ]
  ```

  **Step B — Add `check_vision` in `src/vidscope/infrastructure/startup.py`:**

  1. Add a new remediation constant near the top (after `_COOKIES_MISSING_REMEDIATION`):

  ```python
  _VISION_OPTIONAL_REMEDIATION: Final = (
      "Vision OCR + face-count are optional (M008). If you want to "
      "extract on-screen text and classify content shape, install the "
      "extra: `uv sync --extra vision`. Without it, the visual_intelligence "
      "pipeline stage emits SKIPPED and the rest of the pipeline is "
      "unaffected."
  )
  ```

  2. Add the check function after `check_analyzer`:

  ```python
  def check_vision() -> CheckResult:
      """Return a :class:`CheckResult` for the optional vision extra.

      States:

      1. **Both installed**: ``ok=True``, version_or_error reports both
         module versions.
      2. **Neither installed**: ``ok=True`` (optional), version_or_error
         says "not installed (optional)".
      3. **Partial install** (one present, other missing): ``ok=False``,
         names the missing package.

      The vision extra is optional — its absence is a healthy state.
      Only a BROKEN install (one half present, the other missing)
      warrants ``ok=False``.
      """
      from importlib.util import find_spec  # noqa: PLC0415

      has_rapidocr = find_spec("rapidocr_onnxruntime") is not None
      has_cv2 = find_spec("cv2") is not None

      if not has_rapidocr and not has_cv2:
          return CheckResult(
              name="vision",
              ok=True,
              version_or_error="not installed (optional)",
              remediation=_VISION_OPTIONAL_REMEDIATION,
          )
      if has_rapidocr and has_cv2:
          try:
              from importlib.metadata import version  # noqa: PLC0415
              rapidocr_v = version("rapidocr-onnxruntime")
          except Exception:  # noqa: BLE001
              rapidocr_v = "unknown"
          try:
              from importlib.metadata import version  # noqa: PLC0415
              cv2_v = version("opencv-python-headless")
          except Exception:  # noqa: BLE001
              cv2_v = "unknown"
          return CheckResult(
              name="vision",
              ok=True,
              version_or_error=(
                  f"rapidocr-onnxruntime={rapidocr_v}, "
                  f"opencv-python-headless={cv2_v}"
              ),
              remediation="",
          )
      # Partial install.
      missing = (
          "opencv-python-headless" if has_rapidocr else "rapidocr-onnxruntime"
      )
      return CheckResult(
          name="vision",
          ok=False,
          version_or_error=f"partial install: {missing} missing",
          remediation=_VISION_OPTIONAL_REMEDIATION,
      )
  ```

  3. Update `__all__` (lines 34-42) to include `"check_vision"`.

  4. Update `run_all_checks` (lines 374-386) to append `check_vision()`:

  ```python
  def run_all_checks() -> list[CheckResult]:
      return [
          check_ffmpeg(),
          check_ytdlp(),
          check_mcp_sdk(),
          check_cookies(),
          check_analyzer(),
          check_vision(),
      ]
  ```

  **Step C — Create fixtures generator `tests/fixtures/vision/generate_fixtures.py`:**

  This script generates synthetic JPGs using Pillow (already a transitive dep of rapidocr; but may not be installed in the dev env). We keep the generator simple — write it so tests can SKIP if Pillow is unavailable instead of failing.

  ```python
  """Generate synthetic JPG fixtures for M008 vision adapter tests.

  Run once from the repo root:

      uv run python tests/fixtures/vision/generate_fixtures.py

  Creates deterministic fixtures under tests/fixtures/vision/ that
  the unit tests consume. Re-running overwrites — safe.
  """

  from __future__ import annotations

  from pathlib import Path

  FIXTURE_DIR = Path(__file__).parent


  def _require_pil() -> None:
      try:
          import PIL  # noqa: F401, PLC0415
      except ImportError as exc:
          raise SystemExit(
              "Pillow is required to generate vision fixtures.\n"
              "Install with: uv add --dev Pillow"
          ) from exc


  def generate_text_jpg(path: Path, text: str, size: tuple[int, int] = (400, 100)) -> None:
      from PIL import Image, ImageDraw  # noqa: PLC0415

      img = Image.new("RGB", size, color="white")
      draw = ImageDraw.Draw(img)
      # Default font — deterministic bitmap rendering across platforms.
      draw.text((10, 40), text, fill="black")
      img.save(path, format="JPEG", quality=95)


  def generate_blank_jpg(path: Path, size: tuple[int, int] = (400, 100), color: str = "white") -> None:
      from PIL import Image  # noqa: PLC0415

      img = Image.new("RGB", size, color=color)
      img.save(path, format="JPEG", quality=95)


  def main() -> None:
      _require_pil()
      FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

      # OCR fixtures
      generate_text_jpg(FIXTURE_DIR / "text_present.jpg", "Link in bio: example.com")
      generate_text_jpg(FIXTURE_DIR / "text_fr.jpg", "Lien en bio : promo.fr")
      generate_blank_jpg(FIXTURE_DIR / "no_text.jpg")

      # Face fixtures — a blank is enough because we stub cascade in
      # unit tests. A real frontal-face JPG is only needed for the
      # (slow, excluded-by-default) integration tests shipped in S02.
      generate_blank_jpg(FIXTURE_DIR / "face_none.jpg")

      print(f"Generated fixtures in {FIXTURE_DIR}")


  if __name__ == "__main__":
      main()
  ```

  Also create:
  - `tests/fixtures/vision/__init__.py` — empty file (marker so pytest can discover).

  IMPORTANT: **do not commit the generated JPGs as binary files in this plan** — the fixture generator is the source of truth; tests that need them should call `pytest.importorskip("PIL")` and generate on-the-fly in `tmp_path` or via a conftest fixture. Our unit tests in T03 already operate via stubs (no real JPG content needed), so only a minimal `b"fake-jpg-file"` is written. Real JPG fixtures enter play in S02-P01 integration tests.

  **Step D — Add/extend `tests/unit/infrastructure/test_startup.py`:**

  Add a `TestCheckVision` class with:
  - `test_check_vision_both_missing` — when both find_spec return None (via monkeypatch), ok=True, version_or_error contains "not installed".
  - `test_check_vision_both_present` — monkeypatch find_spec to always return a truthy stub, ok=True, version_or_error references both package names.
  - `test_check_vision_partial_install` — monkeypatch only rapidocr to exist, ok=False, version_or_error names opencv-python-headless.
  - `test_run_all_checks_includes_vision` — `{r.name for r in run_all_checks()}` includes `"vision"`.

  Use `monkeypatch.setattr("importlib.util.find_spec", lambda name: ...)` to simulate each state.
  </action>

  <acceptance_criteria>
    - `grep -q 'optional-dependencies' pyproject.toml` exit 0
    - `grep -q 'rapidocr-onnxruntime' pyproject.toml` exit 0
    - `grep -q 'opencv-python-headless' pyproject.toml` exit 0
    - `grep -q 'override-dependencies' pyproject.toml` exit 0
    - `grep -q 'def check_vision' src/vidscope/infrastructure/startup.py` exit 0
    - `grep -q 'check_vision()' src/vidscope/infrastructure/startup.py` exit 0
    - `uv run python -c "from vidscope.infrastructure.startup import check_vision, run_all_checks; r = check_vision(); print(r.name, r.ok); assert r.name == 'vision'"` prints `vision <True|False>`
    - `uv run python -c "from vidscope.infrastructure.startup import run_all_checks; names = [r.name for r in run_all_checks()]; assert 'vision' in names, names; print('ok')"` prints `ok`
    - `uv run vidscope doctor` prints a table containing a `vision` row (exit code 0 or 2 depending on install state — both acceptable)
    - `test -f tests/fixtures/vision/__init__.py`
    - `test -f tests/fixtures/vision/generate_fixtures.py`
    - `uv run pytest tests/unit/infrastructure/test_startup.py -x -q` exit 0
    - `uv run mypy src` exit 0
    <automated>uv run pytest tests/unit/infrastructure/test_startup.py -q && uv run python -c "from vidscope.infrastructure.startup import run_all_checks; assert 'vision' in [r.name for r in run_all_checks()]"</automated>
  </acceptance_criteria>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ONNX model download → local FS | RapidOCR downloads the ~50MB model from ModelScope CDN on first call; untrusted bytes land on disk |
| Frame JPGs → RapidOCR / OpenCV | User-ingested frames (from yt-dlp) are fed to native C++ libraries (ONNX runtime, OpenCV image decoders); malformed input could trigger parser bugs |
| FTS5 virtual table ← frame_texts | OCR output (untrusted text from arbitrary videos) is inserted into an FTS5 index queried later via MATCH |
| Protocol boundary adapter→port | Adapter modules in `vidscope.adapters.vision` must never reach into other adapters (enforced by import-linter) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-M008-S01-01 | **Tampering (T)** | ONNX model file downloaded from ModelScope CDN on first `RapidOCR()` call | accept | The model download happens inside `rapidocr-onnxruntime` library code; vidscope has no control over integrity. Mitigations deferred to M011+: (a) model pinning via local cache directory, (b) optional checksum verification. For M008 we accept because the library is widely used and the alternative (hand-rolling ONNX download) is strictly worse. Documented in M008-RESEARCH §8.1. |
| T-M008-S01-02 | **Denial of Service (D)** | RapidOCR processing an adversarially crafted JPG (extreme size, malformed EXIF) | mitigate | `RapidOcrEngine.extract_text` wraps `engine(image_path)` in `try/except Exception: return []`. A parser crash in ONNX or OpenCV becomes an empty result, not a pipeline-killing exception. Same for `HaarcascadeFaceCounter.count_faces`. Upstream frame size is already bounded by ffmpeg extractor (M001/S04 caps to 30 frames per video). |
| T-M008-S01-03 | **Denial of Service (D)** | FTS5 query with malformed MATCH syntax crashing `find_video_ids_by_text` | mitigate | `FrameTextRepositorySQLite.find_video_ids_by_text` wraps `conn.execute(text(...))` in `try/except SQLAlchemyError` and re-raises as `StorageError` with the query string escaped in the message. No crash propagates beyond the UoW boundary. |
| T-M008-S01-04 | **Information Disclosure (I)** | OCR text persisted in `frame_texts` may include sensitive PII captured in screen overlays (email addresses, phone numbers) | accept | The project is a single-user local tool (R032 — out of scope: multi-user). No network surface, no export path, no telemetry. The user is the sole data owner. PII captured by OCR mirrors PII already visible in the ingested video — ingesting a video with PII on-screen is a decision the user made explicitly via `vidscope add`. Documented in M008-RESEARCH §5 implicit in the "single-user local" principle. |
| T-M008-S01-05 | **Information Disclosure (I)** | Log output from adapter `_logger.warning(...)` could leak image paths or partial OCR content | mitigate | Logging is `logging.getLogger(__name__)` with INFO for "library missing" (benign), WARNING for library crashes with image path + exception message only (no OCR content). Never log the extracted text itself. Enforced by code review in T03 action — executor must not add `_logger.*(text)` calls. |
| T-M008-S01-06 | **Tampering (T)** | `frame_texts_fts` not synchronised on DELETE (cascade from videos/frames removes parent but not FTS5 rows) | accept | Documented orphan: the FTS5 index may hold entries for deleted videos. The risk is that `find_video_ids_by_text` returns a video_id that no longer exists, which callers must resolve through `videos.get()` returning None. This mirrors the same gap in `SearchIndexSQLite` (M001/S01) and is consistent. A future milestone may add a cleanup pass or triggers. |
| T-M008-S01-07 | **Elevation of Privilege (E)** | Python package `rapidocr-onnxruntime` is installed into the same venv as vidscope; malicious package on PyPI could execute arbitrary code | accept | Standard supply-chain risk of any Python dep. Mitigation: `uv sync --extra vision` installs from PyPI with SHA-256 verification via uv's lockfile (when `uv lock` is committed). The project does not lock currently — this is an M011 operability concern. For M008 we accept; installing optional extras is an opt-in action. |
| T-M008-S01-08 | **Spoofing (S)** | Import-linter contract bypassed by a rogue adapter import | mitigate | `vision-adapter-is-self-contained` added to `.importlinter` forbids `vidscope.adapters.vision` from importing any other adapter/infrastructure/application/pipeline/cli/mcp module. `uv run lint-imports` is part of the quality gates and runs in CI (plus as part of each task's acceptance criteria). |

</threat_model>

<verification>
Commands that prove S01-P01 completion (ordered most-specific → broad):

```bash
# Class-level tests
uv run pytest tests/unit/domain/test_entities.py::TestFrameText -x -q
uv run pytest tests/unit/domain/test_values.py::TestContentShape -x -q
uv run pytest tests/unit/ports/test_ocr_engine.py -x -q
uv run pytest tests/unit/adapters/vision -x -q
uv run pytest tests/unit/adapters/sqlite/test_frame_text_repository.py -x -q
uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q
uv run pytest tests/unit/infrastructure/test_startup.py -x -q

# StageName integrity (exactly 7 members in canonical order)
uv run python -c "from vidscope.domain import StageName; assert [s.value for s in StageName] == ['ingest','transcribe','frames','analyze','visual_intelligence','metadata_extract','index']"

# ContentShape exhaustiveness
uv run python -c "from vidscope.domain import ContentShape; assert {s.value for s in ContentShape} == {'talking_head','broll','mixed','unknown'}"

# FrameText + ports importability
uv run python -c "from vidscope.domain import FrameText; from vidscope.ports import OcrEngine, FaceCounter, OcrLine, FrameTextRepository; print('ok')"

# Adapter smoke (library-absent path is the default in dev env)
uv run python -c "from vidscope.adapters.vision import RapidOcrEngine, HaarcascadeFaceCounter; e = RapidOcrEngine(); c = HaarcascadeFaceCounter(); assert e.extract_text('/no/such/file.jpg') == []; assert c.count_faces('/no/such/file.jpg') == 0; print('ok')"

# Schema idempotence
uv run python -c "from sqlalchemy import create_engine; from vidscope.adapters.sqlite.schema import init_db; e = create_engine('sqlite:///:memory:'); init_db(e); init_db(e); print('ok')"

# Doctor surface
uv run vidscope doctor | grep -q vision

# Full suite (no regression)
uv run pytest -q

# 4 quality gates
uv run ruff check src tests
uv run mypy src
uv run lint-imports
uv run pytest -q
```

Import-linter: 10 contracts expected green (9 prior + new `vision-adapter-is-self-contained`).
</verification>

<success_criteria>
- All 5 tasks green (acceptance criteria pass on every task).
- `uv run pytest -q` exits 0 with ≥ 40 new tests added (domain + ports + vision adapter + sqlite + startup + schema) and zero regressions on the 735+ existing tests.
- `uv run lint-imports` reports 10 contracts green (includes new `vision-adapter-is-self-contained`).
- `uv run mypy src` exits 0 with no new type errors.
- `uv run ruff check src tests` exits 0.
- `uv run vidscope doctor` prints a table containing a row `vision` (ok or fail — both acceptable since the extra is optional at dev time).
- `pyproject.toml` declares `[project.optional-dependencies] vision = [...]` + `[tool.uv] override-dependencies = [...]`.
- S02-P01 (next plan) can `from vidscope.adapters.vision import RapidOcrEngine, HaarcascadeFaceCounter` and `from vidscope.ports import OcrEngine, FaceCounter, FrameTextRepository` without any further changes to the ports/adapter layers.
</success_criteria>

<output>
After completion, create `.gsd/milestones/M008/slices/S01/S01-P01-SUMMARY.md` following the standard summary template.
</output>
