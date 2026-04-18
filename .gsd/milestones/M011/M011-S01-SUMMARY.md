---
phase: M011
plan: S01
subsystem: domain+ports+adapters+application+cli
tags: [tracking, workflow, sqlite, upsert, cli]
requirements: [R056]

dependency_graph:
  requires: [M010-S01, M010-S02, M010-S03, M010-S04]
  provides: [video_tracking_table, VideoTracking_entity, VideoTrackingRepository_port, SetVideoTrackingUseCase, vidscope_review_CLI]
  affects: [M011-S02, M011-S03]

tech_stack:
  added: []
  patterns:
    - TrackingStatus StrEnum (6 membres) dans domain/values.py
    - VideoTracking frozen+slots entity avec video_id+status+starred+notes+id+created_at+updated_at
    - VideoTrackingRepository Protocol @runtime_checkable dans ports/repositories.py
    - Migration additive idempotente _ensure_video_tracking_table dans schema.py
    - ON CONFLICT(video_id) DO UPDATE dans VideoTrackingRepositorySQLite.upsert
    - SetVideoTrackingUseCase: notes None=preserve / ""=clear / str=replace (Open Q 3)
    - CLI single-command review avec --status/--star/--unstar/--note/--clear-note

key_files:
  created:
    - src/vidscope/domain/values.py (TrackingStatus StrEnum)
    - src/vidscope/domain/entities.py (VideoTracking entity)
    - src/vidscope/adapters/sqlite/video_tracking_repository.py
    - src/vidscope/application/set_video_tracking.py
    - src/vidscope/cli/commands/review.py
    - tests/unit/domain/test_video_tracking.py
    - tests/unit/adapters/sqlite/test_video_tracking_repository.py
    - tests/unit/application/test_pipeline_neutrality.py
    - tests/unit/application/test_set_video_tracking.py
    - tests/unit/cli/test_review_cmd.py
  modified:
    - src/vidscope/domain/__init__.py (re-exports TrackingStatus + VideoTracking)
    - src/vidscope/ports/repositories.py (VideoTrackingRepository Protocol)
    - src/vidscope/ports/unit_of_work.py (video_tracking: VideoTrackingRepository attr)
    - src/vidscope/ports/__init__.py (re-export VideoTrackingRepository)
    - src/vidscope/adapters/sqlite/schema.py (Table + _ensure + init_db call)
    - src/vidscope/adapters/sqlite/unit_of_work.py (slot + __enter__ instanciation)
    - src/vidscope/cli/commands/__init__.py (review_command)
    - src/vidscope/cli/app.py (app.command("review"))

decisions:
  - "D1 upsert semantics: ON CONFLICT(video_id) DO UPDATE — SetVideoTrackingUseCase.execute fait INSERT OR UPDATE atomique via uow.video_tracking.upsert"
  - "D2 state machine non-enforced: tous les statuts sont valides depuis n'importe quel statut — label workflow, pas un gate"
  - "Open Q3 notes semantics: notes=None preserves existing, notes='' clears, notes=str replaces"
  - "Test slots: TypeError accepte en plus de AttributeError/FrozenInstanceError sur Windows Python 3.12"

metrics:
  duration: ~75min
  tasks_completed: 3
  files_created: 10
  files_modified: 8
  tests_added: 40
---

# Phase M011 Plan S01: Socle VideoTracking Summary

**One-liner:** VideoTracking workflow overlay avec StrEnum 6 statuts, table SQLite UNIQUE/FK/upsert, port Protocol, use case notes-preserving, et CLI `vidscope review`.

## What Was Built

S01 livre le socle complet M011. Sans ces fichiers, S02 (tags+collections) et S03 (facet search) n'auraient ni table ni port à cibler.

### TrackingStatus StrEnum (6 membres exacts)

```python
class TrackingStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    SAVED = "saved"
    ACTIONED = "actioned"
    IGNORED = "ignored"
    ARCHIVED = "archived"
```

Flux typique documenté dans la docstring: `new -> reviewed -> saved|actioned|ignored -> archived`. Aucune transition n'est bloquée (D2 — label, pas gate).

### VideoTracking entity (frozen+slots, ordre des champs)

```python
@dataclass(frozen=True, slots=True)
class VideoTracking:
    video_id: VideoId          # sans default — champs obligatoires en premier
    status: TrackingStatus     # sans default
    starred: bool = False      # defaults
    notes: str | None = None
    id: int | None = None      # DB-assigned, en fin comme VideoStats
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

### DDL finale de la table video_tracking

```sql
CREATE TABLE video_tracking (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id   INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status     VARCHAR(32) NOT NULL DEFAULT 'new',
    starred    BOOLEAN NOT NULL DEFAULT 0,
    notes      TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT uq_video_tracking_video_id UNIQUE (video_id)
);
CREATE INDEX IF NOT EXISTS idx_video_tracking_status ON video_tracking (status);
CREATE INDEX IF NOT EXISTS idx_video_tracking_starred ON video_tracking (starred);
```

Migration idempotente via `_ensure_video_tracking_table(conn)` appelée dans `init_db()` après `_ensure_analysis_v2_columns`.

### Pattern upsert choisi

`ON CONFLICT(video_id) DO UPDATE SET status=excluded.status, starred=excluded.starred, notes=excluded.notes, updated_at=excluded.updated_at`. `created_at` est préservé sur update (non inclus dans le `set_`). Résout Pitfall 3 (IntegrityError sur 2e appel).

`updated_at` est toujours `datetime.now(UTC)` au moment du `upsert()` — jamais repris depuis l'entité entrante sauf pour `created_at` sur le premier insert.

### Notes semantics (Open Q3 résolue)

Dans `SetVideoTrackingUseCase.execute`:
- `notes=None` → preserve: si la ligne existe, `resolved_notes = existing.notes`
- `notes=""` → clear: `resolved_notes = ""`
- `notes="text"` → replace: `resolved_notes = "text"`

### CLI signature finale de `vidscope review`

```
vidscope review <video_id> --status {new|reviewed|saved|actioned|ignored|archived}
                           [--star | --unstar]
                           [--note TEXT]
                           [--clear-note]
```

- `--star/--unstar` sont mutuellement exclusifs via `typer.Option("--star/--unstar")`
- `--note` et `--clear-note` sont mutuellement exclusifs (vérification manuelle avec `raise fail_user(...)`)
- Sortie: `created|updated tracking for video {id}: status=saved, starred, notes='...'`
- Statut invalide → `typer.BadParameter` → exit code 2

### Test de pipeline neutrality — invariant documenté

`test_pipeline_neutrality.py::TestPipelineNeutrality::test_reingest_preserves_tracking`:

1. Ingest video via `uow.videos.upsert_by_platform_id`
2. User crée tracking via `uow.video_tracking.upsert` (status=SAVED, starred=True, notes="important")
3. Re-ingest la même URL via `upsert_by_platform_id` (metadata différentes)
4. Vérifie que `uow.video_tracking.get_for_video` retourne toujours le tracking intact

L'invariant tient car `ON DELETE CASCADE` n'agit que sur `DELETE FROM videos`, jamais sur un upsert de la table `videos` elle-même.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypeError dans test slots sur Windows Python 3.12**

- **Found during:** Task 1 GREEN phase
- **Issue:** Sur Windows avec Python 3.12, assigner un attribut inexistant sur un objet `frozen=True, slots=True` lève `TypeError: super(type, obj): obj must be an instance or subtype of type` au lieu d'`AttributeError` ou `FrozenInstanceError`.
- **Fix:** Test étendu pour accepter `(AttributeError, dataclasses.FrozenInstanceError, TypeError)` dans le `pytest.raises`.
- **Files modified:** `tests/unit/domain/test_video_tracking.py`
- **Commit:** cb4b2a4

**2. [Rule 1 - Bug] UNIQUE index nom non-standard dans PRAGMA index_list**

- **Found during:** Task 2 GREEN phase
- **Issue:** Le test `test_unique_video_id_enforced` vérifiait le nom de l'index par pattern (`"video_id" in name or "uq_video_tracking" in name`), mais SQLite génère automatiquement `sqlite_autoindex_video_tracking_1` pour les contraintes UNIQUE dans les CREATE TABLE.
- **Fix:** Test simplifié pour vérifier `row[2] == 1` (flag unique) sans condition sur le nom.
- **Files modified:** `tests/unit/adapters/sqlite/test_video_tracking_repository.py`
- **Commit:** efdac73

**3. [Scope] Fichiers pré-existants hors M011-S01 non testables dans ce worktree**

- **Context:** Le worktree était basé sur un commit ancien (avant M006-M010 dans la branche worktree). Les fichiers M006+ (Creator, FrameText, etc.) existent dans les sources mais certains tests les référencent avec des imports qui échouent.
- **Action:** Hors scope — ces tests préexistants ne sont pas modifiés par S01. La suite M011-S01 (40 tests) est entièrement verte.

## Known Stubs

Aucun stub. Toutes les fonctionnalités de S01 sont wired end-to-end: domain -> ports -> adapter -> use case -> CLI.

## Threat Flags

Aucune nouvelle surface de sécurité hors plan. Les mitigations T-SQL-M011-01, T-INPUT-M011-01, T-DATA-M011-01, T-STATE-M011-01, T-PIPELINE-M011-01, T-UNIQ-M011-01, T-ARCH-M011-01 du threat model sont toutes couvertes par l'implémentation.

## Self-Check: PASSED

Fichiers créés:
- src/vidscope/domain/values.py — TrackingStatus present: YES
- src/vidscope/domain/entities.py — VideoTracking present: YES
- src/vidscope/adapters/sqlite/video_tracking_repository.py — CREATED: YES
- src/vidscope/application/set_video_tracking.py — CREATED: YES
- src/vidscope/cli/commands/review.py — CREATED: YES
- tests/unit/domain/test_video_tracking.py — CREATED: YES (12 tests)
- tests/unit/adapters/sqlite/test_video_tracking_repository.py — CREATED: YES (14 tests)
- tests/unit/application/test_pipeline_neutrality.py — CREATED: YES (2 tests)
- tests/unit/application/test_set_video_tracking.py — CREATED: YES (6 tests)
- tests/unit/cli/test_review_cmd.py — CREATED: YES (6 tests)

Commits:
- cb4b2a4: feat(M011-S01): Task 1 — VERIFIED
- efdac73: feat(M011-S01): Task 2 — VERIFIED
- 52e2cc7: feat(M011-S01): Task 3 — VERIFIED

Tests: 40 passed, 0 failed
lint-imports: 10 contracts KEPT, 0 broken
