---
phase: M011
plan: S02
subsystem: domain+ports+adapters+application+cli
tags: [tags, collections, many-to-many, sqlite, workflow, cli]
requirements: [R057]

dependency_graph:
  requires: [M011-S01]
  provides: [Tag_entity, Collection_entity, TagRepository_port, CollectionRepository_port, tags_collections_tables, TagRepositorySQLite, CollectionRepositorySQLite, TagVideoUseCase, CreateCollectionUseCase, vidscope_tag_CLI, vidscope_collection_CLI]
  affects: [M011-S03]

tech_stack:
  added: []
  patterns:
    - Tag + Collection frozen+slots entities (name str sans default, id int|None, created_at datetime|None)
    - TagName + CollectionName NewType aliases dans domain/values.py (type-checker seulement)
    - TagRepository @runtime_checkable Protocol avec get_or_create/assign/unassign/list_video_ids_for_tag
    - CollectionRepository @runtime_checkable Protocol avec create/add_video/remove_video/list_video_ids_for_collection
    - Migration idempotente _ensure_tags_collections_tables: ordre tags -> tag_assignments -> collections -> collection_items (Pitfall 2)
    - TagRepositorySQLite: lowercase+strip dans _normalize(), on_conflict_do_nothing sur UNIQUE(name) et UNIQUE(video_id, tag_id)
    - CollectionRepositorySQLite: case-preserved, on_conflict_do_nothing sur UNIQUE(collection_id, video_id)
    - 4 tag use cases + 4 collection use cases (application-pure, InMemory fakes pour tests)
    - CollectionSummary frozen+slots DTO (collection + video_count) pour list command
    - vidscope tag sub-app (Typer) + vidscope collection sub-app (Typer) enregistrées via app.add_typer

key_files:
  created:
    - src/vidscope/adapters/sqlite/tag_repository.py
    - src/vidscope/adapters/sqlite/collection_repository.py
    - src/vidscope/application/tag_video.py
    - src/vidscope/application/collection_library.py
    - src/vidscope/cli/commands/tags.py
    - src/vidscope/cli/commands/collections.py
    - tests/unit/domain/test_tag_collection_entities.py
    - tests/unit/adapters/sqlite/test_tag_repository.py
    - tests/unit/adapters/sqlite/test_collection_repository.py
    - tests/unit/application/test_tag_use_cases.py
    - tests/unit/application/test_collection_use_cases.py
    - tests/unit/cli/test_tags_cmd.py
    - tests/unit/cli/test_collections_cmd.py
  modified:
    - src/vidscope/domain/values.py (TagName + CollectionName NewType + __all__)
    - src/vidscope/domain/entities.py (Tag + Collection entities + __all__)
    - src/vidscope/domain/__init__.py (re-exports Tag + Collection + TagName + CollectionName)
    - src/vidscope/ports/repositories.py (TagRepository + CollectionRepository Protocols + __all__)
    - src/vidscope/ports/unit_of_work.py (tags: TagRepository + collections: CollectionRepository attrs)
    - src/vidscope/ports/__init__.py (re-exports TagRepository + CollectionRepository + __all__)
    - src/vidscope/adapters/sqlite/schema.py (4 tables SQLAlchemy + _ensure_tags_collections_tables + init_db call)
    - src/vidscope/adapters/sqlite/unit_of_work.py (imports + __init__ attrs + __enter__ instantiation)
    - src/vidscope/cli/commands/__init__.py (collection_app + tag_app imports + __all__)
    - src/vidscope/cli/app.py (imports + add_typer registrations)

decisions:
  - "D3 tag normalization: TagRepositorySQLite._normalize() applique .strip().lower() avant tout INSERT/SELECT. UNIQUE(name) en DB opère sur la valeur déjà normalisée."
  - "D3 collection case-preserve: CollectionRepositorySQLite stocke le nom avec casse exacte. Deux collections avec casses différentes sont des lignes distinctes."
  - "Pitfall 2 migration order: _ensure_tags_collections_tables crée dans l'ordre strict tags -> tag_assignments -> collections -> collection_items pour respecter les FK."
  - "CollectionSummary DTO application-layer (frozen+slots) plutôt que domain entity — projection spécifique au use case list."

metrics:
  duration: ~60min
  tasks_completed: 2
  files_created: 13
  files_modified: 10
  tests_added: 55
---

# Phase M011 Plan S02: Tags + Collections Summary

**One-liner:** Tags many-to-many avec normalisation lowercase (D3), Collections case-preserved, 4 tables SQLite FK CASCADE, 8 use cases application-pure, 2 sous-apps CLI (`vidscope tag`, `vidscope collection`), 55 tests verts.

## What Was Built

S02 livre la couche tags+collections complète. S03 peut maintenant filtrer par `--tag X` et `--collection Y` via `TagRepository.list_video_ids_for_tag` et `CollectionRepository.list_video_ids_for_collection`.

### Entités `Tag` et `Collection` (frozen+slots)

```python
@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    id: int | None = None
    created_at: datetime | None = None

@dataclass(frozen=True, slots=True)
class Collection:
    name: str
    id: int | None = None
    created_at: datetime | None = None
```

NewType documentation-only: `TagName = NewType("TagName", str)` et `CollectionName = NewType("CollectionName", str)`.

### DDL des 4 tables (UNIQUE + FK CASCADE)

```sql
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(128) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_tags_name UNIQUE (name)
);

CREATE TABLE tag_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_tag_assignments_video_tag UNIQUE (video_id, tag_id)
);

CREATE TABLE collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_collections_name UNIQUE (name)
);

CREATE TABLE collection_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_collection_items_coll_video UNIQUE (collection_id, video_id)
);
```

Migration idempotente `_ensure_tags_collections_tables(conn)` appelée dans `init_db()` après `_ensure_video_tracking_table`. Ordre strict respecté (Pitfall 2 RESEARCH).

### Pattern de normalisation

**TagName** (lowercase+strip via `_normalize()`):
- `get_or_create("Idea")` → tag name `"idea"`, même ligne que `get_or_create("IDEA")`
- `get_or_create("   ")` → lève `StorageError`
- `on_conflict_do_nothing` sur `UNIQUE(name)` pour les insertions concurrentes

**CollectionName** (case-preserved, D3 RESEARCH):
- `create("Concurrents")` et `create("concurrents")` → 2 lignes distinctes
- `create("X")` puis `create("X")` → lève `StorageError` (UNIQUE violation)

### Interface complète des 2 Protocols

**TagRepository** (`@runtime_checkable`):
```python
def get_or_create(self, name: str) -> Tag: ...
def get_by_name(self, name: str) -> Tag | None: ...
def list_all(self, *, limit: int = 1000) -> list[Tag]: ...
def list_for_video(self, video_id: VideoId) -> list[Tag]: ...
def assign(self, video_id: VideoId, tag_id: int) -> None: ...       # idempotent
def unassign(self, video_id: VideoId, tag_id: int) -> None: ...     # no-op si absent
def list_video_ids_for_tag(self, name: str, *, limit: int = 1000) -> list[VideoId]: ...
```

**CollectionRepository** (`@runtime_checkable`):
```python
def create(self, name: str) -> Collection: ...                       # raise StorageError si dupliqué
def get_by_name(self, name: str) -> Collection | None: ...
def list_all(self, *, limit: int = 1000) -> list[Collection]: ...
def add_video(self, collection_id: int, video_id: VideoId) -> None: ...   # idempotent
def remove_video(self, collection_id: int, video_id: VideoId) -> None: ... # no-op si absent
def list_videos(self, collection_id: int, *, limit: int = 1000) -> list[VideoId]: ...
def list_collections_for_video(self, video_id: VideoId) -> list[Collection]: ...
def list_video_ids_for_collection(self, name: str, *, limit: int = 1000) -> list[VideoId]: ...
```

### 8 use cases

**Tags** (`application/tag_video.py`):
- `TagVideoUseCase.execute(video_id: int, name: str) -> Tag` — get_or_create + assign
- `UntagVideoUseCase.execute(video_id: int, name: str) -> bool` — get_by_name + unassign, retourne False si absent
- `ListTagsUseCase.execute(*, limit: int = 1000) -> list[Tag]`
- `ListVideoTagsUseCase.execute(video_id: int) -> list[Tag]`

**Collections** (`application/collection_library.py`):
- `CreateCollectionUseCase.execute(name: str) -> Collection`
- `AddToCollectionUseCase.execute(collection_name: str, video_id: int) -> Collection` — raise DomainError si collection absente
- `RemoveFromCollectionUseCase.execute(collection_name: str, video_id: int) -> Collection` — raise DomainError si collection absente
- `ListCollectionsUseCase.execute(*, limit: int = 1000) -> list[CollectionSummary]` — avec video_count

### CLI signatures finales

```
vidscope tag --help
vidscope tag add <video_id> <name>       # normalize lowercase, retourne "added tag X to video Y"
vidscope tag remove <video_id> <name>    # retourne "removed" ou "nothing to do"
vidscope tag list                        # tableau Rich: id | name | created
vidscope tag video <video_id>            # liste des tags de la vidéo

vidscope collection --help
vidscope collection create <name>        # case-preserved, retourne "created collection X (id=N)"
vidscope collection add <name> <vid_id>  # retourne "added video N to X"
vidscope collection remove <name> <vid>  # retourne "removed video N from X"
vidscope collection list                 # tableau Rich: id | name | videos | created
vidscope collection show <name>          # liste les video_ids de la collection
```

## Deviations from Plan

Aucune déviation. Plan exécuté exactement tel qu'écrit.

## Known Stubs

Aucun stub. Toutes les fonctionnalités de S02 sont wired end-to-end: domain -> ports -> adapter -> use case -> CLI.

## Threat Flags

Aucune nouvelle surface de sécurité hors plan. Les mitigations T-SQL-M011-02, T-INPUT-M011-02, T-DATA-M011-02, T-DUPE-M011-01, T-CASCADE-M011-01, T-MIG-M011-01, T-ARCH-M011-02 du threat model sont toutes couvertes par l'implémentation.

## Self-Check: PASSED

Fichiers créés:
- src/vidscope/adapters/sqlite/tag_repository.py — class TagRepositorySQLite: YES
- src/vidscope/adapters/sqlite/collection_repository.py — class CollectionRepositorySQLite: YES
- src/vidscope/application/tag_video.py — class TagVideoUseCase: YES
- src/vidscope/application/collection_library.py — class CreateCollectionUseCase: YES
- src/vidscope/cli/commands/tags.py — tag_app = typer.Typer: YES
- src/vidscope/cli/commands/collections.py — collection_app = typer.Typer: YES

Fichiers modifiés:
- src/vidscope/domain/entities.py — class Tag + class Collection: YES
- src/vidscope/ports/repositories.py — class TagRepository + class CollectionRepository: YES
- src/vidscope/ports/unit_of_work.py — tags: TagRepository + collections: CollectionRepository: YES
- src/vidscope/adapters/sqlite/schema.py — _ensure_tags_collections_tables + appel init_db: YES
- src/vidscope/adapters/sqlite/unit_of_work.py — self.tags + self.collections dans __enter__: YES
- src/vidscope/cli/app.py — add_typer(tag_app) + add_typer(collection_app): YES

Commits:
- bf3fcf3: feat(M011-S02): Task 1 — VERIFIED
- be25d2e: feat(M011-S02): Task 2 — VERIFIED

Tests: 55 passed, 0 failed
lint-imports: 10 contracts KEPT, 0 broken
vidscope tag --help: OK
vidscope collection --help: OK
