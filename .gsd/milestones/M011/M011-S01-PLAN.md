---
phase: M011
plan: S01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/vidscope/domain/values.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/video_tracking_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/application/set_video_tracking.py
  - src/vidscope/cli/commands/review.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/domain/test_video_tracking.py
  - tests/unit/adapters/sqlite/test_video_tracking_repository.py
  - tests/unit/application/test_set_video_tracking.py
  - tests/unit/application/test_pipeline_neutrality.py
  - tests/unit/cli/test_review_cmd.py
autonomous: true
requirements: [R056]
must_haves:
  truths:
    - "`TrackingStatus` StrEnum existe dans `vidscope.domain.values` avec EXACTEMENT 6 membres: NEW='new', REVIEWED='reviewed', SAVED='saved', ACTIONED='actioned', IGNORED='ignored', ARCHIVED='archived'"
    - "`VideoTracking` entity frozen+slots existe dans `vidscope.domain.entities` avec champs: video_id (VideoId), status (TrackingStatus), starred (bool=False), notes (str|None=None), id (int|None=None), created_at (datetime|None=None), updated_at (datetime|None=None)"
    - "Le domain reste pur: `vidscope.domain` n'importe aucun third-party (contrat `domain-is-pure` toujours KEPT)"
    - "Port `VideoTrackingRepository` Protocol @runtime_checkable dans `vidscope.ports.repositories` expose: `upsert(tracking)`, `get_for_video(video_id)`, `list_by_status(status, *, limit=1000)`, `list_starred(*, limit=1000)`"
    - "`UnitOfWork` Protocol dans `vidscope.ports.unit_of_work` déclare `video_tracking: VideoTrackingRepository`"
    - "`init_db(engine)` appelle `_ensure_video_tracking_table(conn)` qui crée la table `video_tracking` si absente (idempotent, vérifie via `sqlite_master`)"
    - "Table `video_tracking` contient: id PK, video_id FK videos ON DELETE CASCADE NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'new', starred BOOLEAN NOT NULL DEFAULT 0, notes TEXT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, UNIQUE(video_id), index sur (status) et (starred)"
    - "`VideoTrackingRepositorySQLite.upsert(tracking)` utilise `ON CONFLICT(video_id) DO UPDATE SET status=excluded.status, starred=excluded.starred, notes=excluded.notes, updated_at=excluded.updated_at` — 2e appel sur le même video_id n'émet aucune IntegrityError"
    - "`SqliteUnitOfWork.__enter__` instancie `self.video_tracking = VideoTrackingRepositorySQLite(self._connection)`"
    - "`SetVideoTrackingUseCase` accepte video_id+status+starred?+notes? et délègue à `uow.video_tracking.upsert()` — accepte `notes=None` (preserve existing) distinct de `notes=''` (clear)"
    - "CLI `vidscope review <video_id> --status {new|reviewed|saved|actioned|ignored|archived} [--star] [--unstar] [--note TEXT] [--clear-note]` existe et imprime confirmation sur succès"
    - "Re-ingest d'une vidéo existante (upsert_by_platform_id) NE TOUCHE PAS à la ligne video_tracking associée — pipeline neutrality garantie"
    - "Les 10 contrats import-linter existants restent KEPT après ajout des nouveaux fichiers"
  artifacts:
    - path: "src/vidscope/domain/values.py"
      provides: "TrackingStatus StrEnum"
      contains: "class TrackingStatus"
    - path: "src/vidscope/domain/entities.py"
      provides: "VideoTracking frozen dataclass"
      contains: "class VideoTracking"
    - path: "src/vidscope/ports/repositories.py"
      provides: "VideoTrackingRepository Protocol"
      contains: "class VideoTrackingRepository"
    - path: "src/vidscope/adapters/sqlite/schema.py"
      provides: "_ensure_video_tracking_table + appel dans init_db"
      contains: "_ensure_video_tracking_table"
    - path: "src/vidscope/adapters/sqlite/video_tracking_repository.py"
      provides: "VideoTrackingRepositorySQLite adapter"
      contains: "class VideoTrackingRepositorySQLite"
    - path: "src/vidscope/application/set_video_tracking.py"
      provides: "SetVideoTrackingUseCase"
      contains: "class SetVideoTrackingUseCase"
    - path: "src/vidscope/cli/commands/review.py"
      provides: "vidscope review CLI command"
      contains: "review_command"
  key_links:
    - from: "src/vidscope/adapters/sqlite/schema.py"
      to: "_ensure_video_tracking_table"
      via: "Appel depuis init_db() (après _ensure_analysis_v2_columns)"
      pattern: "_ensure_video_tracking_table\\(conn\\)"
    - from: "src/vidscope/adapters/sqlite/unit_of_work.py"
      to: "VideoTrackingRepositorySQLite"
      via: "Instanciation dans __enter__ + slot dans __init__"
      pattern: "VideoTrackingRepositorySQLite\\(self\\._connection\\)"
    - from: "src/vidscope/ports/unit_of_work.py"
      to: "VideoTrackingRepository"
      via: "Attribut Protocol UnitOfWork.video_tracking"
      pattern: "video_tracking: VideoTrackingRepository"
    - from: "src/vidscope/cli/app.py"
      to: "review_command"
      via: "Import + registration via app.command('review')(review_command)"
      pattern: "app.command\\(\"review\"\\)"
    - from: "src/vidscope/application/set_video_tracking.py"
      to: "VideoTrackingRepository"
      via: "Appel uow.video_tracking.upsert() via UoW factory"
      pattern: "uow\\.video_tracking\\.upsert"
---

<objective>
S01 livre le socle M011 : value object `TrackingStatus` (6 membres), entité domain `VideoTracking` (frozen+slots, workflow overlay), port `VideoTrackingRepository`, migration SQLite additive de la table `video_tracking` (UNIQUE sur video_id, FK CASCADE, indexes status/starred), adapter SQLite avec upsert `ON CONFLICT`, extension de `UnitOfWork`, use case `SetVideoTrackingUseCase`, sous-commande CLI `vidscope review`, et tests de pipeline neutrality.

Purpose: Sans ce socle, S02 (tags+collections) et S03 (facet search sur --status/--starred) ne peuvent rien écrire ni filtrer. La table `videos` reste IMMUTABLE — aucun champ workflow n'est ajouté à `videos`, tout va dans `video_tracking` (D033 du ROADMAP). La pipeline neutrality est critique: re-ingest d'une vidéo existante ne doit jamais wiper les annotations utilisateur.
Output: Domain étendu + port + adapter SQLite + UoW étendu + use case + CLI `review` + 4 suites de tests (domain, adapter, use case, neutrality, CLI).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M011/M011-ROADMAP.md
@.gsd/milestones/M011/M011-RESEARCH.md
@.gsd/milestones/M011/M011-VALIDATION.md
@.gsd/REQUIREMENTS.md
@src/vidscope/domain/values.py
@src/vidscope/domain/entities.py
@src/vidscope/domain/__init__.py
@src/vidscope/ports/repositories.py
@src/vidscope/ports/unit_of_work.py
@src/vidscope/ports/__init__.py
@src/vidscope/adapters/sqlite/schema.py
@src/vidscope/adapters/sqlite/unit_of_work.py
@src/vidscope/adapters/sqlite/video_stats_repository.py
@src/vidscope/cli/commands/watch.py
@src/vidscope/cli/app.py
@.importlinter

<interfaces>
Patterns et signatures existants DÉJÀ VÉRIFIÉS dans le codebase :

**StrEnum pattern (domain/values.py)** :
```python
from enum import StrEnum

class ContentType(StrEnum):
    TUTORIAL = "tutorial"
    ...
    UNKNOWN = "unknown"
```

**Frozen+slots dataclass pattern (domain/entities.py — VideoStats M009)** :
```python
@dataclass(frozen=True, slots=True)
class VideoStats:
    video_id: VideoId
    captured_at: datetime
    view_count: int | None = None
    ...
    id: int | None = None
    created_at: datetime | None = None
```

**Migration additive idempotente (schema.py — M009/M010)** :
```python
def _ensure_video_stats_table(conn: Connection) -> None:
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "video_stats" in existing:
        return
    conn.execute(text("""CREATE TABLE video_stats (...) """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ..."))

def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
        _ensure_analysis_v2_columns(conn)
        # M011: à ajouter
```

**Port Protocol pattern (ports/repositories.py — VideoStatsRepository)** :
```python
@runtime_checkable
class VideoStatsRepository(Protocol):
    def append(self, stats: VideoStats) -> VideoStats: ...
    def latest_for_video(self, video_id: VideoId) -> VideoStats | None: ...
```

**Upsert SQLite ON CONFLICT pattern (video_stats_repository.py)** :
```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = (
    sqlite_insert(video_stats_table)
    .values(**payload)
    .on_conflict_do_nothing(index_elements=["video_id", "captured_at"])
)
self._conn.execute(stmt)
```

Pour M011 upsert (DO UPDATE au lieu de DO NOTHING) :
```python
stmt = sqlite_insert(video_tracking_table).values(**payload)
stmt = stmt.on_conflict_do_update(
    index_elements=["video_id"],
    set_={
        "status": stmt.excluded.status,
        "starred": stmt.excluded.starred,
        "notes": stmt.excluded.notes,
        "updated_at": stmt.excluded.updated_at,
    },
)
```

**UoW Protocol pattern (ports/unit_of_work.py)** :
```python
@runtime_checkable
class UnitOfWork(Protocol):
    videos: VideoRepository
    transcripts: TranscriptRepository
    ...
    video_stats: VideoStatsRepository
    # M011 add: video_tracking, tags, collections
```

**UoW concrete pattern (adapters/sqlite/unit_of_work.py.__enter__)** :
```python
def __enter__(self) -> SqliteUnitOfWork:
    self._connection = self._engine.connect()
    self._transaction = self._connection.begin()
    self.videos = VideoRepositorySQLite(self._connection)
    ...
    self.video_stats = VideoStatsRepositorySQLite(self._connection)
    # M011 add: self.video_tracking = VideoTrackingRepositorySQLite(...)
    return self
```

**CLI sub-command pattern (cli/commands/watch.py)** :
```python
import typer
from vidscope.cli._support import (
    acquire_container, console, fail_user, handle_domain_errors,
)

watch_app = typer.Typer(name="watch", help="...", no_args_is_help=True, add_completion=False)

@watch_app.command("add")
def add(url: str = typer.Argument(...)) -> None:
    with handle_domain_errors():
        container = acquire_container()
        use_case = AddWatchedAccountUseCase(...)
        result = use_case.execute(url)
```

**CLI single-command pattern (cli/commands/search.py — pour review qui n'est PAS un sub-app)** :
Approche alternative acceptée: `review_command` est une fonction unique enregistrée via `app.command("review")(review_command)` dans `cli/app.py`. Signature avec `Annotated[...]` par KNOWLEDGE.md.

**Enregistrement dans cli/app.py** :
```python
app.command("review", help="...")(review_command)
```

**Use case pattern (application/refresh_stats.py ou similaire)** :
Use case accepte `unit_of_work_factory` dans __init__, expose `.execute(...)` method, retourne dataclass frozen+slots pour le résultat, n'importe AUCUN adapter (`application-has-no-adapters` contract).

**Test fixture engine (tests/unit/adapters/sqlite/conftest.py)** — fournit un `engine` SQLAlchemy fraîchement `init_db()`-isé pour chaque test.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: TrackingStatus + VideoTracking entity + port VideoTrackingRepository + UoW Protocol</name>
  <files>src/vidscope/domain/values.py, src/vidscope/domain/entities.py, src/vidscope/domain/__init__.py, src/vidscope/ports/repositories.py, src/vidscope/ports/unit_of_work.py, src/vidscope/ports/__init__.py, tests/unit/domain/test_video_tracking.py</files>
  <read_first>
    - src/vidscope/domain/values.py (pattern StrEnum `ContentType`, `Platform`, `Language` avec `__all__` — placement et style docstring)
    - src/vidscope/domain/entities.py (pattern `VideoStats` frozen+slots en lignes 231-255 — ordre des champs, defaults, `id`/`created_at` en fin)
    - src/vidscope/domain/__init__.py (re-exports entities + values dans le `__all__` groupé par concern)
    - src/vidscope/ports/repositories.py (pattern `VideoStatsRepository` lignes 315-393 — Protocol @runtime_checkable, docstrings, limit par défaut)
    - src/vidscope/ports/unit_of_work.py (Protocol UnitOfWork lignes 52-80 — comment déclarer un nouvel attribut)
    - src/vidscope/ports/__init__.py (re-exports + __all__)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 10 S01 — "status ENUM {new, reviewed, saved, actioned, ignored, archived}, starred bool, notes TEXT")
    - .gsd/milestones/M011/M011-RESEARCH.md (Pattern 1-3 + D1 upsert semantics + D2 state machine non-enforced)
  </read_first>
  <behavior>
    - Test 1: `TrackingStatus` est un `StrEnum` avec EXACTEMENT 6 membres: `NEW="new"`, `REVIEWED="reviewed"`, `SAVED="saved"`, `ACTIONED="actioned"`, `IGNORED="ignored"`, `ARCHIVED="archived"`. `{s.value for s in TrackingStatus} == {"new", "reviewed", "saved", "actioned", "ignored", "archived"}`.
    - Test 2: `TrackingStatus("new") is TrackingStatus.NEW` et `str(TrackingStatus.NEW) == "new"`.
    - Test 3: `TrackingStatus("bogus")` lève `ValueError`.
    - Test 4: `VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)` construit un objet valide (tous les autres champs ont des defaults).
    - Test 5: `VideoTracking` a exactement ces champs avec ces defaults: `video_id: VideoId`, `status: TrackingStatus`, `starred: bool = False`, `notes: str | None = None`, `id: int | None = None`, `created_at: datetime | None = None`, `updated_at: datetime | None = None`. Ordre: champs sans default, puis champs avec default.
    - Test 6: `VideoTracking` est `frozen=True, slots=True` — assignation post-construction lève `FrozenInstanceError`, `hasattr(vt, '__dict__')` est False.
    - Test 7: `VideoTracking(...)` accepte et retient explicitement `starred=True`, `notes="my note"`.
    - Test 8: Les imports fonctionnent: `from vidscope.domain import TrackingStatus, VideoTracking` sans erreur.
    - Test 9: `VideoTrackingRepository` est un `Protocol` `@runtime_checkable` dans `vidscope.ports.repositories` et est re-exporté depuis `vidscope.ports`.
    - Test 10: `UnitOfWork` Protocol dans `vidscope.ports.unit_of_work` déclare `video_tracking: VideoTrackingRepository` (attribut annotation).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/domain/values.py` (per D-01 du ROADMAP M011 ligne 10, per Pattern 2 RESEARCH).

(a) Ajouter AVANT la ligne `class Language(StrEnum)` existante (pour regrouper avec ContentType/SentimentLabel) :

```python
class TrackingStatus(StrEnum):
    """User-assigned workflow status for a single video (M011).

    Stored in the ``video_tracking`` table (separate from the immutable
    ``videos`` table per D033). Typical user flow:

        new -> reviewed -> saved|actioned|ignored -> archived

    No state machine is enforced — any transition is legal (D2 of M011
    RESEARCH, R032 single-user tool). The status is a label, not a gate.
    """

    NEW = "new"
    REVIEWED = "reviewed"
    SAVED = "saved"
    ACTIONED = "actioned"
    IGNORED = "ignored"
    ARCHIVED = "archived"
```

(b) Mettre à jour le `__all__` du module : ajouter `"TrackingStatus"` trié alphabétiquement entre `"StageName"` et `"VideoId"`. Le tuple final devient :
```python
__all__ = [
    "ContentType",
    "Language",
    "Platform",
    "PlatformId",
    "RunStatus",
    "SentimentLabel",
    "StageName",
    "TrackingStatus",
    "VideoId",
]
```

Étape 2 — Étendre `src/vidscope/domain/entities.py` (per Pattern 1 RESEARCH).

(a) Mettre à jour l'import depuis `vidscope.domain.values` en haut du fichier pour inclure `TrackingStatus` :
```python
from vidscope.domain.values import (
    ContentType,
    Language,
    Platform,
    PlatformId,
    RunStatus,
    SentimentLabel,
    StageName,
    TrackingStatus,
    VideoId,
)
```

(b) Ajouter la classe `VideoTracking` à la fin du fichier (après `VideoStats`). Ordre des champs: non-default puis default, `id`/`created_at`/`updated_at` en FIN (pattern VideoStats) :

```python
@dataclass(frozen=True, slots=True)
class VideoTracking:
    """User workflow overlay for a single video (M011/R056).

    One row per video — UNIQUE on ``video_id``. The table is independent
    of ``videos`` (D033 immutable videos). Re-ingesting a video leaves
    the ``video_tracking`` row untouched — that's the pipeline neutrality
    invariant.

    Fields
    ------
    video_id:
        FK to ``videos.id`` with ON DELETE CASCADE.
    status:
        Current workflow label. Typical flow: new -> reviewed ->
        saved|actioned|ignored -> archived. Any transition is legal.
    starred:
        Independent of ``status`` — user may star any row.
    notes:
        Free-text note. ``None`` means "no note set" (distinct from
        ``""`` which means "note was explicitly cleared").
    """

    video_id: VideoId
    status: TrackingStatus
    starred: bool = False
    notes: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

(c) Ajouter `"VideoTracking"` au `__all__` du module (tri alphabétique, dans la liste des entities entre `"VideoStats"` et `"WatchRefresh"`) :
```python
__all__ = [
    "Analysis",
    "Frame",
    "PipelineRun",
    "Transcript",
    "TranscriptSegment",
    "Video",
    "VideoStats",
    "VideoTracking",
    "WatchRefresh",
    "WatchedAccount",
]
```

Étape 3 — Étendre `src/vidscope/domain/__init__.py` pour re-exporter :

(a) Ajouter `VideoTracking` dans l'import depuis `entities` et `TrackingStatus` dans l'import depuis `values` :
```python
from vidscope.domain.entities import (
    Analysis,
    Frame,
    PipelineRun,
    Transcript,
    TranscriptSegment,
    Video,
    VideoStats,
    VideoTracking,
    WatchedAccount,
    WatchRefresh,
)

from vidscope.domain.values import (
    ContentType,
    Language,
    Platform,
    PlatformId,
    RunStatus,
    SentimentLabel,
    StageName,
    TrackingStatus,
    VideoId,
)
```

(b) Dans `__all__`, ajouter `"VideoTracking"` dans la section `# entities` (après `"VideoStats"`) et `"TrackingStatus"` dans la section `# values` (entre `"StageName"` et `"VideoId"`). Conserver les autres sections intactes.

Étape 4 — Ajouter le Protocol `VideoTrackingRepository` dans `src/vidscope/ports/repositories.py` (per Pattern 3 RESEARCH).

(a) Mettre à jour l'import depuis `vidscope.domain` en haut du fichier pour inclure `TrackingStatus` et `VideoTracking` :
```python
from vidscope.domain import (
    Analysis,
    ContentType,
    Frame,
    PipelineRun,
    Platform,
    PlatformId,
    RunStatus,
    StageName,
    TrackingStatus,
    Transcript,
    Video,
    VideoId,
    VideoStats,
    VideoTracking,
    WatchedAccount,
    WatchRefresh,
)
```

(b) Ajouter `"VideoTrackingRepository"` à `__all__` (tri alphabétique, après `"VideoStatsRepository"`) :
```python
__all__ = [
    "AnalysisRepository",
    "FrameRepository",
    "PipelineRunRepository",
    "TranscriptRepository",
    "VideoRepository",
    "VideoStatsRepository",
    "VideoTrackingRepository",
    "WatchAccountRepository",
    "WatchRefreshRepository",
]
```

(c) Ajouter la classe Protocol à la FIN du fichier (après `VideoStatsRepository`) :

```python
@runtime_checkable
class VideoTrackingRepository(Protocol):
    """Persistence for :class:`VideoTracking` rows (M011/R056).

    One row per video — UNIQUE on ``video_id``. ``upsert`` is the only
    write method: creating and updating share the same signature, so
    callers don't need to decide between INSERT/UPDATE (D1 M011 RESEARCH).
    """

    def upsert(self, tracking: VideoTracking) -> VideoTracking:
        """Insert or update the tracking row for ``tracking.video_id``.

        Uses ``ON CONFLICT(video_id) DO UPDATE`` so a second call for the
        same ``video_id`` atomically replaces ``status``, ``starred``,
        ``notes``, and ``updated_at``. Returns the persisted entity with
        ``id``, ``created_at``, ``updated_at`` populated.
        """
        ...

    def get_for_video(self, video_id: VideoId) -> VideoTracking | None:
        """Return the tracking row for ``video_id`` or ``None`` if absent.

        Sparse table semantics: absence means "no user workflow yet",
        not "implicit new status".
        """
        ...

    def list_by_status(
        self, status: TrackingStatus, *, limit: int = 1000
    ) -> list[VideoTracking]:
        """Return every tracking row whose ``status`` equals ``status``.

        Ordered by ``updated_at DESC`` (most recent first). Capped at
        ``limit`` (default 1000) to avoid unbounded scans.
        """
        ...

    def list_starred(self, *, limit: int = 1000) -> list[VideoTracking]:
        """Return every tracking row with ``starred=True``.

        Ordered by ``updated_at DESC``. Capped at ``limit`` (default 1000).
        """
        ...
```

Étape 5 — Étendre `src/vidscope/ports/unit_of_work.py` pour ajouter `video_tracking` (per Pattern 5 RESEARCH) :

(a) Dans l'import depuis `vidscope.ports.repositories`, ajouter `VideoTrackingRepository` :
```python
from vidscope.ports.repositories import (
    AnalysisRepository,
    FrameRepository,
    PipelineRunRepository,
    TranscriptRepository,
    VideoRepository,
    VideoStatsRepository,
    VideoTrackingRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)
```

(b) Dans la classe `UnitOfWork` Protocol, ajouter APRÈS la ligne `video_stats: VideoStatsRepository` :
```python
    video_tracking: VideoTrackingRepository
```

Étape 6 — Étendre `src/vidscope/ports/__init__.py` pour re-exporter le nouveau Protocol :

(a) Dans l'import depuis `vidscope.ports.repositories`, ajouter `VideoTrackingRepository` (ordre alphabétique).

(b) Dans `__all__`, ajouter `"VideoTrackingRepository"` entre `"VideoStatsRepository"` et `"WatchAccountRepository"` (tri alphabétique).

Étape 7 — Créer `tests/unit/domain/test_video_tracking.py` :

```python
"""Unit tests for TrackingStatus enum + VideoTracking domain entity (M011/S01/R056)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from vidscope.domain import (
    TrackingStatus,
    VideoId,
    VideoTracking,
)


class TestTrackingStatusEnum:
    def test_has_exactly_six_members(self) -> None:
        assert {s.value for s in TrackingStatus} == {
            "new", "reviewed", "saved", "actioned", "ignored", "archived",
        }

    def test_construction_from_string(self) -> None:
        assert TrackingStatus("new") is TrackingStatus.NEW
        assert TrackingStatus("reviewed") is TrackingStatus.REVIEWED
        assert TrackingStatus("saved") is TrackingStatus.SAVED
        assert TrackingStatus("actioned") is TrackingStatus.ACTIONED
        assert TrackingStatus("ignored") is TrackingStatus.IGNORED
        assert TrackingStatus("archived") is TrackingStatus.ARCHIVED

    def test_strenum_semantics(self) -> None:
        assert str(TrackingStatus.NEW) == "new"
        assert TrackingStatus.NEW == "new"

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            TrackingStatus("bogus")


class TestVideoTrackingEntity:
    def test_minimal_construction(self) -> None:
        vt = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        assert vt.video_id == VideoId(1)
        assert vt.status is TrackingStatus.NEW
        assert vt.starred is False
        assert vt.notes is None
        assert vt.id is None
        assert vt.created_at is None
        assert vt.updated_at is None

    def test_full_construction(self) -> None:
        now = datetime.now(UTC)
        vt = VideoTracking(
            video_id=VideoId(42),
            status=TrackingStatus.SAVED,
            starred=True,
            notes="look at the hook",
            id=7,
            created_at=now,
            updated_at=now,
        )
        assert vt.starred is True
        assert vt.notes == "look at the hook"
        assert vt.id == 7
        assert vt.created_at == now

    def test_frozen_prevents_mutation(self) -> None:
        vt = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        with pytest.raises(dataclasses.FrozenInstanceError):
            vt.status = TrackingStatus.SAVED  # type: ignore[misc]

    def test_slots_prevents_new_attributes(self) -> None:
        vt = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        assert not hasattr(vt, "__dict__")
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            vt.bogus = "x"  # type: ignore[attr-defined]

    def test_notes_none_vs_empty_string_distinct(self) -> None:
        unset = VideoTracking(video_id=VideoId(1), status=TrackingStatus.NEW)
        cleared = VideoTracking(
            video_id=VideoId(1), status=TrackingStatus.NEW, notes="",
        )
        assert unset.notes is None
        assert cleared.notes == ""
        assert unset.notes != cleared.notes


class TestPortReExports:
    """Ensure VideoTrackingRepository + UoW attr are wired."""

    def test_port_repository_importable(self) -> None:
        from vidscope.ports import VideoTrackingRepository

        assert VideoTrackingRepository is not None

    def test_uow_protocol_declares_video_tracking(self) -> None:
        from vidscope.ports import UnitOfWork

        # Protocol annotations are readable via __annotations__
        anns = UnitOfWork.__annotations__
        assert "video_tracking" in anns

    def test_video_tracking_repository_is_runtime_checkable(self) -> None:
        from typing import get_origin

        from vidscope.ports import VideoTrackingRepository

        # @runtime_checkable Protocols have _is_runtime_protocol True
        assert getattr(VideoTrackingRepository, "_is_runtime_protocol", False) is True
```

Étape 8 — Exécuter :
```
uv run pytest tests/unit/domain/test_video_tracking.py -x -q
uv run lint-imports
```

NE PAS importer sqlalchemy / typer / rich depuis `vidscope.domain.*` ou `vidscope.ports.*` (contrats `domain-is-pure`, `ports-are-pure`). NE PAS ajouter `VideoTracking` à la table `videos` — la table `videos` reste IMMUTABLE (D033).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/domain/test_video_tracking.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class TrackingStatus" src/vidscope/domain/values.py` matches
    - `grep -nE 'NEW = "new"' src/vidscope/domain/values.py` matches
    - `grep -nE 'ARCHIVED = "archived"' src/vidscope/domain/values.py` matches
    - `grep -n '"TrackingStatus"' src/vidscope/domain/values.py` matches (in __all__)
    - `grep -n "class VideoTracking" src/vidscope/domain/entities.py` matches
    - `grep -n "status: TrackingStatus" src/vidscope/domain/entities.py` matches
    - `grep -n "starred: bool = False" src/vidscope/domain/entities.py` matches
    - `grep -n "notes: str | None = None" src/vidscope/domain/entities.py` matches
    - `grep -n "updated_at: datetime | None = None" src/vidscope/domain/entities.py` matches
    - `grep -n '"VideoTracking"' src/vidscope/domain/__init__.py` matches
    - `grep -n '"TrackingStatus"' src/vidscope/domain/__init__.py` matches
    - `grep -n "class VideoTrackingRepository" src/vidscope/ports/repositories.py` matches
    - `grep -n "@runtime_checkable" src/vidscope/ports/repositories.py` returns multiple matches (including near VideoTrackingRepository)
    - `grep -n "video_tracking: VideoTrackingRepository" src/vidscope/ports/unit_of_work.py` matches
    - `grep -n '"VideoTrackingRepository"' src/vidscope/ports/__init__.py` matches
    - `uv run pytest tests/unit/domain/test_video_tracking.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (domain-is-pure + ports-are-pure toujours KEPT)
  </acceptance_criteria>
  <done>
    - TrackingStatus StrEnum (6 membres) livrée dans domain/values.py
    - VideoTracking entity frozen+slots livrée dans domain/entities.py
    - VideoTrackingRepository Protocol livré dans ports/repositories.py
    - UnitOfWork Protocol déclare video_tracking attr
    - Re-exports ports/__init__.py + domain/__init__.py à jour
    - Tests domain (13+) verts
    - domain-is-pure + ports-are-pure toujours KEPT
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Migration video_tracking + VideoTrackingRepositorySQLite + SqliteUnitOfWork + Pipeline neutrality test</name>
  <files>src/vidscope/adapters/sqlite/schema.py, src/vidscope/adapters/sqlite/video_tracking_repository.py, src/vidscope/adapters/sqlite/unit_of_work.py, tests/unit/adapters/sqlite/test_video_tracking_repository.py, tests/unit/application/test_pipeline_neutrality.py</files>
  <read_first>
    - src/vidscope/adapters/sqlite/schema.py (pattern `_ensure_video_stats_table` lignes 278-329 — CREATE TABLE IF + existing check + indexes + appel depuis init_db)
    - src/vidscope/adapters/sqlite/video_stats_repository.py (pattern entity↔row helpers `_entity_to_row` / `_row_to_entity`, int(VideoId) cast, SQLAlchemy Core bind params, ON CONFLICT DO NOTHING — pour M011 utiliser DO UPDATE à la place)
    - src/vidscope/adapters/sqlite/unit_of_work.py (pattern __enter__ + __init__ slots — où ajouter le repo)
    - src/vidscope/domain/entities.py (VideoTracking livrée en Task 1)
    - src/vidscope/adapters/sqlite/video_repository.py (pattern upsert_by_platform_id — comment construit-il le repo avec un ON CONFLICT DO UPDATE)
    - tests/unit/adapters/sqlite/test_video_stats_repository.py (patterns de tests — fixture engine, CRUD, UNIQUE constraint)
    - tests/unit/adapters/sqlite/conftest.py (fixture `engine` disponible — init_db appelé)
    - .gsd/milestones/M011/M011-RESEARCH.md (Pattern 4 migration, Pattern 5 UoW, D1 upsert, Pitfall 3 UNIQUE constraint, Pitfall 5 pipeline neutrality, Pitfall 7 updated_at)
  </read_first>
  <behavior>
    - Test 1: Après `init_db(engine)` sur une DB fraîche, la table `video_tracking` existe avec colonnes: id, video_id, status, starred, notes, created_at, updated_at (vérifiable via `PRAGMA table_info(video_tracking)`).
    - Test 2: La table `video_tracking` a une contrainte UNIQUE sur `video_id` (vérifiable via `PRAGMA index_list('video_tracking')` ou via tentative d'insertion dupliquée qui DOIT passer par upsert sans erreur).
    - Test 3: `_ensure_video_tracking_table` est idempotent: appeler deux fois ne lève pas.
    - Test 4: Indexes `idx_video_tracking_status` ET `idx_video_tracking_starred` existent après init_db.
    - Test 5: `VideoTrackingRepositorySQLite.upsert(new_tracking)` sur un video_id sans ligne existante crée la ligne, renvoie l'entity avec `id` populé + `created_at` + `updated_at` timezone-aware UTC.
    - Test 6: `upsert(tracking)` sur un video_id AVEC ligne existante met à jour `status`, `starred`, `notes`, `updated_at` en gardant `id` et `created_at` intacts (updated_at strictement postérieur à created_at après update avec delay).
    - Test 7: Un deuxième appel `upsert(...)` sur le même `video_id` N'ÉMET AUCUNE `IntegrityError` / `StorageError` — Pitfall 3 résolu.
    - Test 8: `get_for_video(video_id)` renvoie `None` pour un video_id sans ligne, renvoie une `VideoTracking` pour un video_id avec ligne.
    - Test 9: `list_by_status(TrackingStatus.SAVED)` renvoie uniquement les rows avec status=='saved', ordonnées par `updated_at DESC`.
    - Test 10: `list_starred()` renvoie uniquement les rows avec starred=True, ordonnées par `updated_at DESC`.
    - Test 11: Suppression d'une video (DELETE FROM videos WHERE id=...) cascade la ligne `video_tracking` (FK ON DELETE CASCADE).
    - Test 12: `SqliteUnitOfWork.__enter__` expose `uow.video_tracking` comme instance de `VideoTrackingRepositorySQLite`.
    - Test 13 (pipeline neutrality): Insérer une ligne video, upsert tracking, puis ré-upsert la même video via `VideoRepository.upsert_by_platform_id` — la ligne `video_tracking` existe toujours et ses valeurs ne changent PAS (Pitfall 5).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/adapters/sqlite/schema.py`.

(a) Ajouter la Table SQLAlchemy Core `video_tracking` APRÈS la table `video_stats` existante (environ ligne 230), AVANT la section FTS5 DDL :

```python
# M011: user workflow overlay (one row per video, UNIQUE on video_id).
# Independent of `videos` — re-ingesting a video never touches this row
# (pipeline neutrality per D033 / Pitfall 5 of M011 RESEARCH).
video_tracking = Table(
    "video_tracking",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("status", String(32), nullable=False, default="new"),
    Column("starred", Boolean, nullable=False, default=False),
    Column("notes", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("video_id", name="uq_video_tracking_video_id"),
)
```

(b) Ajouter `"video_tracking"` au tuple `__all__` (ligne ~56-67) en tri alphabétique, entre `"video_stats"` et `"videos"` :
```python
__all__ = [
    "analyses",
    "frames",
    "init_db",
    "metadata",
    "pipeline_runs",
    "transcripts",
    "video_stats",
    "video_tracking",
    "videos",
    "watch_refreshes",
    "watched_accounts",
]
```

(c) Ajouter la fonction de migration APRÈS `_ensure_analysis_v2_columns` et AVANT la ligne finale `Row = dict[str, Any]` :

```python
def _ensure_video_tracking_table(conn: Connection) -> None:
    """M011/S01 migration: create ``video_tracking`` if absent. Idempotent.

    Called by :func:`init_db` on every startup so pre-M011 databases are
    upgraded automatically. No-op when the table already exists.

    Indexes
    -------
    - ``idx_video_tracking_status``: speeds up ``--status`` facet search (S03).
    - ``idx_video_tracking_starred``: speeds up ``--starred`` facet search (S03).
    """
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "video_tracking" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE video_tracking (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id   INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                    status     VARCHAR(32) NOT NULL DEFAULT 'new',
                    starred    BOOLEAN NOT NULL DEFAULT 0,
                    notes      TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_video_tracking_video_id UNIQUE (video_id)
                )
                """
            )
        )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_tracking_status "
            "ON video_tracking (status)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_tracking_starred "
            "ON video_tracking (starred)"
        )
    )
```

(d) Dans `init_db()` (ligne ~250), ajouter l'appel APRÈS `_ensure_analysis_v2_columns(conn)` :

```python
def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
        _ensure_analysis_v2_columns(conn)
        _ensure_video_tracking_table(conn)   # <-- M011/S01
```

Étape 2 — Créer `src/vidscope/adapters/sqlite/video_tracking_repository.py` :

```python
"""SQLite implementation of :class:`VideoTrackingRepository` (M011/S01/R056).

One row per video — UNIQUE on ``video_id``. The only write method is
``upsert``: callers never decide between INSERT/UPDATE because the
``ON CONFLICT(video_id) DO UPDATE`` handles both atomically.

Security (T-SQL-M011-01): all queries use SQLAlchemy Core parameterized
statements. ``video_id`` values are cast to ``int`` explicitly and enum
values via ``.value`` — no raw string interpolation touches the query.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import video_tracking as video_tracking_table
from vidscope.domain import TrackingStatus, VideoId, VideoTracking

__all__ = ["VideoTrackingRepositorySQLite"]


class VideoTrackingRepositorySQLite:
    """Repository for :class:`VideoTracking` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes — upsert only (D1 of M011 RESEARCH)
    # ------------------------------------------------------------------

    def upsert(self, tracking: VideoTracking) -> VideoTracking:
        """Insert or update the tracking row for ``tracking.video_id``.

        Uses ``ON CONFLICT(video_id) DO UPDATE`` (Pitfall 3 resolved):
        second call for the same ``video_id`` atomically replaces
        ``status``, ``starred``, ``notes``, ``updated_at``. ``created_at``
        is preserved on update (via ``excluded`` only on insert path).
        """
        now = datetime.now(UTC)
        payload = {
            "video_id": int(tracking.video_id),
            "status": tracking.status.value,
            "starred": bool(tracking.starred),
            "notes": tracking.notes,
            "created_at": tracking.created_at or now,
            "updated_at": now,
        }
        stmt = sqlite_insert(video_tracking_table).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["video_id"],
            set_={
                "status": stmt.excluded.status,
                "starred": stmt.excluded.starred,
                "notes": stmt.excluded.notes,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self._conn.execute(stmt)

        existing = self.get_for_video(tracking.video_id)
        if existing is None:  # pragma: no cover — defensive
            return tracking
        return existing

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_for_video(self, video_id: VideoId) -> VideoTracking | None:
        stmt = (
            select(video_tracking_table)
            .where(video_tracking_table.c.video_id == int(video_id))
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().first()
        if row is None:
            return None
        return _row_to_entity(dict(row))

    def list_by_status(
        self, status: TrackingStatus, *, limit: int = 1000
    ) -> list[VideoTracking]:
        stmt = (
            select(video_tracking_table)
            .where(video_tracking_table.c.status == status.value)
            .order_by(video_tracking_table.c.updated_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_entity(dict(r)) for r in rows]

    def list_starred(self, *, limit: int = 1000) -> list[VideoTracking]:
        stmt = (
            select(video_tracking_table)
            .where(video_tracking_table.c.starred.is_(True))
            .order_by(video_tracking_table.c.updated_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_entity(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _row_to_entity(row: dict[str, Any]) -> VideoTracking:
    # Defensive enum parse — corrupted DB value -> default to NEW (T-DATA-01).
    status_raw = row.get("status")
    try:
        status = TrackingStatus(str(status_raw)) if status_raw else TrackingStatus.NEW
    except ValueError:
        status = TrackingStatus.NEW

    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)

    return VideoTracking(
        id=int(row["id"]),
        video_id=VideoId(int(row["video_id"])),
        status=status,
        starred=bool(row.get("starred")),
        notes=row.get("notes"),
        created_at=created_at,
        updated_at=updated_at,
    )
```

Étape 3 — Étendre `src/vidscope/adapters/sqlite/unit_of_work.py` (per Pattern 5 RESEARCH).

(a) Ajouter l'import en haut du fichier (tri alphabétique) :
```python
from vidscope.adapters.sqlite.video_tracking_repository import (
    VideoTrackingRepositorySQLite,
)
```

(b) Dans le bloc `from vidscope.ports import (...)`, ajouter `VideoTrackingRepository` (tri alphabétique) :
```python
from vidscope.ports import (
    AnalysisRepository,
    FrameRepository,
    PipelineRunRepository,
    SearchIndex,
    TranscriptRepository,
    VideoRepository,
    VideoStatsRepository,
    VideoTrackingRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)
```

(c) Dans `SqliteUnitOfWork.__init__`, ajouter l'annotation de slot APRÈS `self.video_stats: VideoStatsRepository` :
```python
        self.video_tracking: VideoTrackingRepository
```

(d) Dans `SqliteUnitOfWork.__enter__`, ajouter l'instanciation APRÈS `self.video_stats = VideoStatsRepositorySQLite(self._connection)` :
```python
        self.video_tracking = VideoTrackingRepositorySQLite(self._connection)
```

Étape 4 — Créer `tests/unit/adapters/sqlite/test_video_tracking_repository.py` :

```python
"""Unit tests for VideoTrackingRepositorySQLite (M011/S01/R056)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.video_tracking_repository import (
    VideoTrackingRepositorySQLite,
)
from vidscope.domain import TrackingStatus, VideoId, VideoTracking


def _insert_video(engine: Engine, platform_id: str) -> int:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos (platform, platform_id, url, created_at) "
                "VALUES (:p, :pid, :u, :c)"
            ),
            {
                "p": "youtube",
                "pid": platform_id,
                "u": f"https://y.be/{platform_id}",
                "c": datetime.now(UTC),
            },
        )
        return int(
            conn.execute(
                text("SELECT id FROM videos WHERE platform_id=:pid"),
                {"pid": platform_id},
            ).scalar()
        )


class TestMigration:
    def test_table_exists_after_init_db(self, engine: Engine) -> None:
        with engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
        assert "video_tracking" in names

    def test_table_has_expected_columns(self, engine: Engine) -> None:
        with engine.connect() as conn:
            cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(video_tracking)"))
            }
        assert {
            "id", "video_id", "status", "starred", "notes",
            "created_at", "updated_at",
        }.issubset(cols)

    def test_indexes_exist(self, engine: Engine) -> None:
        with engine.connect() as conn:
            idx_rows = list(conn.execute(text("PRAGMA index_list('video_tracking')")))
        idx_names = {row[1] for row in idx_rows}
        assert "idx_video_tracking_status" in idx_names
        assert "idx_video_tracking_starred" in idx_names

    def test_unique_video_id_enforced(self, engine: Engine) -> None:
        # The UNIQUE constraint exists — upsert relies on it.
        with engine.connect() as conn:
            idx_rows = list(conn.execute(text("PRAGMA index_list('video_tracking')")))
        unique_idx = [row[1] for row in idx_rows if row[2] == 1]
        # The UNIQUE constraint creates an implicit index name containing "video_id".
        assert any("video_id" in name or "uq_video_tracking" in name for name in unique_idx), (
            f"UNIQUE video_id constraint missing: indexes={idx_rows}"
        )

    def test_ensure_table_idempotent(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.schema import _ensure_video_tracking_table

        with engine.begin() as conn:
            _ensure_video_tracking_table(conn)
            _ensure_video_tracking_table(conn)
        # No error = idempotent


class TestUpsertInsert:
    def test_upsert_creates_row_with_id_populated(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tup1")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            tracking = VideoTracking(
                video_id=VideoId(vid),
                status=TrackingStatus.SAVED,
                starred=True,
                notes="cool hook",
            )
            persisted = repo.upsert(tracking)

        assert persisted.id is not None
        assert persisted.video_id == VideoId(vid)
        assert persisted.status is TrackingStatus.SAVED
        assert persisted.starred is True
        assert persisted.notes == "cool hook"
        assert persisted.created_at is not None
        assert persisted.created_at.tzinfo is not None
        assert persisted.updated_at is not None

    def test_upsert_existing_row_replaces_fields(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tup2")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            first = repo.upsert(
                VideoTracking(
                    video_id=VideoId(vid), status=TrackingStatus.NEW, notes="initial",
                )
            )
        time.sleep(0.01)
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            second = repo.upsert(
                VideoTracking(
                    video_id=VideoId(vid),
                    status=TrackingStatus.ACTIONED,
                    starred=True,
                    notes="updated",
                )
            )
        assert first.id == second.id  # same row
        assert second.status is TrackingStatus.ACTIONED
        assert second.starred is True
        assert second.notes == "updated"
        assert second.updated_at is not None and first.updated_at is not None
        assert second.updated_at >= first.updated_at

    def test_second_upsert_does_not_raise(self, engine: Engine) -> None:
        """Pitfall 3: ON CONFLICT DO UPDATE prevents IntegrityError."""
        vid = _insert_video(engine, "tup3")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.NEW))
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.REVIEWED))
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.SAVED))


class TestReads:
    def test_get_for_video_none_when_absent(self, engine: Engine) -> None:
        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            assert repo.get_for_video(VideoId(99999)) is None

    def test_get_for_video_returns_entity(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tr1")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(
                VideoTracking(
                    video_id=VideoId(vid), status=TrackingStatus.SAVED, starred=True,
                )
            )
        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            got = repo.get_for_video(VideoId(vid))
        assert got is not None
        assert got.status is TrackingStatus.SAVED
        assert got.starred is True

    def test_list_by_status_filters_and_orders(self, engine: Engine) -> None:
        # Three videos, two with status SAVED, one with NEW.
        vids = [_insert_video(engine, f"tb{i}") for i in range(3)]
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(vids[0]), status=TrackingStatus.SAVED))
            time.sleep(0.01)
            repo.upsert(VideoTracking(video_id=VideoId(vids[1]), status=TrackingStatus.NEW))
            time.sleep(0.01)
            repo.upsert(VideoTracking(video_id=VideoId(vids[2]), status=TrackingStatus.SAVED))

        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            saved = repo.list_by_status(TrackingStatus.SAVED)
        assert len(saved) == 2
        assert all(t.status is TrackingStatus.SAVED for t in saved)
        # Ordered by updated_at DESC -> vids[2] first
        assert int(saved[0].video_id) == vids[2]

    def test_list_starred_filters(self, engine: Engine) -> None:
        v1 = _insert_video(engine, "ts1")
        v2 = _insert_video(engine, "ts2")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(v1), status=TrackingStatus.NEW, starred=True))
            repo.upsert(VideoTracking(video_id=VideoId(v2), status=TrackingStatus.NEW, starred=False))
        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            starred = repo.list_starred()
        assert len(starred) == 1
        assert int(starred[0].video_id) == v1


class TestCascade:
    def test_delete_video_cascades_to_tracking(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tc1")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.SAVED))
        # Enable FK enforcement for this connection then delete.
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("DELETE FROM videos WHERE id=:v"), {"v": vid})
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM video_tracking WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert row == 0


class TestUoWExposure:
    def test_uow_exposes_video_tracking(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork

        with SqliteUnitOfWork(engine) as uow:
            assert isinstance(uow.video_tracking, VideoTrackingRepositorySQLite)
```

Étape 5 — Créer `tests/unit/application/test_pipeline_neutrality.py` (test regression critique — Pitfall 5) :

```python
"""Pipeline neutrality regression guard (M011/S01/R056).

Re-ingesting a video via VideoRepository.upsert_by_platform_id must NOT
touch the associated video_tracking row. This is the invariant that
keeps user annotations safe across re-ingests.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Platform,
    PlatformId,
    TrackingStatus,
    Video,
    VideoId,
    VideoTracking,
)


class TestPipelineNeutrality:
    def test_reingest_preserves_tracking(self, engine: Engine) -> None:
        # Step 1: ingest video.
        with SqliteUnitOfWork(engine) as uow:
            v = uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("neutral1"),
                    url="https://y.be/neutral1",
                    title="Original title",
                )
            )
            assert v.id is not None
            video_id = v.id

        # Step 2: user sets tracking.
        with SqliteUnitOfWork(engine) as uow:
            uow.video_tracking.upsert(
                VideoTracking(
                    video_id=VideoId(int(video_id)),
                    status=TrackingStatus.SAVED,
                    starred=True,
                    notes="important",
                )
            )

        # Step 3: re-ingest the SAME URL with different metadata.
        with SqliteUnitOfWork(engine) as uow:
            uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("neutral1"),
                    url="https://y.be/neutral1",
                    title="Updated title",
                    view_count=12345,
                )
            )

        # Step 4: assert tracking row is INTACT.
        with SqliteUnitOfWork(engine) as uow:
            tracking = uow.video_tracking.get_for_video(VideoId(int(video_id)))
        assert tracking is not None
        assert tracking.status is TrackingStatus.SAVED
        assert tracking.starred is True
        assert tracking.notes == "important"

    def test_tracking_has_exactly_one_row_per_video(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            v = uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("neutral2"),
                    url="https://y.be/neutral2",
                )
            )
            assert v.id is not None
            vid = int(v.id)

        with SqliteUnitOfWork(engine) as uow:
            uow.video_tracking.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.NEW))
            uow.video_tracking.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.REVIEWED))
            uow.video_tracking.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.SAVED))

        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM video_tracking WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert count == 1
```

Étape 6 — Exécuter :
```
uv run pytest tests/unit/adapters/sqlite/test_video_tracking_repository.py tests/unit/application/test_pipeline_neutrality.py -x -q
uv run lint-imports
```

NE PAS utiliser de string interpolation pour le SQL (contrat de sécurité T-SQL). NE PAS ajouter des champs à la table `videos` (D033 videos immutable).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/sqlite/test_video_tracking_repository.py tests/unit/application/test_pipeline_neutrality.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n 'video_tracking = Table' src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n 'def _ensure_video_tracking_table' src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n '_ensure_video_tracking_table(conn)' src/vidscope/adapters/sqlite/schema.py` matches (appel dans init_db)
    - `grep -n 'idx_video_tracking_status' src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n 'idx_video_tracking_starred' src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n 'uq_video_tracking_video_id' src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n 'class VideoTrackingRepositorySQLite' src/vidscope/adapters/sqlite/video_tracking_repository.py` matches
    - `grep -n 'on_conflict_do_update' src/vidscope/adapters/sqlite/video_tracking_repository.py` matches
    - `grep -n 'index_elements=\["video_id"\]' src/vidscope/adapters/sqlite/video_tracking_repository.py` matches
    - `grep -n 'VideoTrackingRepositorySQLite(self._connection)' src/vidscope/adapters/sqlite/unit_of_work.py` matches
    - `grep -n 'self.video_tracking' src/vidscope/adapters/sqlite/unit_of_work.py` matches
    - `uv run pytest tests/unit/adapters/sqlite/test_video_tracking_repository.py -x -q` exits 0
    - `uv run pytest tests/unit/application/test_pipeline_neutrality.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (application-has-no-adapters KEPT — le test de neutrality utilise SqliteUnitOfWork mais il vit dans tests/, pas dans application/)
  </acceptance_criteria>
  <done>
    - Table SQLAlchemy Core `video_tracking` déclarée avec UNIQUE(video_id) + FK CASCADE
    - Migration `_ensure_video_tracking_table` idempotente + appelée dans init_db
    - Indexes `idx_video_tracking_status` et `idx_video_tracking_starred` créés
    - `VideoTrackingRepositorySQLite` livré avec upsert ON CONFLICT DO UPDATE (Pitfall 3)
    - `SqliteUnitOfWork` expose `uow.video_tracking`
    - Pipeline neutrality test vert — re-ingest ne wipe pas tracking
    - 15+ tests adapter + 2 tests neutrality verts
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: SetVideoTrackingUseCase + CLI `vidscope review` + registration dans app.py</name>
  <files>src/vidscope/application/set_video_tracking.py, src/vidscope/cli/commands/review.py, src/vidscope/cli/commands/__init__.py, src/vidscope/cli/app.py, tests/unit/application/test_set_video_tracking.py, tests/unit/cli/test_review_cmd.py</files>
  <read_first>
    - src/vidscope/application/search_videos.py (pattern use case simple — __init__ qui prend unit_of_work_factory, execute() method, no adapter imports)
    - src/vidscope/application/refresh_stats.py (pattern plus complexe si use case retourne un dataclass de résultat — à consulter pour pattern result)
    - src/vidscope/cli/commands/search.py (pattern single-command CLI avec `Annotated[...]` options)
    - src/vidscope/cli/commands/watch.py (pattern acquire_container + handle_domain_errors + fail_user)
    - src/vidscope/cli/commands/__init__.py (où enregistrer review_command)
    - src/vidscope/cli/app.py (lignes 78-113 — pattern d'enregistrement `app.command("review", help="...")(review_command)`)
    - src/vidscope/cli/_support.py (acquire_container, console, fail_user, handle_domain_errors — imports nécessaires)
    - tests/unit/application/test_refresh_stats.py ou test_search_videos.py (pattern InMemory repo fake pour tests application)
    - tests/unit/cli/test_watch.py (pattern CliRunner pour CLI snapshot)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 10 CLI signature `vidscope review <id> --status saved --star --note "..."`)
    - .gsd/milestones/M011/M011-RESEARCH.md (D1 upsert semantics + Open Question 3 notes None vs "")
  </read_first>
  <behavior>
    - Test 1: `SetVideoTrackingUseCase(unit_of_work_factory=factory).execute(video_id=1, status=TrackingStatus.SAVED)` appelle `uow.video_tracking.upsert(...)` exactement une fois avec un `VideoTracking(video_id=VideoId(1), status=TrackingStatus.SAVED, starred=False, notes=None)`.
    - Test 2: `.execute(video_id=1, status=TrackingStatus.SAVED, starred=True, notes="hook")` passe `starred=True, notes="hook"` à upsert.
    - Test 3: `.execute(video_id=1, status=TrackingStatus.SAVED, notes=None)` sur une ligne EXISTANTE avec notes="old" → préserve "old" (None == "no update"). Implémentation: use case fetche get_for_video, si notes arg is None ET existant existe, passe l'ancien notes à upsert.
    - Test 4: `.execute(video_id=1, status=TrackingStatus.SAVED, notes="")` clear les notes existantes (empty string == explicit clear).
    - Test 5: Use case retourne un `SetVideoTrackingResult(tracking=VideoTracking(...))` ou similaire — signature à documenter, doit au minimum retourner le tracking persisté.
    - Test 6: CLI `vidscope review 42 --status saved --star --note "look"` imprime une ligne de confirmation contenant le video_id, le status, et "starred".
    - Test 7: CLI `vidscope review 42 --status invalid` lève une BadParameter ("--status expects ...") — exit code != 0.
    - Test 8: CLI `vidscope review 42 --status new --unstar` dé-starre la ligne.
    - Test 9: CLI `vidscope review 42 --status new --clear-note` met `notes=""` (explicit clear).
    - Test 10: `vidscope review --help` liste toutes les options et les 6 valeurs de --status.
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/application/set_video_tracking.py` :

```python
"""SetVideoTrackingUseCase — M011/S01/R056.

Writes a user workflow overlay for a single video: ``status``, ``starred``,
``notes``. Idempotent via the repository's ``upsert`` — calling ``execute``
twice with the same inputs produces the same end state.

``notes`` semantics (D1 + Open Question 3 of M011 RESEARCH):
- ``notes=None`` -> preserve existing notes if the row exists (no-op on notes).
- ``notes=""`` -> explicit clear (set DB notes to "").
- ``notes="text"`` -> set to text.

Follows hexagonal discipline: only imports from vidscope.domain and
vidscope.ports. No adapter reach-in.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import TrackingStatus, VideoId, VideoTracking
from vidscope.ports import UnitOfWorkFactory

__all__ = ["SetVideoTrackingResult", "SetVideoTrackingUseCase"]


@dataclass(frozen=True, slots=True)
class SetVideoTrackingResult:
    """Outcome of :class:`SetVideoTrackingUseCase.execute`."""

    tracking: VideoTracking
    created: bool  # True if this was the first tracking row for the video


class SetVideoTrackingUseCase:
    """Upsert the workflow overlay for a single video."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        video_id: int,
        *,
        status: TrackingStatus,
        starred: bool = False,
        notes: str | None = None,
    ) -> SetVideoTrackingResult:
        """Set or update the tracking row for ``video_id``.

        Parameters
        ----------
        video_id:
            Primary key of the target video.
        status:
            New :class:`TrackingStatus` value.
        starred:
            New starred flag (default False).
        notes:
            ``None`` preserves existing notes when the row already
            exists; empty string clears them; any other string replaces.
        """
        vid = VideoId(int(video_id))
        with self._uow_factory() as uow:
            existing = uow.video_tracking.get_for_video(vid)
            resolved_notes: str | None
            if notes is None and existing is not None:
                resolved_notes = existing.notes  # preserve
            else:
                resolved_notes = notes  # may be "", replace; may be str, replace

            new_entity = VideoTracking(
                video_id=vid,
                status=status,
                starred=starred,
                notes=resolved_notes,
            )
            persisted = uow.video_tracking.upsert(new_entity)
            return SetVideoTrackingResult(
                tracking=persisted,
                created=existing is None,
            )
```

Étape 2 — Créer `src/vidscope/cli/commands/review.py` (per Pattern 6 RESEARCH + CLI single-command pattern de search.py) :

```python
"""`vidscope review <video_id> [--status X] [--star/--unstar] [--note TEXT] [--clear-note]`

M011/S01/R056: set a user workflow overlay on a single video.
"""

from __future__ import annotations

from typing import Annotated

import typer

from vidscope.application.set_video_tracking import SetVideoTrackingUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain import TrackingStatus

__all__ = ["review_command"]


def _parse_status(raw: str) -> TrackingStatus:
    norm = raw.strip().lower()
    try:
        return TrackingStatus(norm)
    except ValueError as exc:
        valid = ", ".join(s.value for s in TrackingStatus)
        raise typer.BadParameter(
            f"--status must be one of: {valid}. Got {raw!r}."
        ) from exc


def review_command(
    video_id: Annotated[int, typer.Argument(help="Video id (from `vidscope list`).")],
    status: Annotated[
        str,
        typer.Option(
            "--status",
            help=(
                "Workflow status: new, reviewed, saved, actioned, ignored, archived."
            ),
        ),
    ],
    star: Annotated[
        bool,
        typer.Option("--star/--unstar", help="Set or unset the starred flag."),
    ] = False,
    note: Annotated[
        str | None,
        typer.Option("--note", help="Set a free-text note (overwrites existing)."),
    ] = None,
    clear_note: Annotated[
        bool,
        typer.Option("--clear-note", help="Clear the existing note (sets to '')."),
    ] = False,
) -> None:
    """Set workflow overlay (status, starred, notes) on a video."""
    with handle_domain_errors():
        if note is not None and clear_note:
            raise fail_user("--note and --clear-note are mutually exclusive.")

        parsed_status = _parse_status(status)
        resolved_notes: str | None
        if clear_note:
            resolved_notes = ""
        else:
            resolved_notes = note  # None -> preserve, str -> replace

        container = acquire_container()
        use_case = SetVideoTrackingUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(
            video_id,
            status=parsed_status,
            starred=star,
            notes=resolved_notes,
        )

        verb = "created" if result.created else "updated"
        star_label = "starred" if result.tracking.starred else "unstarred"
        console.print(
            f"[bold green]{verb}[/bold green] tracking for video "
            f"{int(result.tracking.video_id)}: "
            f"status={result.tracking.status.value}, {star_label}"
            + (
                f", notes={result.tracking.notes!r}"
                if result.tracking.notes is not None
                else ""
            )
        )
```

Étape 3 — Enregistrer la commande dans `src/vidscope/cli/commands/__init__.py` :

(a) Ajouter l'import (tri alphabétique après `refresh_stats_command`):
```python
from vidscope.cli.commands.review import review_command
```

(b) Ajouter `"review_command"` au `__all__` (tri alphabétique, après `"refresh_stats_command"`).

Étape 4 — Enregistrer dans `src/vidscope/cli/app.py` :

(a) Dans l'import `from vidscope.cli.commands import (...)`, ajouter `review_command` (tri alphabétique, après `refresh_stats_command`).

(b) Ajouter l'enregistrement APRÈS la ligne `app.command("refresh-stats", ...)(refresh_stats_command)` (ou à la fin des commandes, avant `app.command("explain", ...)`) :
```python
app.command(
    "review",
    help="Set workflow overlay (status, starred, notes) on a video.",
)(review_command)
```

Étape 5 — Créer `tests/unit/application/test_set_video_tracking.py` :

```python
"""Unit tests for SetVideoTrackingUseCase (M011/S01/R056)."""

from __future__ import annotations

from types import SimpleNamespace

from vidscope.application.set_video_tracking import (
    SetVideoTrackingResult,
    SetVideoTrackingUseCase,
)
from vidscope.domain import TrackingStatus, VideoId, VideoTracking


class _FakeTrackingRepo:
    def __init__(self) -> None:
        self._store: dict[int, VideoTracking] = {}
        self.upsert_calls: list[VideoTracking] = []

    def get_for_video(self, video_id: VideoId) -> VideoTracking | None:
        return self._store.get(int(video_id))

    def upsert(self, tracking: VideoTracking) -> VideoTracking:
        self.upsert_calls.append(tracking)
        persisted = VideoTracking(
            video_id=tracking.video_id,
            status=tracking.status,
            starred=tracking.starred,
            notes=tracking.notes,
            id=42,
        )
        self._store[int(tracking.video_id)] = persisted
        return persisted

    def list_by_status(self, status, *, limit=1000):
        return []

    def list_starred(self, *, limit=1000):
        return []


class _FakeUoW:
    def __init__(self, tracking_repo: _FakeTrackingRepo) -> None:
        self.video_tracking = tracking_repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _make_factory(repo: _FakeTrackingRepo):
    def _factory():
        return _FakeUoW(repo)

    return _factory


class TestSetVideoTrackingUseCase:
    def test_creates_new_tracking_row(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        result = uc.execute(1, status=TrackingStatus.SAVED)

        assert isinstance(result, SetVideoTrackingResult)
        assert result.created is True
        assert result.tracking.status is TrackingStatus.SAVED
        assert result.tracking.starred is False
        assert len(repo.upsert_calls) == 1
        call = repo.upsert_calls[0]
        assert call.video_id == VideoId(1)
        assert call.notes is None

    def test_updates_existing_tracking_row(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW)
        result = uc.execute(1, status=TrackingStatus.ACTIONED, starred=True)
        assert result.created is False
        assert result.tracking.status is TrackingStatus.ACTIONED
        assert result.tracking.starred is True

    def test_notes_none_preserves_existing(self) -> None:
        """Open Q 3: --note absent => preserve existing notes."""
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW, notes="first")
        result = uc.execute(1, status=TrackingStatus.SAVED, notes=None)
        assert result.tracking.notes == "first"

    def test_notes_empty_string_clears(self) -> None:
        """Open Q 3: --clear-note (notes='') clears existing."""
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW, notes="first")
        result = uc.execute(1, status=TrackingStatus.SAVED, notes="")
        assert result.tracking.notes == ""

    def test_notes_string_replaces(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        uc.execute(1, status=TrackingStatus.NEW, notes="first")
        result = uc.execute(1, status=TrackingStatus.SAVED, notes="second")
        assert result.tracking.notes == "second"

    def test_starred_default_false(self) -> None:
        repo = _FakeTrackingRepo()
        uc = SetVideoTrackingUseCase(unit_of_work_factory=_make_factory(repo))
        result = uc.execute(1, status=TrackingStatus.NEW)
        assert result.tracking.starred is False
```

Étape 6 — Créer `tests/unit/cli/test_review_cmd.py` :

```python
"""CliRunner tests for `vidscope review` (M011/S01/R056)."""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from vidscope.cli.app import app


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    # Taxonomy path needs the repo root
    import pathlib
    here = pathlib.Path(__file__).resolve()
    for _ in range(6):
        if (here / "config" / "taxonomy.yaml").is_file():
            monkeypatch.chdir(here)
            break
        here = here.parent
    yield


def _insert_video(tmp_path) -> int:
    """Insert a video row so `review` has something to point to."""
    from datetime import UTC, datetime
    from sqlalchemy import text
    from vidscope.infrastructure.container import build_container

    container = build_container()
    try:
        with container.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO videos (platform, platform_id, url, created_at) "
                    "VALUES (:p, :pid, :u, :c)"
                ),
                {
                    "p": "youtube", "pid": "cli_review_1",
                    "u": "https://y.be/cli_review_1",
                    "c": datetime.now(UTC),
                },
            )
            vid = int(
                conn.execute(
                    text("SELECT id FROM videos WHERE platform_id='cli_review_1'")
                ).scalar()
            )
        return vid
    finally:
        container.engine.dispose()


class TestReviewCmd:
    def test_help_lists_all_statuses(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["review", "--help"])
        assert result.exit_code == 0
        for s in ("new", "reviewed", "saved", "actioned", "ignored", "archived"):
            assert s in result.output

    def test_review_saved_with_star_and_note(self, tmp_path) -> None:
        vid = _insert_video(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["review", str(vid), "--status", "saved", "--star", "--note", "hook"],
        )
        assert result.exit_code == 0, result.output
        assert "saved" in result.output
        assert "starred" in result.output

    def test_review_invalid_status_fails(self, tmp_path) -> None:
        vid = _insert_video(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["review", str(vid), "--status", "bogus"])
        assert result.exit_code != 0
        assert "bogus" in result.output or "--status" in result.output

    def test_review_unstar(self, tmp_path) -> None:
        vid = _insert_video(tmp_path)
        runner = CliRunner()
        # First: star
        r1 = runner.invoke(
            app, ["review", str(vid), "--status", "saved", "--star"]
        )
        assert r1.exit_code == 0
        # Then: unstar
        r2 = runner.invoke(
            app, ["review", str(vid), "--status", "saved", "--unstar"]
        )
        assert r2.exit_code == 0
        assert "unstarred" in r2.output

    def test_review_clear_note(self, tmp_path) -> None:
        vid = _insert_video(tmp_path)
        runner = CliRunner()
        runner.invoke(
            app, ["review", str(vid), "--status", "saved", "--note", "initial"]
        )
        r = runner.invoke(
            app, ["review", str(vid), "--status", "saved", "--clear-note"]
        )
        assert r.exit_code == 0

    def test_review_note_and_clear_note_mutually_exclusive(self, tmp_path) -> None:
        vid = _insert_video(tmp_path)
        runner = CliRunner()
        r = runner.invoke(
            app,
            [
                "review", str(vid), "--status", "saved",
                "--note", "x", "--clear-note",
            ],
        )
        assert r.exit_code != 0
```

Étape 7 — Exécuter :
```
uv run pytest tests/unit/application/test_set_video_tracking.py tests/unit/cli/test_review_cmd.py -x -q
uv run lint-imports
```

NE PAS importer `vidscope.adapters.*` depuis `vidscope.application.set_video_tracking` (contrat `application-has-no-adapters`). NE PAS importer `vidscope.adapters.*` directement depuis `vidscope.cli.commands.review` (doit passer par `acquire_container`).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_set_video_tracking.py tests/unit/cli/test_review_cmd.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class SetVideoTrackingUseCase" src/vidscope/application/set_video_tracking.py` matches
    - `grep -n "unit_of_work_factory" src/vidscope/application/set_video_tracking.py` matches
    - `grep -nE "from vidscope.adapters" src/vidscope/application/set_video_tracking.py` returns exit 1 (no match — application-has-no-adapters)
    - `grep -n "def review_command" src/vidscope/cli/commands/review.py` matches
    - `grep -nE '"--status"' src/vidscope/cli/commands/review.py` matches
    - `grep -nE '"--star/--unstar"' src/vidscope/cli/commands/review.py` matches
    - `grep -nE '"--clear-note"' src/vidscope/cli/commands/review.py` matches
    - `grep -n "review_command" src/vidscope/cli/commands/__init__.py` matches
    - `grep -n 'app.command(\s*"review"' src/vidscope/cli/app.py` matches
    - `grep -n "review_command" src/vidscope/cli/app.py` matches
    - `uv run pytest tests/unit/application/test_set_video_tracking.py -x -q` exits 0
    - `uv run pytest tests/unit/cli/test_review_cmd.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (application-has-no-adapters KEPT)
  </acceptance_criteria>
  <done>
    - SetVideoTrackingUseCase livré (application pure, no adapter imports)
    - CLI `vidscope review` enregistrée sur le root app avec --status/--star/--unstar/--note/--clear-note
    - Notes semantics: None=preserve, ""=clear, str=replace (Open Q 3 résolue)
    - 6 tests use case + 6 tests CLI verts
    - 10 contrats import-linter toujours KEPT
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI (user) → SetVideoTrackingUseCase | `--note` contenu fourni par l'utilisateur (texte libre). |
| CLI (user) → VideoTrackingRepositorySQLite | `video_id` fourni par CLI, enum status fourni par CLI. |
| Disk DB (pre-M011) → `_row_to_entity` | Données pré-migration potentiellement NULL, ou enum value inattendu après corruption. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-SQL-M011-01 | Tampering | `VideoTrackingRepositorySQLite` queries | mitigate | SQLAlchemy Core `sqlite_insert(...).values(**payload)` + `.where(col == value)` bind params uniquement. `int(tracking.video_id)` cast explicite. `status.value` (enum) passé comme bind. Zéro string interpolation. |
| T-INPUT-M011-01 | Tampering | CLI `--note` contient texte libre | mitigate | `--note` est stocké dans la colonne `notes TEXT` via bind param, jamais interprété. Pas de rendu HTML (CLI rich prints l'output localement). `notes` n'est écrit nulle part sur le réseau (R032 single-user). |
| T-DATA-M011-01 | Tampering | `_row_to_entity` sur status corrompu en DB | mitigate | Try/except `ValueError` sur `TrackingStatus(str(status_raw))` → défaut `TrackingStatus.NEW`. Pas de crash. Test implicite via idempotence des migrations. |
| T-STATE-M011-01 | Availability | Migration `_ensure_video_tracking_table` sur DB pré-M011 | mitigate | Check via `sqlite_master` avant CREATE TABLE. `CREATE INDEX IF NOT EXISTS` pour les index. Test `test_ensure_table_idempotent`. |
| T-PIPELINE-M011-01 | Tampering | Re-ingest wipe video_tracking | mitigate | `ON DELETE CASCADE` n'agit que sur DELETE explicite, pas sur upsert_by_platform_id. Test `test_reingest_preserves_tracking` garantit l'invariant. |
| T-UNIQ-M011-01 | Availability | 2e appel `vidscope review` sur même video_id | mitigate | `on_conflict_do_update(index_elements=["video_id"])` — IntegrityError impossible. Test `test_second_upsert_does_not_raise`. |
| T-ARCH-M011-01 | Spoofing | Application layer important un adapter | mitigate | Contrat `application-has-no-adapters` existant reste KEPT. Test architecture. |
</threat_model>

<verification>
Après les 3 tâches, exécuter :
- `uv run pytest tests/unit/domain/test_video_tracking.py tests/unit/adapters/sqlite/test_video_tracking_repository.py tests/unit/application/test_pipeline_neutrality.py tests/unit/application/test_set_video_tracking.py tests/unit/cli/test_review_cmd.py -x -q` vert
- `uv run lint-imports` vert — 10 contrats KEPT (dont `domain-is-pure`, `ports-are-pure`, `application-has-no-adapters`)
- `uv run pytest -m architecture -x -q` vert
- `uv run vidscope review --help` liste toutes les 6 valeurs de --status
- `grep -n "TrackingStatus" src/vidscope/domain/__init__.py` matches
- `grep -n "video_tracking = Table" src/vidscope/adapters/sqlite/schema.py` matches
</verification>

<success_criteria>
S01 est complet quand :
- [ ] `TrackingStatus` StrEnum (6 membres) livrée + re-exportée depuis `vidscope.domain`
- [ ] `VideoTracking` entity frozen+slots livrée + re-exportée
- [ ] `VideoTrackingRepository` Protocol livré dans `vidscope.ports.repositories` + re-exporté
- [ ] `UnitOfWork` Protocol déclare `video_tracking: VideoTrackingRepository`
- [ ] Table `video_tracking` créée par migration additive idempotente dans `init_db`
- [ ] `VideoTrackingRepositorySQLite` avec upsert ON CONFLICT DO UPDATE + get/list_by_status/list_starred
- [ ] `SqliteUnitOfWork` expose `uow.video_tracking`
- [ ] `SetVideoTrackingUseCase` livré (application pure) avec semantics None=preserve / ""=clear / str=replace
- [ ] CLI `vidscope review` enregistrée avec --status/--star/--unstar/--note/--clear-note
- [ ] Test de pipeline neutrality: re-ingest ne wipe pas tracking (regression guard)
- [ ] Suite tests unit verte (domain + adapter + use case + CLI + neutrality)
- [ ] `lint-imports` vert (10 contrats KEPT inchangés)
- [ ] R056 couvert au niveau socle (domain + port + adapter + use case + CLI + guard)
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M011/M011-S01-SUMMARY.md` documentant :
- Signature finale de `TrackingStatus` (6 membres exacts) et `VideoTracking` (ordre des champs, defaults)
- DDL finale de la table `video_tracking` (UNIQUE video_id, FK CASCADE, 2 indexes)
- Pattern upsert choisi (ON CONFLICT DO UPDATE) et décision sur updated_at
- Notes semantics (None/""/str) implémentée dans `SetVideoTrackingUseCase`
- CLI signature finale de `vidscope review`
- Test de pipeline neutrality — invariant documenté
- Liste exhaustive des fichiers créés/modifiés
</output>
