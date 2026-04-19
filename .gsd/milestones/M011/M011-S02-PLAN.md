---
phase: M011
plan: S02
type: execute
wave: 2
depends_on: [S01]
files_modified:
  - src/vidscope/domain/values.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/tag_repository.py
  - src/vidscope/adapters/sqlite/collection_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/application/tag_video.py
  - src/vidscope/application/collection_library.py
  - src/vidscope/cli/commands/tags.py
  - src/vidscope/cli/commands/collections.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/domain/test_tag_collection_entities.py
  - tests/unit/adapters/sqlite/test_tag_repository.py
  - tests/unit/adapters/sqlite/test_collection_repository.py
  - tests/unit/application/test_tag_use_cases.py
  - tests/unit/application/test_collection_use_cases.py
  - tests/unit/cli/test_tags_cmd.py
  - tests/unit/cli/test_collections_cmd.py
autonomous: true
requirements: [R057]
must_haves:
  truths:
    - "`TagName` NewType str et `CollectionName` NewType str existent dans `vidscope.domain.values` (documentation-only alias pour mypy)"
    - "Entités domain `Tag` (frozen+slots: id int|None, name str, created_at datetime|None) et `Collection` (frozen+slots: id int|None, name str, created_at datetime|None) livrées dans `vidscope.domain.entities`"
    - "Port `TagRepository` Protocol @runtime_checkable avec: `get_or_create(name)`, `get_by_name(name)`, `list_all(*, limit=1000)`, `list_for_video(video_id)`, `assign(video_id, tag_id)`, `unassign(video_id, tag_id)`, `list_video_ids_for_tag(name)`"
    - "Port `CollectionRepository` Protocol @runtime_checkable avec: `create(name)`, `get_by_name(name)`, `list_all(*, limit=1000)`, `add_video(collection_id, video_id)`, `remove_video(collection_id, video_id)`, `list_videos(collection_id, *, limit=1000)`, `list_collections_for_video(video_id)`, `list_video_ids_for_collection(name)`"
    - "`UnitOfWork` Protocol déclare `tags: TagRepository` et `collections: CollectionRepository`"
    - "Migration `_ensure_tags_collections_tables(conn)` crée 4 tables dans l'ordre: `tags`, `tag_assignments`, `collections`, `collection_items` (Pitfall 2) — toutes UNIQUE appropriées, FK CASCADE"
    - "`init_db()` appelle `_ensure_tags_collections_tables(conn)` APRÈS `_ensure_video_tracking_table(conn)`"
    - "Tag name normalisation: `TagRepositorySQLite.get_or_create('Idea')`, `get_or_create('IDEA')`, `get_or_create('idea')` retournent la MÊME ligne (lowercase strip via `.lower().strip()` avant INSERT/SELECT)"
    - "Collection name est UNIQUE global (pas de normalisation — Collection names sont user-facing et case-sensitive per D3 research)"
    - "`SqliteUnitOfWork` instancie `self.tags` et `self.collections` dans `__enter__`"
    - "4 use cases tag: `TagVideoUseCase`, `UntagVideoUseCase`, `ListTagsUseCase`, `ListVideoTagsUseCase`"
    - "4 use cases collection: `CreateCollectionUseCase`, `AddToCollectionUseCase`, `RemoveFromCollectionUseCase`, `ListCollectionsUseCase`"
    - "CLI `vidscope tag` sub-app avec sous-commandes: `add <video_id> <name>`, `remove <video_id> <name>`, `list`, `video <video_id>`"
    - "CLI `vidscope collection` sub-app avec sous-commandes: `create <name>`, `add <collection_name> <video_id>`, `remove <collection_name> <video_id>`, `list`, `show <collection_name>`"
    - "Delete cascade vérifié: DELETE videos row → `tag_assignments` et `collection_items` rows supprimés; DELETE tags row → `tag_assignments` supprimé; DELETE collections row → `collection_items` supprimé"
  artifacts:
    - path: "src/vidscope/domain/entities.py"
      provides: "Tag + Collection entities"
      contains: "class Collection"
    - path: "src/vidscope/ports/repositories.py"
      provides: "TagRepository + CollectionRepository Protocols"
      contains: "class CollectionRepository"
    - path: "src/vidscope/adapters/sqlite/schema.py"
      provides: "4 tables: tags, tag_assignments, collections, collection_items"
      contains: "_ensure_tags_collections_tables"
    - path: "src/vidscope/adapters/sqlite/tag_repository.py"
      provides: "TagRepositorySQLite (lowercase normalization)"
      contains: "class TagRepositorySQLite"
    - path: "src/vidscope/adapters/sqlite/collection_repository.py"
      provides: "CollectionRepositorySQLite"
      contains: "class CollectionRepositorySQLite"
    - path: "src/vidscope/application/tag_video.py"
      provides: "4 tag use cases"
      contains: "class TagVideoUseCase"
    - path: "src/vidscope/application/collection_library.py"
      provides: "4 collection use cases"
      contains: "class CreateCollectionUseCase"
    - path: "src/vidscope/cli/commands/tags.py"
      provides: "vidscope tag sub-app"
      contains: "tag_app = typer.Typer"
    - path: "src/vidscope/cli/commands/collections.py"
      provides: "vidscope collection sub-app"
      contains: "collection_app = typer.Typer"
  key_links:
    - from: "src/vidscope/adapters/sqlite/schema.py"
      to: "_ensure_tags_collections_tables"
      via: "Appel depuis init_db() après _ensure_video_tracking_table"
      pattern: "_ensure_tags_collections_tables\\(conn\\)"
    - from: "src/vidscope/adapters/sqlite/unit_of_work.py"
      to: "TagRepositorySQLite + CollectionRepositorySQLite"
      via: "Instanciation dans __enter__"
      pattern: "TagRepositorySQLite\\(self\\._connection\\)"
    - from: "src/vidscope/cli/app.py"
      to: "tag_app + collection_app"
      via: "app.add_typer(tag_app, name='tag') + app.add_typer(collection_app, name='collection')"
      pattern: "add_typer\\(tag_app"
    - from: "src/vidscope/adapters/sqlite/tag_repository.py"
      to: "TagName lowercase normalization"
      via: ".lower().strip() appliqué dans get_or_create et get_by_name"
      pattern: "\\.lower\\(\\)\\.strip\\(\\)"
---

<objective>
S02 livre les mécaniques tags et collections : entités `Tag`/`Collection`, 4 tables SQLite (tags, tag_assignments, collections, collection_items) avec relations many-to-many, adaptateurs SQLite avec normalisation lowercase des tags (D3 RESEARCH), 8 use cases (4 tag + 4 collection), 2 sous-apps CLI (`vidscope tag` et `vidscope collection`). Dépend de S01 pour l'extension de l'UoW (S01 a ajouté `video_tracking`, S02 ajoute `tags` et `collections`).

Purpose: S03 aura besoin de filtrer par `--tag X` et `--collection Y`. S02 construit l'ossature de données et d'API nécessaire. Avec S01 (tracking) + S02 (tags+collections), l'utilisateur peut annoter tout le workflow personnel d'une vidéo: status + starred + notes + tags + collection membership.
Output: Domain étendu (Tag + Collection), port/adapters, 4 tables SQLite avec UNIQUE et FK CASCADE, 8 use cases, 2 sous-apps CLI.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M011/M011-ROADMAP.md
@.gsd/milestones/M011/M011-RESEARCH.md
@.gsd/milestones/M011/M011-VALIDATION.md
@.gsd/milestones/M011/M011-S01-PLAN.md
@src/vidscope/domain/values.py
@src/vidscope/domain/entities.py
@src/vidscope/ports/repositories.py
@src/vidscope/ports/unit_of_work.py
@src/vidscope/adapters/sqlite/schema.py
@src/vidscope/adapters/sqlite/unit_of_work.py
@src/vidscope/adapters/sqlite/video_stats_repository.py
@src/vidscope/adapters/sqlite/watch_account_repository.py
@src/vidscope/application/search_videos.py
@src/vidscope/cli/commands/watch.py
@src/vidscope/cli/commands/cookies.py
@src/vidscope/cli/app.py

<interfaces>
Patterns DÉJÀ livrés en S01 (à étendre similaire):

**Entity pattern (VideoTracking livrée en S01)**:
```python
@dataclass(frozen=True, slots=True)
class VideoTracking:
    video_id: VideoId
    status: TrackingStatus
    starred: bool = False
    ...
```

**Port pattern**: VideoTrackingRepository est le modèle direct. Appliquer la même structure.

**Migration pattern (schema.py après S01)**:
Après S01, init_db appelle `_ensure_video_tracking_table`. S02 ajoute un appel après.

**Many-to-many SQL pattern (RESEARCH Code Examples)**:
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

**Sub-app CLI pattern (cli/commands/watch.py + cli/commands/cookies.py livrés)**:
```python
tag_app = typer.Typer(
    name="tag",
    help="...",
    no_args_is_help=True,
    add_completion=False,
)

@tag_app.command("add")
def tag_add(video_id: int, name: str) -> None:
    with handle_domain_errors():
        container = acquire_container()
        use_case = TagVideoUseCase(unit_of_work_factory=container.unit_of_work)
        use_case.execute(video_id, name)
```

Enregistrement dans app.py via `app.add_typer(tag_app, name="tag")`.

**UoW extension pattern (livré en S01 avec video_tracking)**: ajouter 2 attributs dans le Protocol + 2 instances dans __enter__.

**TagName normalization pattern (D3 RESEARCH)**:
```python
def get_or_create(self, name: str) -> Tag:
    normalized = name.lower().strip()
    if not normalized:
        raise ValueError("tag name cannot be empty or whitespace-only")
    # SELECT ... WHERE name = normalized ; if miss, INSERT
```

**Many-to-many subquery pattern (analysis_repository.py pour S03 preview)**:
```python
tag_subq = (
    select(tag_assignments_table.c.video_id)
    .join(tags_table, tags_table.c.id == tag_assignments_table.c.tag_id)
    .where(tags_table.c.name == tag)
)
```

**Application use case discipline**: 1 fichier par groupe métier ou 1 fichier par use case — choisir une convention. Ici regroupés: `tag_video.py` contient 4 use cases tag, `collection_library.py` contient 4 use cases collection. Pattern: __init__ prend `unit_of_work_factory`, execute() method, retourne dataclass frozen result si nécessaire.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Tag + Collection entities + ports + Migration SQLite + Adapters SQLite + UoW extension</name>
  <files>src/vidscope/domain/values.py, src/vidscope/domain/entities.py, src/vidscope/domain/__init__.py, src/vidscope/ports/repositories.py, src/vidscope/ports/unit_of_work.py, src/vidscope/ports/__init__.py, src/vidscope/adapters/sqlite/schema.py, src/vidscope/adapters/sqlite/tag_repository.py, src/vidscope/adapters/sqlite/collection_repository.py, src/vidscope/adapters/sqlite/unit_of_work.py, tests/unit/domain/test_tag_collection_entities.py, tests/unit/adapters/sqlite/test_tag_repository.py, tests/unit/adapters/sqlite/test_collection_repository.py</files>
  <read_first>
    - src/vidscope/domain/values.py (après S01: contient TrackingStatus — ajouter NewType aliases)
    - src/vidscope/domain/entities.py (après S01: contient VideoTracking)
    - src/vidscope/ports/repositories.py (après S01: contient VideoTrackingRepository — miroir du pattern)
    - src/vidscope/ports/unit_of_work.py (après S01: contient video_tracking attr)
    - src/vidscope/adapters/sqlite/schema.py (après S01: contient _ensure_video_tracking_table)
    - src/vidscope/adapters/sqlite/video_stats_repository.py (pattern repository: _entity_to_row helpers, int() casts)
    - src/vidscope/adapters/sqlite/watch_account_repository.py (pattern list_all, get_by_name, exists)
    - src/vidscope/adapters/sqlite/unit_of_work.py (après S01: contient video_tracking instantiation)
    - .gsd/milestones/M011/M011-RESEARCH.md (Code Examples many-to-many SQL + D3 tag normalization + Pitfall 2 migration order + Pitfall 4 case sensitivity)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 11 S02: 3 entities + 6 use cases CLI — on simplifie à `Tag + Collection` 2 entities + `CollectionItem` row-only)
  </read_first>
  <behavior>
    - Test 1: `Tag(id=None, name="idea")` construit, frozen+slots, re-exporté depuis `vidscope.domain`.
    - Test 2: `Collection(id=None, name="Concurrents Shopify")` construit, frozen+slots.
    - Test 3: `from vidscope.ports import TagRepository, CollectionRepository` fonctionne; les deux sont `@runtime_checkable`.
    - Test 4: `UnitOfWork.__annotations__` contient `tags` ET `collections`.
    - Test 5: Après `init_db`, les 4 tables existent: `tags`, `tag_assignments`, `collections`, `collection_items` (via sqlite_master).
    - Test 6: Chaque table a la contrainte UNIQUE attendue (`tags.name`, `tag_assignments(video_id, tag_id)`, `collections.name`, `collection_items(collection_id, video_id)`).
    - Test 7: `_ensure_tags_collections_tables` est idempotent: appeler deux fois ne lève pas.
    - Test 8: `TagRepositorySQLite.get_or_create("Idea")` renvoie un Tag avec `name="idea"` (lowercased); `get_or_create("IDEA")` retourne le MÊME tag (même id).
    - Test 9: `TagRepositorySQLite.get_or_create("   ")` lève `DomainError` / `ValueError` (nom vide après strip).
    - Test 10: `TagRepositorySQLite.list_all()` renvoie les tags triés alphabétiquement par nom; `list_for_video(video_id)` renvoie les tags assignés à cette vidéo.
    - Test 11: `TagRepositorySQLite.assign(video_id, tag_id)` ajoute une ligne dans tag_assignments; appeler 2x avec les mêmes IDs est idempotent (`INSERT OR IGNORE` ou équivalent).
    - Test 12: `TagRepositorySQLite.unassign(video_id, tag_id)` supprime la ligne; no-op si absent.
    - Test 13: `TagRepositorySQLite.list_video_ids_for_tag("idea")` renvoie les VideoId qui ont ce tag (utilisé par S03).
    - Test 14: `CollectionRepositorySQLite.create("Concurrents Shopify")` crée et retourne Collection; un 2e appel avec le même nom lève `StorageError` (UNIQUE violation).
    - Test 15: Collection names NE SONT PAS normalisés (D3 research): `create("Concurrents")` et `create("concurrents")` créent 2 lignes distinctes.
    - Test 16: `CollectionRepositorySQLite.add_video(coll_id, vid_id)` crée une ligne collection_items; idempotent (same coll+vid 2x = OK no duplicate).
    - Test 17: `CollectionRepositorySQLite.remove_video(coll_id, vid_id)` supprime; no-op si absent.
    - Test 18: `list_videos(coll_id)` renvoie les VideoId, `list_collections_for_video(vid_id)` renvoie les Collection, `list_video_ids_for_collection("Name")` renvoie VideoId (pour S03).
    - Test 19: DELETE video row cascade supprime les lignes tag_assignments et collection_items liées.
    - Test 20: DELETE tag row cascade supprime tag_assignments liées; DELETE collection row cascade supprime collection_items liées.
    - Test 21: `SqliteUnitOfWork.__enter__` expose `uow.tags` (TagRepositorySQLite) et `uow.collections` (CollectionRepositorySQLite).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/domain/values.py` :

(a) Ajouter APRÈS `VideoId = NewType(...)` (vers fin du fichier) :
```python
TagName = NewType("TagName", str)
"""Lowercase, stripped tag name. Normalisation enforced by the
TagRepository.get_or_create. Using NewType keeps the value distinct
from arbitrary str at the type-checker level (D3 M011 RESEARCH)."""

CollectionName = NewType("CollectionName", str)
"""User-facing collection name. Case-preserved (D3 M011 RESEARCH) —
unlike TagName, the DB stores "Concurrents" and "concurrents" as
distinct rows."""
```

(b) Ajouter `"CollectionName"` et `"TagName"` au `__all__` (tri alphabétique).

Étape 2 — Étendre `src/vidscope/domain/entities.py` :

(a) Ajouter les 2 entities APRÈS `VideoTracking` (livré en S01), AVANT `WatchedAccount` :

```python
@dataclass(frozen=True, slots=True)
class Tag:
    """User tag applied to videos (M011/S02/R057).

    Tags are a global namespace (no per-user scoping — R032 single-user
    tool). ``name`` is always lowercase-stripped by the repository on
    insert/lookup (D3 M011 RESEARCH). Uniqueness enforced at the DB
    level by UNIQUE(name).
    """

    name: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Collection:
    """User-curated collection of videos (M011/S02/R057).

    Collections are named groupings (e.g. "Concurrents Shopify").
    Unlike :class:`Tag`, collection ``name`` is case-preserved — two
    collections with different casing are distinct rows.
    """

    name: str
    id: int | None = None
    created_at: datetime | None = None
```

(b) Ajouter `"Collection"` et `"Tag"` au `__all__` (tri alphabétique dans la section entities).

Étape 3 — Étendre `src/vidscope/domain/__init__.py` :

(a) Dans l'import depuis `entities`, ajouter `Collection` et `Tag` (tri alphabétique).

(b) Dans l'import depuis `values`, ajouter `CollectionName` et `TagName` (tri alphabétique).

(c) Dans `__all__`, ajouter `"Collection"` et `"Tag"` dans la section entities, `"CollectionName"` et `"TagName"` dans la section values.

Étape 4 — Étendre `src/vidscope/ports/repositories.py` :

(a) Dans l'import depuis `vidscope.domain`, ajouter `Collection`, `CollectionName`, `Tag`, `TagName` (tri alphabétique).

(b) Ajouter `"CollectionRepository"` et `"TagRepository"` à `__all__` (tri alphabétique).

(c) Ajouter les 2 Protocols à la FIN du fichier (après `VideoTrackingRepository` livré en S01) :

```python
@runtime_checkable
class TagRepository(Protocol):
    """Persistence for :class:`Tag` rows + many-to-many ``tag_assignments``.

    Tag names are normalised to lowercase-stripped in this layer
    (D3 M011 RESEARCH). UNIQUE(name) at DB level prevents duplicates.
    """

    def get_or_create(self, name: str) -> Tag:
        """Return the :class:`Tag` row for ``name`` (lowercased, stripped).

        Creates the row if it does not exist. Raises ``ValueError`` if
        ``name`` is empty after stripping.
        """
        ...

    def get_by_name(self, name: str) -> Tag | None:
        """Return the :class:`Tag` matching ``name`` (lowercased) or ``None``."""
        ...

    def list_all(self, *, limit: int = 1000) -> list[Tag]:
        """Return every tag ordered by ``name`` ascending."""
        ...

    def list_for_video(self, video_id: VideoId) -> list[Tag]:
        """Return tags assigned to ``video_id``, ordered by name ascending."""
        ...

    def assign(self, video_id: VideoId, tag_id: int) -> None:
        """Assign ``tag_id`` to ``video_id``. Idempotent — re-assigning is a no-op."""
        ...

    def unassign(self, video_id: VideoId, tag_id: int) -> None:
        """Remove the assignment if present. No-op if absent."""
        ...

    def list_video_ids_for_tag(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        """Return every video_id tagged with ``name`` (lowercased).

        Used by :class:`SearchVideosUseCase` in S03 to compute the tag
        facet intersection set.
        """
        ...


@runtime_checkable
class CollectionRepository(Protocol):
    """Persistence for :class:`Collection` + many-to-many ``collection_items``."""

    def create(self, name: str) -> Collection:
        """Create a new collection. Raises ``StorageError`` if the name
        already exists (UNIQUE violation). Name is case-preserved (D3)."""
        ...

    def get_by_name(self, name: str) -> Collection | None:
        """Return the :class:`Collection` matching ``name`` exactly or ``None``."""
        ...

    def list_all(self, *, limit: int = 1000) -> list[Collection]:
        """Return every collection ordered by ``name`` ascending."""
        ...

    def add_video(self, collection_id: int, video_id: VideoId) -> None:
        """Add ``video_id`` to the collection. Idempotent — re-adding is a no-op."""
        ...

    def remove_video(self, collection_id: int, video_id: VideoId) -> None:
        """Remove the membership if present. No-op if absent."""
        ...

    def list_videos(
        self, collection_id: int, *, limit: int = 1000
    ) -> list[VideoId]:
        """Return video_ids in the collection, ordered by membership
        created_at descending (most-recently-added first)."""
        ...

    def list_collections_for_video(self, video_id: VideoId) -> list[Collection]:
        """Return collections containing ``video_id`` ordered by name asc."""
        ...

    def list_video_ids_for_collection(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        """Return every video_id in the collection named ``name``.

        Used by :class:`SearchVideosUseCase` in S03 for the collection facet.
        """
        ...
```

Étape 5 — Étendre `src/vidscope/ports/unit_of_work.py` :

(a) Dans l'import depuis repositories, ajouter `CollectionRepository` et `TagRepository` (tri alphabétique).

(b) Dans la classe `UnitOfWork`, ajouter APRÈS `video_tracking: VideoTrackingRepository` (livré en S01) :
```python
    tags: TagRepository
    collections: CollectionRepository
```

Étape 6 — Étendre `src/vidscope/ports/__init__.py` :

Ajouter `CollectionRepository` et `TagRepository` dans l'import + `__all__` (tri alphabétique).

Étape 7 — Étendre `src/vidscope/adapters/sqlite/schema.py` :

(a) Ajouter les 4 Tables SQLAlchemy Core APRÈS `video_tracking` (livré en S01) et AVANT la section FTS5 DDL :

```python
# M011/S02: tag namespace + many-to-many tag_assignments.
tags = Table(
    "tags",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("name", name="uq_tags_name"),
)

tag_assignments = Table(
    "tag_assignments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tag_id",
        Integer,
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("video_id", "tag_id", name="uq_tag_assignments_video_tag"),
)

# M011/S02: user-curated collections + many-to-many collection_items.
collections = Table(
    "collections",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("name", name="uq_collections_name"),
)

collection_items = Table(
    "collection_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "collection_id",
        Integer,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("collection_id", "video_id", name="uq_collection_items_coll_video"),
)
```

(b) Ajouter les 4 noms dans `__all__` (tri alphabétique): `"collection_items"`, `"collections"`, `"tag_assignments"`, `"tags"`.

(c) Ajouter la fonction migration APRÈS `_ensure_video_tracking_table` (livré en S01) et AVANT la ligne `Row = dict[str, Any]` :

```python
def _ensure_tags_collections_tables(conn: Connection) -> None:
    """M011/S02 migration: create tags + tag_assignments + collections +
    collection_items if absent. Idempotent.

    Created in strict order (Pitfall 2): tags, tag_assignments,
    collections, collection_items. Order matters because
    tag_assignments and collection_items have FKs to the preceding tables.
    """
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }

    if "tags" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE tags (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       VARCHAR(128) NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_tags_name UNIQUE (name)
                )
                """
            )
        )

    if "tag_assignments" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE tag_assignments (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id   INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_tag_assignments_video_tag UNIQUE (video_id, tag_id)
                )
                """
            )
        )

    if "collections" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE collections (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       VARCHAR(255) NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_collections_name UNIQUE (name)
                )
                """
            )
        )

    if "collection_items" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE collection_items (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                    video_id      INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                    created_at    DATETIME NOT NULL,
                    CONSTRAINT uq_collection_items_coll_video UNIQUE (collection_id, video_id)
                )
                """
            )
        )

    # Indexes (idempotent via IF NOT EXISTS)
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_tag_assignments_video_id "
            "ON tag_assignments (video_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_tag_assignments_tag_id "
            "ON tag_assignments (tag_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_collection_items_collection_id "
            "ON collection_items (collection_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_collection_items_video_id "
            "ON collection_items (video_id)"
        )
    )
```

(d) Modifier `init_db()` pour appeler la nouvelle migration APRÈS `_ensure_video_tracking_table` :
```python
def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
        _ensure_analysis_v2_columns(conn)
        _ensure_video_tracking_table(conn)
        _ensure_tags_collections_tables(conn)   # <-- M011/S02
```

Étape 8 — Créer `src/vidscope/adapters/sqlite/tag_repository.py` :

```python
"""SQLite implementation of :class:`TagRepository` (M011/S02/R057).

Tag names are normalised to lowercase-stripped before INSERT/SELECT.
UNIQUE(name) at the DB level prevents duplicates.

Security (T-SQL-M011-02): all queries use SQLAlchemy Core parameterised
binds. No string interpolation, no f-strings inside execute().
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import (
    tag_assignments as tag_assignments_table,
)
from vidscope.adapters.sqlite.schema import tags as tags_table
from vidscope.domain import Tag, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["TagRepositorySQLite"]


def _normalize(name: str) -> str:
    """Lowercase + strip. Empty result is a domain error (caller raises)."""
    return name.strip().lower()


class TagRepositorySQLite:
    """Repository for :class:`Tag` and tag_assignments backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Tag CRUD
    # ------------------------------------------------------------------

    def get_or_create(self, name: str) -> Tag:
        normalized = _normalize(name)
        if not normalized:
            raise StorageError(
                f"tag name cannot be empty or whitespace-only (got {name!r})"
            )
        # Try to SELECT first (happy path avoids ON CONFLICT)
        existing = self.get_by_name(normalized)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        stmt = sqlite_insert(tags_table).values(name=normalized, created_at=now)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        self._conn.execute(stmt)
        # Re-fetch (insert may have been a no-op if a concurrent writer won)
        row = (
            self._conn.execute(
                select(tags_table).where(tags_table.c.name == normalized)
            )
            .mappings()
            .first()
        )
        if row is None:  # pragma: no cover
            raise StorageError(f"tag {normalized!r} missing after insert")
        return _row_to_tag(dict(row))

    def get_by_name(self, name: str) -> Tag | None:
        normalized = _normalize(name)
        if not normalized:
            return None
        row = (
            self._conn.execute(
                select(tags_table).where(tags_table.c.name == normalized)
            )
            .mappings()
            .first()
        )
        return _row_to_tag(dict(row)) if row else None

    def list_all(self, *, limit: int = 1000) -> list[Tag]:
        rows = (
            self._conn.execute(
                select(tags_table)
                .order_by(tags_table.c.name.asc())
                .limit(max(1, int(limit)))
            )
            .mappings()
            .all()
        )
        return [_row_to_tag(dict(r)) for r in rows]

    def list_for_video(self, video_id: VideoId) -> list[Tag]:
        stmt = (
            select(tags_table)
            .join(
                tag_assignments_table,
                tag_assignments_table.c.tag_id == tags_table.c.id,
            )
            .where(tag_assignments_table.c.video_id == int(video_id))
            .order_by(tags_table.c.name.asc())
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_tag(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # tag_assignments (many-to-many)
    # ------------------------------------------------------------------

    def assign(self, video_id: VideoId, tag_id: int) -> None:
        now = datetime.now(UTC)
        stmt = sqlite_insert(tag_assignments_table).values(
            video_id=int(video_id), tag_id=int(tag_id), created_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["video_id", "tag_id"]
        )
        self._conn.execute(stmt)

    def unassign(self, video_id: VideoId, tag_id: int) -> None:
        stmt = delete(tag_assignments_table).where(
            (tag_assignments_table.c.video_id == int(video_id))
            & (tag_assignments_table.c.tag_id == int(tag_id))
        )
        self._conn.execute(stmt)

    def list_video_ids_for_tag(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        normalized = _normalize(name)
        if not normalized:
            return []
        stmt = (
            select(tag_assignments_table.c.video_id)
            .join(tags_table, tags_table.c.id == tag_assignments_table.c.tag_id)
            .where(tags_table.c.name == normalized)
            .order_by(tag_assignments_table.c.created_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).all()
        return [VideoId(int(r[0])) for r in rows]


def _row_to_tag(row: dict[str, Any]) -> Tag:
    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return Tag(
        id=int(row["id"]),
        name=str(row["name"]),
        created_at=created_at,
    )
```

Étape 9 — Créer `src/vidscope/adapters/sqlite/collection_repository.py` :

```python
"""SQLite implementation of :class:`CollectionRepository` (M011/S02/R057).

Collection names are case-preserved (D3 M011 RESEARCH — unlike tags).
UNIQUE(name) at DB level is case-sensitive by default on SQLite.

Security (T-SQL-M011-02): all queries use SQLAlchemy Core binds.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import (
    collection_items as collection_items_table,
)
from vidscope.adapters.sqlite.schema import collections as collections_table
from vidscope.domain import Collection, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["CollectionRepositorySQLite"]


class CollectionRepositorySQLite:
    """Repository for :class:`Collection` + collection_items backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Collection CRUD
    # ------------------------------------------------------------------

    def create(self, name: str) -> Collection:
        stripped = name.strip()
        if not stripped:
            raise StorageError("collection name cannot be empty or whitespace-only")

        now = datetime.now(UTC)
        try:
            result = self._conn.execute(
                collections_table.insert().values(name=stripped, created_at=now)
            )
        except Exception as exc:  # IntegrityError on UNIQUE violation
            raise StorageError(
                f"collection {stripped!r} already exists or DB error: {exc}",
                cause=exc,
            ) from exc

        inserted_id = result.inserted_primary_key
        if not inserted_id or inserted_id[0] is None:  # pragma: no cover
            raise StorageError(f"insert returned no id for collection {stripped!r}")
        return Collection(id=int(inserted_id[0]), name=stripped, created_at=now)

    def get_by_name(self, name: str) -> Collection | None:
        stripped = name.strip()
        if not stripped:
            return None
        row = (
            self._conn.execute(
                select(collections_table).where(collections_table.c.name == stripped)
            )
            .mappings()
            .first()
        )
        return _row_to_collection(dict(row)) if row else None

    def list_all(self, *, limit: int = 1000) -> list[Collection]:
        rows = (
            self._conn.execute(
                select(collections_table)
                .order_by(collections_table.c.name.asc())
                .limit(max(1, int(limit)))
            )
            .mappings()
            .all()
        )
        return [_row_to_collection(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # collection_items (membership)
    # ------------------------------------------------------------------

    def add_video(self, collection_id: int, video_id: VideoId) -> None:
        now = datetime.now(UTC)
        stmt = sqlite_insert(collection_items_table).values(
            collection_id=int(collection_id),
            video_id=int(video_id),
            created_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["collection_id", "video_id"]
        )
        self._conn.execute(stmt)

    def remove_video(self, collection_id: int, video_id: VideoId) -> None:
        stmt = delete(collection_items_table).where(
            (collection_items_table.c.collection_id == int(collection_id))
            & (collection_items_table.c.video_id == int(video_id))
        )
        self._conn.execute(stmt)

    def list_videos(
        self, collection_id: int, *, limit: int = 1000
    ) -> list[VideoId]:
        stmt = (
            select(collection_items_table.c.video_id)
            .where(collection_items_table.c.collection_id == int(collection_id))
            .order_by(collection_items_table.c.created_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).all()
        return [VideoId(int(r[0])) for r in rows]

    def list_collections_for_video(
        self, video_id: VideoId
    ) -> list[Collection]:
        stmt = (
            select(collections_table)
            .join(
                collection_items_table,
                collection_items_table.c.collection_id == collections_table.c.id,
            )
            .where(collection_items_table.c.video_id == int(video_id))
            .order_by(collections_table.c.name.asc())
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_collection(dict(r)) for r in rows]

    def list_video_ids_for_collection(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        stripped = name.strip()
        if not stripped:
            return []
        stmt = (
            select(collection_items_table.c.video_id)
            .join(
                collections_table,
                collections_table.c.id == collection_items_table.c.collection_id,
            )
            .where(collections_table.c.name == stripped)
            .order_by(collection_items_table.c.created_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).all()
        return [VideoId(int(r[0])) for r in rows]


def _row_to_collection(row: dict[str, Any]) -> Collection:
    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return Collection(
        id=int(row["id"]),
        name=str(row["name"]),
        created_at=created_at,
    )
```

Étape 10 — Étendre `src/vidscope/adapters/sqlite/unit_of_work.py` :

(a) Ajouter imports (tri alphabétique) :
```python
from vidscope.adapters.sqlite.collection_repository import (
    CollectionRepositorySQLite,
)
from vidscope.adapters.sqlite.tag_repository import TagRepositorySQLite
```

(b) Dans l'import `from vidscope.ports import (...)`, ajouter `CollectionRepository`, `TagRepository` (tri alphabétique).

(c) Dans `SqliteUnitOfWork.__init__`, ajouter APRÈS `self.video_tracking: VideoTrackingRepository` :
```python
        self.tags: TagRepository
        self.collections: CollectionRepository
```

(d) Dans `SqliteUnitOfWork.__enter__`, ajouter APRÈS `self.video_tracking = VideoTrackingRepositorySQLite(...)` :
```python
        self.tags = TagRepositorySQLite(self._connection)
        self.collections = CollectionRepositorySQLite(self._connection)
```

Étape 11 — Créer les 3 fichiers de tests.

(a) `tests/unit/domain/test_tag_collection_entities.py` :

```python
"""Tag + Collection entities (M011/S02/R057)."""
from __future__ import annotations

import dataclasses

import pytest

from vidscope.domain import Collection, Tag


class TestTagEntity:
    def test_minimal(self) -> None:
        t = Tag(name="idea")
        assert t.name == "idea"
        assert t.id is None

    def test_frozen(self) -> None:
        t = Tag(name="idea")
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.name = "other"  # type: ignore[misc]


class TestCollectionEntity:
    def test_minimal(self) -> None:
        c = Collection(name="Concurrents")
        assert c.name == "Concurrents"
        assert c.id is None

    def test_frozen(self) -> None:
        c = Collection(name="X")
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.name = "Y"  # type: ignore[misc]


class TestPortReExports:
    def test_tag_repo_importable(self) -> None:
        from vidscope.ports import TagRepository
        assert getattr(TagRepository, "_is_runtime_protocol", False) is True

    def test_collection_repo_importable(self) -> None:
        from vidscope.ports import CollectionRepository
        assert getattr(CollectionRepository, "_is_runtime_protocol", False) is True

    def test_uow_has_tags_and_collections(self) -> None:
        from vidscope.ports import UnitOfWork
        anns = UnitOfWork.__annotations__
        assert "tags" in anns
        assert "collections" in anns
```

(b) `tests/unit/adapters/sqlite/test_tag_repository.py` :

```python
"""TagRepositorySQLite (M011/S02/R057)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.tag_repository import TagRepositorySQLite
from vidscope.domain import VideoId
from vidscope.domain.errors import StorageError


def _insert_video(engine: Engine, platform_id: str) -> int:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO videos (platform, platform_id, url, created_at) "
                 "VALUES ('youtube', :pid, :u, :c)"),
            {"pid": platform_id, "u": f"https://y.be/{platform_id}",
             "c": datetime.now(UTC)},
        )
        return int(conn.execute(
            text("SELECT id FROM videos WHERE platform_id=:pid"),
            {"pid": platform_id},
        ).scalar())


class TestTagMigration:
    def test_tables_exist(self, engine: Engine) -> None:
        with engine.connect() as conn:
            names = {row[0] for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )}
        assert "tags" in names
        assert "tag_assignments" in names

    def test_idempotent_migration(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.schema import _ensure_tags_collections_tables
        with engine.begin() as conn:
            _ensure_tags_collections_tables(conn)
            _ensure_tags_collections_tables(conn)


class TestGetOrCreate:
    def test_creates_new(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
        assert t.name == "idea"
        assert t.id is not None

    def test_normalizes_case_and_whitespace(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t1 = repo.get_or_create("Idea")
            t2 = repo.get_or_create("IDEA")
            t3 = repo.get_or_create("  idea  ")
        assert t1.id == t2.id == t3.id
        assert t1.name == "idea"

    def test_empty_name_raises(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            with pytest.raises(StorageError):
                repo.get_or_create("   ")
            with pytest.raises(StorageError):
                repo.get_or_create("")


class TestListAndFindTag:
    def test_list_all_sorted(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            repo.get_or_create("zeta")
            repo.get_or_create("alpha")
            repo.get_or_create("mu")
            tags = repo.list_all()
        names = [t.name for t in tags]
        assert names == sorted(names)

    def test_get_by_name_none_when_absent(self, engine: Engine) -> None:
        with engine.connect() as conn:
            repo = TagRepositorySQLite(conn)
            assert repo.get_by_name("nonexistent") is None


class TestAssignUnassign:
    def test_assign_idempotent(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta1")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
            assert t.id is not None
            repo.assign(VideoId(vid), t.id)
            repo.assign(VideoId(vid), t.id)  # idempotent
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM tag_assignments "
                     "WHERE video_id=:v AND tag_id=:t"),
                {"v": vid, "t": t.id},
            ).scalar()
        assert n == 1

    def test_unassign_noop_when_absent(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta2")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
            assert t.id is not None
            repo.unassign(VideoId(vid), t.id)  # no-op, no error

    def test_list_for_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta3")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t1 = repo.get_or_create("idea")
            t2 = repo.get_or_create("reuse")
            assert t1.id is not None and t2.id is not None
            repo.assign(VideoId(vid), t1.id)
            repo.assign(VideoId(vid), t2.id)
            tags = repo.list_for_video(VideoId(vid))
        names = {t.name for t in tags}
        assert names == {"idea", "reuse"}

    def test_list_video_ids_for_tag(self, engine: Engine) -> None:
        v1 = _insert_video(engine, "ta4")
        v2 = _insert_video(engine, "ta5")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("hook")
            assert t.id is not None
            repo.assign(VideoId(v1), t.id)
            repo.assign(VideoId(v2), t.id)
            ids = repo.list_video_ids_for_tag("hook")
        assert set(int(i) for i in ids) == {v1, v2}

    def test_cascade_delete_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta6")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
            assert t.id is not None
            repo.assign(VideoId(vid), t.id)
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("DELETE FROM videos WHERE id=:v"), {"v": vid})
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM tag_assignments WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert n == 0
```

(c) `tests/unit/adapters/sqlite/test_collection_repository.py` :

```python
"""CollectionRepositorySQLite (M011/S02/R057)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.collection_repository import (
    CollectionRepositorySQLite,
)
from vidscope.domain import VideoId
from vidscope.domain.errors import StorageError


def _insert_video(engine: Engine, platform_id: str) -> int:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO videos (platform, platform_id, url, created_at) "
                 "VALUES ('youtube', :pid, :u, :c)"),
            {"pid": platform_id, "u": f"https://y.be/{platform_id}",
             "c": datetime.now(UTC)},
        )
        return int(conn.execute(
            text("SELECT id FROM videos WHERE platform_id=:pid"),
            {"pid": platform_id},
        ).scalar())


class TestCreate:
    def test_create_returns_entity(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("Concurrents Shopify")
        assert c.name == "Concurrents Shopify"
        assert c.id is not None

    def test_duplicate_name_raises(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            repo.create("X")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            with pytest.raises(StorageError):
                repo.create("X")

    def test_case_preserved_distinct_rows(self, engine: Engine) -> None:
        """D3 M011 RESEARCH: collection names are case-preserved."""
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            a = repo.create("Concurrents")
            b = repo.create("concurrents")
        assert a.id != b.id

    def test_empty_name_raises(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            with pytest.raises(StorageError):
                repo.create("   ")


class TestListAndLookup:
    def test_list_all_sorted(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            repo.create("Zeta")
            repo.create("Alpha")
            repo.create("Mu")
            cols = repo.list_all()
        names = [c.name for c in cols]
        assert names == sorted(names)

    def test_get_by_name(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            repo.create("My Collection")
        with engine.connect() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.get_by_name("My Collection")
            miss = repo.get_by_name("nope")
        assert c is not None
        assert c.name == "My Collection"
        assert miss is None


class TestMembership:
    def test_add_video_idempotent(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm1")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("C1")
            assert c.id is not None
            repo.add_video(c.id, VideoId(vid))
            repo.add_video(c.id, VideoId(vid))
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM collection_items "
                     "WHERE collection_id=:c AND video_id=:v"),
                {"c": c.id, "v": vid},
            ).scalar()
        assert n == 1

    def test_remove_video_noop_when_absent(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("C2")
            assert c.id is not None
            repo.remove_video(c.id, VideoId(999))

    def test_list_videos_ordered_desc(self, engine: Engine) -> None:
        import time
        v1 = _insert_video(engine, "cm2")
        v2 = _insert_video(engine, "cm3")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("C3")
            assert c.id is not None
            repo.add_video(c.id, VideoId(v1))
        time.sleep(0.01)
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.get_by_name("C3")
            assert c is not None and c.id is not None
            repo.add_video(c.id, VideoId(v2))
        with engine.connect() as conn:
            repo = CollectionRepositorySQLite(conn)
            ids = repo.list_videos(c.id)
        # Most-recently-added first: v2 then v1
        assert [int(i) for i in ids] == [v2, v1]

    def test_list_video_ids_for_collection(self, engine: Engine) -> None:
        v1 = _insert_video(engine, "cm4")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("Find Me")
            assert c.id is not None
            repo.add_video(c.id, VideoId(v1))
        with engine.connect() as conn:
            repo = CollectionRepositorySQLite(conn)
            ids = repo.list_video_ids_for_collection("Find Me")
        assert [int(i) for i in ids] == [v1]

    def test_list_collections_for_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm5")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c1 = repo.create("A")
            c2 = repo.create("B")
            assert c1.id is not None and c2.id is not None
            repo.add_video(c1.id, VideoId(vid))
            repo.add_video(c2.id, VideoId(vid))
            cols = repo.list_collections_for_video(VideoId(vid))
        assert {c.name for c in cols} == {"A", "B"}

    def test_cascade_delete_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm6")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("Casc")
            assert c.id is not None
            repo.add_video(c.id, VideoId(vid))
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("DELETE FROM videos WHERE id=:v"), {"v": vid})
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM collection_items WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert n == 0

    def test_cascade_delete_collection(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm7")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("DelMe")
            assert c.id is not None
            repo.add_video(c.id, VideoId(vid))
            cid = c.id
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("DELETE FROM collections WHERE id=:c"), {"c": cid})
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM collection_items WHERE collection_id=:c"),
                {"c": cid},
            ).scalar()
        assert n == 0


class TestUoWExposure:
    def test_uow_exposes_tags_and_collections(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
        with SqliteUnitOfWork(engine) as uow:
            assert uow.tags is not None
            assert uow.collections is not None
```

Étape 12 — Exécuter :
```
uv run pytest tests/unit/domain/test_tag_collection_entities.py tests/unit/adapters/sqlite/test_tag_repository.py tests/unit/adapters/sqlite/test_collection_repository.py -x -q
uv run lint-imports
```

NE PAS utiliser string interpolation pour SQL. NE PAS ajouter de champs à la table `videos`.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/domain/test_tag_collection_entities.py tests/unit/adapters/sqlite/test_tag_repository.py tests/unit/adapters/sqlite/test_collection_repository.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class Tag:" src/vidscope/domain/entities.py` matches
    - `grep -n "class Collection:" src/vidscope/domain/entities.py` matches
    - `grep -n "class TagRepository" src/vidscope/ports/repositories.py` matches
    - `grep -n "class CollectionRepository" src/vidscope/ports/repositories.py` matches
    - `grep -n "tags: TagRepository" src/vidscope/ports/unit_of_work.py` matches
    - `grep -n "collections: CollectionRepository" src/vidscope/ports/unit_of_work.py` matches
    - `grep -n "def _ensure_tags_collections_tables" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "_ensure_tags_collections_tables(conn)" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "CREATE TABLE tags" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "CREATE TABLE tag_assignments" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "CREATE TABLE collections" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "CREATE TABLE collection_items" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "class TagRepositorySQLite" src/vidscope/adapters/sqlite/tag_repository.py` matches
    - `grep -n ".lower().strip()" src/vidscope/adapters/sqlite/tag_repository.py` matches (OR `.strip().lower()`)
    - `grep -n "class CollectionRepositorySQLite" src/vidscope/adapters/sqlite/collection_repository.py` matches
    - `grep -n "self.tags = TagRepositorySQLite" src/vidscope/adapters/sqlite/unit_of_work.py` matches
    - `grep -n "self.collections = CollectionRepositorySQLite" src/vidscope/adapters/sqlite/unit_of_work.py` matches
    - `uv run pytest tests/unit/domain/test_tag_collection_entities.py -x -q` exits 0
    - `uv run pytest tests/unit/adapters/sqlite/test_tag_repository.py -x -q` exits 0
    - `uv run pytest tests/unit/adapters/sqlite/test_collection_repository.py -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - Tag + Collection entities livrées, re-exportées
    - TagRepository + CollectionRepository Protocols livrés
    - 4 tables SQLAlchemy Core + migration idempotente
    - Adapters SQLite: TagRepositorySQLite (lowercase norm), CollectionRepositorySQLite (case-preserved)
    - SqliteUnitOfWork expose uow.tags + uow.collections
    - Cascade delete vérifiée pour video/tag/collection
    - 25+ tests domain+adapter verts
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: 8 use cases (4 tag + 4 collection) + CLI sub-apps `vidscope tag` et `vidscope collection` + registration</name>
  <files>src/vidscope/application/tag_video.py, src/vidscope/application/collection_library.py, src/vidscope/cli/commands/tags.py, src/vidscope/cli/commands/collections.py, src/vidscope/cli/commands/__init__.py, src/vidscope/cli/app.py, tests/unit/application/test_tag_use_cases.py, tests/unit/application/test_collection_use_cases.py, tests/unit/cli/test_tags_cmd.py, tests/unit/cli/test_collections_cmd.py</files>
  <read_first>
    - src/vidscope/application/search_videos.py (pattern use case simple — unit_of_work_factory, execute, no adapter import)
    - src/vidscope/application/set_video_tracking.py (livré en S01 — pattern avec UoW fake pour tests)
    - src/vidscope/cli/commands/watch.py (pattern typer.Typer sub-app avec add/list/remove commands)
    - src/vidscope/cli/commands/cookies.py (pattern typer.Typer avec arguments + options)
    - src/vidscope/cli/app.py (lignes 98-100: `app.add_typer(watch_app, name="watch")` — pattern identique à appliquer)
    - tests/unit/cli/test_watch.py (pattern CliRunner + fixtures pour sub-app)
    - tests/unit/cli/test_review_cmd.py (livré en S01 — pattern d'insertion vidéo + runner)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 11 S02: `vidscope tag add/remove/list`, `vidscope collection create/add/remove/list/show`)
  </read_first>
  <behavior>
    - Test 1: `TagVideoUseCase.execute(video_id, name)` appelle `uow.tags.get_or_create(name)` puis `uow.tags.assign(video_id, tag.id)`. Retourne le Tag persisté.
    - Test 2: `UntagVideoUseCase.execute(video_id, name)` appelle `uow.tags.get_by_name(name)` puis `uow.tags.unassign(video_id, tag.id)`. No-op si le tag n'existe pas.
    - Test 3: `ListTagsUseCase.execute()` retourne `uow.tags.list_all()`.
    - Test 4: `ListVideoTagsUseCase.execute(video_id)` retourne `uow.tags.list_for_video(video_id)`.
    - Test 5: `CreateCollectionUseCase.execute(name)` appelle `uow.collections.create(name)`. Raise StorageError wrappée si existante.
    - Test 6: `AddToCollectionUseCase.execute(collection_name, video_id)` fetch la collection par nom, raise si absente (UserError), puis `uow.collections.add_video(coll.id, video_id)`.
    - Test 7: `RemoveFromCollectionUseCase.execute(collection_name, video_id)` fetch + `uow.collections.remove_video(...)`. Raise si collection absente.
    - Test 8: `ListCollectionsUseCase.execute()` retourne une liste de `CollectionSummary(collection, video_count)` — le count est fetché via un count query ou approximé.
    - Test 9: CLI `vidscope tag --help` liste `add, remove, list, video`.
    - Test 10: CLI `vidscope tag add 42 idea` tag la video 42 avec "idea"; exit 0, "added" dans l'output.
    - Test 11: CLI `vidscope tag list` imprime un tableau avec tous les tags.
    - Test 12: CLI `vidscope tag video 42` imprime les tags de la video 42.
    - Test 13: CLI `vidscope collection --help` liste `create, add, remove, list, show`.
    - Test 14: CLI `vidscope collection create "Concurrents Shopify"` crée la collection; 2e appel échoue avec exit code != 0.
    - Test 15: CLI `vidscope collection add "Concurrents" 42` ajoute la video 42 à la collection; échoue si collection absente.
    - Test 16: CLI `vidscope collection show "Concurrents"` liste les videos de la collection.
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/application/tag_video.py` :

```python
"""Tag use cases (M011/S02/R057).

4 use cases operating on the tags + tag_assignments tables. Every use
case uses `unit_of_work_factory` for atomicity and imports only from
vidscope.domain and vidscope.ports (application-has-no-adapters).
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Tag, VideoId
from vidscope.domain.errors import DomainError
from vidscope.ports import UnitOfWorkFactory

__all__ = [
    "ListTagsUseCase",
    "ListVideoTagsUseCase",
    "TagVideoUseCase",
    "UntagVideoUseCase",
]


class TagVideoUseCase:
    """Tag a single video. Idempotent on re-tag."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, video_id: int, name: str) -> Tag:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            tag = uow.tags.get_or_create(name)
            if tag.id is None:  # pragma: no cover — defensive
                raise DomainError(f"tag {name!r} has no id after get_or_create")
            uow.tags.assign(vid, tag.id)
            return tag


class UntagVideoUseCase:
    """Remove a tag from a video. No-op if the tag or assignment is absent."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, video_id: int, name: str) -> bool:
        """Return True if an assignment was actually removed."""
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            tag = uow.tags.get_by_name(name)
            if tag is None or tag.id is None:
                return False
            uow.tags.unassign(vid, tag.id)
            return True


class ListTagsUseCase:
    """Return every tag globally."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, *, limit: int = 1000) -> list[Tag]:
        with self._uow() as uow:
            return uow.tags.list_all(limit=limit)


class ListVideoTagsUseCase:
    """Return tags assigned to a single video."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, video_id: int) -> list[Tag]:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            return uow.tags.list_for_video(vid)
```

Étape 2 — Créer `src/vidscope/application/collection_library.py` :

```python
"""Collection use cases (M011/S02/R057).

4 use cases operating on the collections + collection_items tables.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Collection, VideoId
from vidscope.domain.errors import DomainError
from vidscope.ports import UnitOfWorkFactory

__all__ = [
    "AddToCollectionUseCase",
    "CollectionSummary",
    "CreateCollectionUseCase",
    "ListCollectionsUseCase",
    "RemoveFromCollectionUseCase",
]


@dataclass(frozen=True, slots=True)
class CollectionSummary:
    """Row used by `vidscope collection list`."""

    collection: Collection
    video_count: int


class CreateCollectionUseCase:
    """Create a new named collection. Raises on duplicate name."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, name: str) -> Collection:
        with self._uow() as uow:
            return uow.collections.create(name)


class AddToCollectionUseCase:
    """Add a video to a collection (by collection name)."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, collection_name: str, video_id: int) -> Collection:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            coll = uow.collections.get_by_name(collection_name)
            if coll is None or coll.id is None:
                raise DomainError(
                    f"collection {collection_name!r} does not exist"
                )
            uow.collections.add_video(coll.id, vid)
            return coll


class RemoveFromCollectionUseCase:
    """Remove a video from a collection."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, collection_name: str, video_id: int) -> Collection:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            coll = uow.collections.get_by_name(collection_name)
            if coll is None or coll.id is None:
                raise DomainError(
                    f"collection {collection_name!r} does not exist"
                )
            uow.collections.remove_video(coll.id, vid)
            return coll


class ListCollectionsUseCase:
    """Return every collection with its video count."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, *, limit: int = 1000) -> list[CollectionSummary]:
        with self._uow() as uow:
            cols = uow.collections.list_all(limit=limit)
            results: list[CollectionSummary] = []
            for c in cols:
                if c.id is None:
                    continue
                vids = uow.collections.list_videos(c.id, limit=10_000)
                results.append(CollectionSummary(collection=c, video_count=len(vids)))
            return results
```

Étape 3 — Créer `src/vidscope/cli/commands/tags.py` :

```python
"""`vidscope tag ...` subcommands (M011/S02/R057)."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.tag_video import (
    ListTagsUseCase,
    ListVideoTagsUseCase,
    TagVideoUseCase,
    UntagVideoUseCase,
)
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["tag_app"]


tag_app = typer.Typer(
    name="tag",
    help="Manage video tags (add, remove, list).",
    no_args_is_help=True,
    add_completion=False,
)


@tag_app.command("add")
def tag_add(
    video_id: int = typer.Argument(..., help="Video id (from `vidscope list`)."),
    name: str = typer.Argument(..., help="Tag name (will be lowercased)."),
) -> None:
    """Tag a video."""
    with handle_domain_errors():
        container = acquire_container()
        uc = TagVideoUseCase(unit_of_work_factory=container.unit_of_work)
        tag = uc.execute(video_id, name)
        console.print(
            f"[bold green]added[/bold green] tag [bold]{tag.name}[/bold] "
            f"to video {video_id}"
        )


@tag_app.command("remove")
def tag_remove(
    video_id: int = typer.Argument(..., help="Video id."),
    name: str = typer.Argument(..., help="Tag name."),
) -> None:
    """Remove a tag from a video."""
    with handle_domain_errors():
        container = acquire_container()
        uc = UntagVideoUseCase(unit_of_work_factory=container.unit_of_work)
        removed = uc.execute(video_id, name)
        if removed:
            console.print(
                f"[bold green]removed[/bold green] tag {name!r} from video {video_id}"
            )
        else:
            console.print(
                f"[dim]tag {name!r} not assigned to video {video_id} — nothing to do[/dim]"
            )


@tag_app.command("list")
def tag_list() -> None:
    """List every tag globally."""
    with handle_domain_errors():
        container = acquire_container()
        uc = ListTagsUseCase(unit_of_work_factory=container.unit_of_work)
        tags = uc.execute()
        console.print(f"[bold]tags:[/bold] {len(tags)}")
        if not tags:
            console.print(
                "[dim]No tags yet. Run [bold]vidscope tag add <id> <name>[/bold].[/dim]"
            )
            return
        table = Table(title="Tags", show_header=True)
        table.add_column("id", justify="right", style="dim")
        table.add_column("name")
        table.add_column("created")
        for t in tags:
            created = t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "-"
            table.add_row(str(t.id), t.name, created)
        console.print(table)


@tag_app.command("video")
def tag_video(
    video_id: int = typer.Argument(..., help="Video id."),
) -> None:
    """List the tags assigned to a single video."""
    with handle_domain_errors():
        container = acquire_container()
        uc = ListVideoTagsUseCase(unit_of_work_factory=container.unit_of_work)
        tags = uc.execute(video_id)
        console.print(
            f"[bold]tags for video {video_id}:[/bold] "
            + (", ".join(t.name for t in tags) if tags else "(none)")
        )
```

Étape 4 — Créer `src/vidscope/cli/commands/collections.py` :

```python
"""`vidscope collection ...` subcommands (M011/S02/R057)."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.collection_library import (
    AddToCollectionUseCase,
    CreateCollectionUseCase,
    ListCollectionsUseCase,
    RemoveFromCollectionUseCase,
)
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["collection_app"]


collection_app = typer.Typer(
    name="collection",
    help="Manage video collections (create, add, remove, list, show).",
    no_args_is_help=True,
    add_completion=False,
)


@collection_app.command("create")
def collection_create(
    name: str = typer.Argument(..., help="Collection name (case-preserved)."),
) -> None:
    """Create a new collection."""
    with handle_domain_errors():
        container = acquire_container()
        uc = CreateCollectionUseCase(unit_of_work_factory=container.unit_of_work)
        c = uc.execute(name)
        console.print(
            f"[bold green]created[/bold green] collection [bold]{c.name}[/bold] (id={c.id})"
        )


@collection_app.command("add")
def collection_add(
    collection_name: str = typer.Argument(..., help="Collection name."),
    video_id: int = typer.Argument(..., help="Video id."),
) -> None:
    """Add a video to a collection."""
    with handle_domain_errors():
        container = acquire_container()
        uc = AddToCollectionUseCase(unit_of_work_factory=container.unit_of_work)
        c = uc.execute(collection_name, video_id)
        console.print(
            f"[bold green]added[/bold green] video {video_id} to "
            f"[bold]{c.name}[/bold]"
        )


@collection_app.command("remove")
def collection_remove(
    collection_name: str = typer.Argument(..., help="Collection name."),
    video_id: int = typer.Argument(..., help="Video id."),
) -> None:
    """Remove a video from a collection."""
    with handle_domain_errors():
        container = acquire_container()
        uc = RemoveFromCollectionUseCase(unit_of_work_factory=container.unit_of_work)
        c = uc.execute(collection_name, video_id)
        console.print(
            f"[bold green]removed[/bold green] video {video_id} from "
            f"[bold]{c.name}[/bold]"
        )


@collection_app.command("list")
def collection_list() -> None:
    """List every collection with its video count."""
    with handle_domain_errors():
        container = acquire_container()
        uc = ListCollectionsUseCase(unit_of_work_factory=container.unit_of_work)
        summaries = uc.execute()
        console.print(f"[bold]collections:[/bold] {len(summaries)}")
        if not summaries:
            console.print(
                "[dim]No collections yet. "
                "Run [bold]vidscope collection create <name>[/bold].[/dim]"
            )
            return
        table = Table(title="Collections", show_header=True)
        table.add_column("id", justify="right", style="dim")
        table.add_column("name")
        table.add_column("videos", justify="right")
        table.add_column("created")
        for s in summaries:
            created = (
                s.collection.created_at.strftime("%Y-%m-%d %H:%M")
                if s.collection.created_at else "-"
            )
            table.add_row(
                str(s.collection.id), s.collection.name,
                str(s.video_count), created,
            )
        console.print(table)


@collection_app.command("show")
def collection_show(
    name: str = typer.Argument(..., help="Collection name."),
) -> None:
    """Show the videos in a collection."""
    with handle_domain_errors():
        container = acquire_container()
        with container.unit_of_work() as uow:
            coll = uow.collections.get_by_name(name)
            if coll is None or coll.id is None:
                console.print(f"[red]collection {name!r} does not exist[/red]")
                raise typer.Exit(code=1)
            video_ids = uow.collections.list_videos(coll.id)
        console.print(
            f"[bold]{coll.name}[/bold]: "
            + (
                ", ".join(str(int(v)) for v in video_ids)
                if video_ids else "(empty)"
            )
        )
```

Étape 5 — Enregistrer dans `src/vidscope/cli/commands/__init__.py` :

(a) Ajouter les imports :
```python
from vidscope.cli.commands.collections import collection_app
from vidscope.cli.commands.tags import tag_app
```

(b) Ajouter `"collection_app"` et `"tag_app"` au `__all__` (tri alphabétique).

Étape 6 — Enregistrer dans `src/vidscope/cli/app.py` :

(a) Dans l'import `from vidscope.cli.commands import (...)`, ajouter `collection_app` et `tag_app`.

(b) Ajouter les 2 sub-app registrations APRÈS `app.add_typer(cookies_app, name="cookies")` :
```python
app.add_typer(tag_app, name="tag")
app.add_typer(collection_app, name="collection")
```

Étape 7 — Créer les 4 fichiers de tests.

(a) `tests/unit/application/test_tag_use_cases.py` (utilise des fakes InMemory) :

```python
"""Tag use case tests with InMemory fakes (M011/S02/R057)."""

from __future__ import annotations

from vidscope.application.tag_video import (
    ListTagsUseCase,
    ListVideoTagsUseCase,
    TagVideoUseCase,
    UntagVideoUseCase,
)
from vidscope.domain import Tag, VideoId


class _FakeTagRepo:
    def __init__(self) -> None:
        self._tags: dict[str, Tag] = {}
        self._assignments: set[tuple[int, int]] = set()
        self._next = 1

    def get_or_create(self, name: str) -> Tag:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("empty tag")
        if normalized not in self._tags:
            self._tags[normalized] = Tag(id=self._next, name=normalized)
            self._next += 1
        return self._tags[normalized]

    def get_by_name(self, name: str) -> Tag | None:
        return self._tags.get(name.strip().lower())

    def list_all(self, *, limit=1000) -> list[Tag]:
        return sorted(self._tags.values(), key=lambda t: t.name)

    def list_for_video(self, video_id: VideoId) -> list[Tag]:
        tag_ids = {tid for vid, tid in self._assignments if vid == int(video_id)}
        return sorted(
            [t for t in self._tags.values() if t.id in tag_ids],
            key=lambda t: t.name,
        )

    def assign(self, video_id: VideoId, tag_id: int) -> None:
        self._assignments.add((int(video_id), int(tag_id)))

    def unassign(self, video_id: VideoId, tag_id: int) -> None:
        self._assignments.discard((int(video_id), int(tag_id)))

    def list_video_ids_for_tag(self, name, *, limit=1000) -> list[VideoId]:
        t = self.get_by_name(name)
        if t is None:
            return []
        return [VideoId(v) for (v, tid) in self._assignments if tid == t.id]


class _FakeUoW:
    def __init__(self, tags_repo: _FakeTagRepo) -> None:
        self.tags = tags_repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _factory_from(repo):
    def _make():
        return _FakeUoW(repo)
    return _make


class TestTagVideoUseCase:
    def test_creates_and_assigns(self) -> None:
        repo = _FakeTagRepo()
        uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        tag = uc.execute(42, "Idea")
        assert tag.name == "idea"
        assert (42, tag.id) in repo._assignments

    def test_idempotent(self) -> None:
        repo = _FakeTagRepo()
        uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        uc.execute(42, "idea")
        uc.execute(42, "idea")
        assert len(repo._assignments) == 1


class TestUntagVideoUseCase:
    def test_removes_assignment(self) -> None:
        repo = _FakeTagRepo()
        tag_uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        tag_uc.execute(42, "idea")
        untag_uc = UntagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        removed = untag_uc.execute(42, "idea")
        assert removed is True
        assert not repo._assignments

    def test_missing_tag_returns_false(self) -> None:
        repo = _FakeTagRepo()
        uc = UntagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        assert uc.execute(42, "ghost") is False


class TestListUseCases:
    def test_list_all(self) -> None:
        repo = _FakeTagRepo()
        repo.get_or_create("zeta")
        repo.get_or_create("alpha")
        uc = ListTagsUseCase(unit_of_work_factory=_factory_from(repo))
        names = [t.name for t in uc.execute()]
        assert names == ["alpha", "zeta"]

    def test_list_for_video(self) -> None:
        repo = _FakeTagRepo()
        tag_uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        tag_uc.execute(7, "idea")
        tag_uc.execute(7, "hook")
        uc = ListVideoTagsUseCase(unit_of_work_factory=_factory_from(repo))
        names = {t.name for t in uc.execute(7)}
        assert names == {"idea", "hook"}
```

(b) `tests/unit/application/test_collection_use_cases.py` :

```python
"""Collection use case tests with InMemory fakes (M011/S02/R057)."""

from __future__ import annotations

import pytest

from vidscope.application.collection_library import (
    AddToCollectionUseCase,
    CreateCollectionUseCase,
    ListCollectionsUseCase,
    RemoveFromCollectionUseCase,
)
from vidscope.domain import Collection, VideoId
from vidscope.domain.errors import DomainError, StorageError


class _FakeCollectionRepo:
    def __init__(self) -> None:
        self._colls: dict[str, Collection] = {}
        self._members: set[tuple[int, int]] = set()
        self._next = 1

    def create(self, name: str) -> Collection:
        stripped = name.strip()
        if not stripped:
            raise StorageError("empty name")
        if stripped in self._colls:
            raise StorageError(f"duplicate: {stripped!r}")
        c = Collection(id=self._next, name=stripped)
        self._colls[stripped] = c
        self._next += 1
        return c

    def get_by_name(self, name: str) -> Collection | None:
        return self._colls.get(name.strip())

    def list_all(self, *, limit=1000) -> list[Collection]:
        return sorted(self._colls.values(), key=lambda c: c.name)

    def add_video(self, collection_id: int, video_id: VideoId) -> None:
        self._members.add((int(collection_id), int(video_id)))

    def remove_video(self, collection_id: int, video_id: VideoId) -> None:
        self._members.discard((int(collection_id), int(video_id)))

    def list_videos(self, collection_id: int, *, limit=1000) -> list[VideoId]:
        return [VideoId(v) for (c, v) in self._members if c == int(collection_id)]

    def list_collections_for_video(self, video_id: VideoId) -> list[Collection]:
        cids = {c for (c, v) in self._members if v == int(video_id)}
        return sorted(
            [c for c in self._colls.values() if c.id in cids],
            key=lambda c: c.name,
        )

    def list_video_ids_for_collection(self, name, *, limit=1000) -> list[VideoId]:
        c = self.get_by_name(name)
        if c is None:
            return []
        return self.list_videos(c.id) if c.id else []


class _FakeUoW:
    def __init__(self, repo: _FakeCollectionRepo) -> None:
        self.collections = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _factory_from(repo):
    def _make():
        return _FakeUoW(repo)
    return _make


class TestCreateCollection:
    def test_creates(self) -> None:
        repo = _FakeCollectionRepo()
        uc = CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo))
        c = uc.execute("X")
        assert c.name == "X"

    def test_duplicate_raises(self) -> None:
        repo = _FakeCollectionRepo()
        uc = CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo))
        uc.execute("X")
        with pytest.raises(StorageError):
            uc.execute("X")


class TestAddRemove:
    def test_add(self) -> None:
        repo = _FakeCollectionRepo()
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X")
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        assert repo._members == {(1, 42)}

    def test_add_missing_collection_raises(self) -> None:
        repo = _FakeCollectionRepo()
        uc = AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo))
        with pytest.raises(DomainError):
            uc.execute("ghost", 42)

    def test_remove(self) -> None:
        repo = _FakeCollectionRepo()
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X")
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        RemoveFromCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        assert repo._members == set()


class TestListCollections:
    def test_returns_summary_with_count(self) -> None:
        repo = _FakeCollectionRepo()
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X")
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("Y")
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 43)
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("Y", 42)
        uc = ListCollectionsUseCase(unit_of_work_factory=_factory_from(repo))
        summaries = uc.execute()
        by_name = {s.collection.name: s.video_count for s in summaries}
        assert by_name == {"X": 2, "Y": 1}
```

(c) `tests/unit/cli/test_tags_cmd.py` :

```python
"""CliRunner tests for `vidscope tag` (M011/S02/R057)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from vidscope.cli.app import app


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    import pathlib
    here = pathlib.Path(__file__).resolve()
    for _ in range(6):
        if (here / "config" / "taxonomy.yaml").is_file():
            monkeypatch.chdir(here)
            break
        here = here.parent
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    yield


def _insert_video(pid: str = "tag_test_1") -> int:
    from vidscope.infrastructure.container import build_container
    container = build_container()
    try:
        with container.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES ('youtube', :p, :u, :c)"),
                {"p": pid, "u": f"https://y.be/{pid}", "c": datetime.now(UTC)},
            )
            return int(conn.execute(
                text("SELECT id FROM videos WHERE platform_id=:p"),
                {"p": pid},
            ).scalar())
    finally:
        container.engine.dispose()


class TestTagCmd:
    def test_help(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["tag", "--help"])
        assert r.exit_code == 0
        for sub in ("add", "remove", "list", "video"):
            assert sub in r.output

    def test_add_and_list(self) -> None:
        vid = _insert_video("tag_add_1")
        runner = CliRunner()
        r1 = runner.invoke(app, ["tag", "add", str(vid), "Idea"])
        assert r1.exit_code == 0, r1.output
        assert "added" in r1.output
        r2 = runner.invoke(app, ["tag", "list"])
        assert r2.exit_code == 0
        assert "idea" in r2.output  # lowercased

    def test_remove(self) -> None:
        vid = _insert_video("tag_remove_1")
        runner = CliRunner()
        runner.invoke(app, ["tag", "add", str(vid), "hook"])
        r = runner.invoke(app, ["tag", "remove", str(vid), "hook"])
        assert r.exit_code == 0
        assert "removed" in r.output

    def test_video_subcommand(self) -> None:
        vid = _insert_video("tag_vid_1")
        runner = CliRunner()
        runner.invoke(app, ["tag", "add", str(vid), "idea"])
        runner.invoke(app, ["tag", "add", str(vid), "reuse"])
        r = runner.invoke(app, ["tag", "video", str(vid)])
        assert r.exit_code == 0
        assert "idea" in r.output
        assert "reuse" in r.output
```

(d) `tests/unit/cli/test_collections_cmd.py` :

```python
"""CliRunner tests for `vidscope collection` (M011/S02/R057)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from vidscope.cli.app import app


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    import pathlib
    here = pathlib.Path(__file__).resolve()
    for _ in range(6):
        if (here / "config" / "taxonomy.yaml").is_file():
            monkeypatch.chdir(here)
            break
        here = here.parent
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    yield


def _insert_video(pid: str) -> int:
    from vidscope.infrastructure.container import build_container
    container = build_container()
    try:
        with container.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES ('youtube', :p, :u, :c)"),
                {"p": pid, "u": f"https://y.be/{pid}", "c": datetime.now(UTC)},
            )
            return int(conn.execute(
                text("SELECT id FROM videos WHERE platform_id=:p"),
                {"p": pid},
            ).scalar())
    finally:
        container.engine.dispose()


class TestCollectionCmd:
    def test_help(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["collection", "--help"])
        assert r.exit_code == 0
        for sub in ("create", "add", "remove", "list", "show"):
            assert sub in r.output

    def test_create_and_duplicate_fails(self) -> None:
        runner = CliRunner()
        r1 = runner.invoke(app, ["collection", "create", "Concurrents"])
        assert r1.exit_code == 0
        assert "created" in r1.output
        r2 = runner.invoke(app, ["collection", "create", "Concurrents"])
        assert r2.exit_code != 0

    def test_add_to_missing_fails(self) -> None:
        vid = _insert_video("col_miss_1")
        runner = CliRunner()
        r = runner.invoke(app, ["collection", "add", "Ghost", str(vid)])
        assert r.exit_code != 0

    def test_add_and_show(self) -> None:
        vid = _insert_video("col_add_1")
        runner = CliRunner()
        runner.invoke(app, ["collection", "create", "MyCol"])
        runner.invoke(app, ["collection", "add", "MyCol", str(vid)])
        r = runner.invoke(app, ["collection", "show", "MyCol"])
        assert r.exit_code == 0
        assert str(vid) in r.output

    def test_remove(self) -> None:
        vid = _insert_video("col_rem_1")
        runner = CliRunner()
        runner.invoke(app, ["collection", "create", "Rem"])
        runner.invoke(app, ["collection", "add", "Rem", str(vid)])
        r = runner.invoke(app, ["collection", "remove", "Rem", str(vid)])
        assert r.exit_code == 0
        assert "removed" in r.output

    def test_list_with_counts(self) -> None:
        v1 = _insert_video("col_list_1")
        v2 = _insert_video("col_list_2")
        runner = CliRunner()
        runner.invoke(app, ["collection", "create", "Lst"])
        runner.invoke(app, ["collection", "add", "Lst", str(v1)])
        runner.invoke(app, ["collection", "add", "Lst", str(v2)])
        r = runner.invoke(app, ["collection", "list"])
        assert r.exit_code == 0
        assert "Lst" in r.output
        assert "2" in r.output  # video_count=2
```

Étape 8 — Exécuter :
```
uv run pytest tests/unit/application/test_tag_use_cases.py tests/unit/application/test_collection_use_cases.py tests/unit/cli/test_tags_cmd.py tests/unit/cli/test_collections_cmd.py -x -q
uv run lint-imports
```
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_tag_use_cases.py tests/unit/application/test_collection_use_cases.py tests/unit/cli/test_tags_cmd.py tests/unit/cli/test_collections_cmd.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class TagVideoUseCase" src/vidscope/application/tag_video.py` matches
    - `grep -n "class UntagVideoUseCase" src/vidscope/application/tag_video.py` matches
    - `grep -n "class ListTagsUseCase" src/vidscope/application/tag_video.py` matches
    - `grep -n "class ListVideoTagsUseCase" src/vidscope/application/tag_video.py` matches
    - `grep -n "class CreateCollectionUseCase" src/vidscope/application/collection_library.py` matches
    - `grep -n "class AddToCollectionUseCase" src/vidscope/application/collection_library.py` matches
    - `grep -n "class RemoveFromCollectionUseCase" src/vidscope/application/collection_library.py` matches
    - `grep -n "class ListCollectionsUseCase" src/vidscope/application/collection_library.py` matches
    - `grep -nE "from vidscope.adapters" src/vidscope/application/tag_video.py` returns exit 1
    - `grep -nE "from vidscope.adapters" src/vidscope/application/collection_library.py` returns exit 1
    - `grep -n "tag_app = typer.Typer" src/vidscope/cli/commands/tags.py` matches
    - `grep -n "collection_app = typer.Typer" src/vidscope/cli/commands/collections.py` matches
    - `grep -nE "add_typer\\(tag_app" src/vidscope/cli/app.py` matches
    - `grep -nE "add_typer\\(collection_app" src/vidscope/cli/app.py` matches
    - `uv run pytest tests/unit/application/test_tag_use_cases.py -x -q` exits 0
    - `uv run pytest tests/unit/application/test_collection_use_cases.py -x -q` exits 0
    - `uv run pytest tests/unit/cli/test_tags_cmd.py -x -q` exits 0
    - `uv run pytest tests/unit/cli/test_collections_cmd.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (application-has-no-adapters KEPT)
  </acceptance_criteria>
  <done>
    - 4 tag use cases + 4 collection use cases livrés (application pure)
    - vidscope tag sub-app avec add/remove/list/video
    - vidscope collection sub-app avec create/add/remove/list/show
    - Registration dans app.py via add_typer
    - 14+ tests use cases + 10+ tests CLI verts
    - application-has-no-adapters toujours KEPT
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI (user) → TagRepositorySQLite | Nom de tag fourni par user. Normalisé lowercase+strip dans le repo. |
| CLI (user) → CollectionRepositorySQLite | Nom de collection fourni par user. Trim whitespace, case-preserved. |
| CLI (user) → video_id (int) | Valeur castée `int(...)` avant tout usage SQL. Pas d'injection possible. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-SQL-M011-02 | Tampering | Tag + Collection queries | mitigate | SQLAlchemy Core bind params via `.where(col == value)` et `sqlite_insert(...).values(**payload)`. Noms cast via `str()`, video_id via `int()`. Aucune string interpolation dans une query. |
| T-INPUT-M011-02 | DoS | Nom de tag / collection anormalement long | accept | SQL column size contraint à VARCHAR(128) / VARCHAR(255). Pas de DoS pratique via l'API SQL. |
| T-DATA-M011-02 | Tampering | Tag name = whitespace/empty après strip | mitigate | `get_or_create` lève `StorageError` si `_normalize` renvoie empty. Test `test_empty_name_raises`. |
| T-DUPE-M011-01 | Availability | Appels CLI répétés `vidscope tag add` ou `collection add` | mitigate | `on_conflict_do_nothing(index_elements=...)` sur tag_assignments et collection_items. Tests d'idempotence. |
| T-CASCADE-M011-01 | Availability | DELETE video orphan les membership rows | mitigate | FK `ON DELETE CASCADE` sur video_id dans tag_assignments et collection_items. Tests `test_cascade_delete_video`. |
| T-MIG-M011-01 | Availability | Migration S02 sur DB partielle (pré-S01 ou intermédiaire) | mitigate | Check `sqlite_master` avant CREATE TABLE pour chaque table. Ordre garanti (tags -> tag_assignments -> collections -> collection_items). Test `test_idempotent_migration`. |
| T-ARCH-M011-02 | Spoofing | Application layer importing adapter | mitigate | Contrat `application-has-no-adapters` existant reste KEPT. `grep "from vidscope.adapters" src/vidscope/application/` doit retourner 0 match. |
</threat_model>

<verification>
Après les 2 tâches, exécuter :
- `uv run pytest tests/unit/domain/test_tag_collection_entities.py tests/unit/adapters/sqlite/test_tag_repository.py tests/unit/adapters/sqlite/test_collection_repository.py tests/unit/application/test_tag_use_cases.py tests/unit/application/test_collection_use_cases.py tests/unit/cli/test_tags_cmd.py tests/unit/cli/test_collections_cmd.py -x -q` vert
- `uv run lint-imports` vert — 10 contrats KEPT
- `uv run pytest -m architecture -x -q` vert
- `uv run vidscope tag --help` OK
- `uv run vidscope collection --help` OK
</verification>

<success_criteria>
S02 est complet quand :
- [ ] `Tag` et `Collection` entities frozen+slots livrées + re-exportées
- [ ] `TagRepository` et `CollectionRepository` Protocols livrés + re-exportés
- [ ] `UnitOfWork` déclare `tags` et `collections`
- [ ] 4 tables créées par migration idempotente: tags, tag_assignments, collections, collection_items
- [ ] Contraintes UNIQUE posées et FK ON DELETE CASCADE actifs
- [ ] `TagRepositorySQLite` normalise lowercase+strip (D3)
- [ ] `CollectionRepositorySQLite` case-preserve (D3)
- [ ] `SqliteUnitOfWork.__enter__` instancie les 2 nouveaux repos
- [ ] 8 use cases livrés (4 tag + 4 collection), tous application-pure
- [ ] CLI `vidscope tag` (add/remove/list/video) et `vidscope collection` (create/add/remove/list/show) enregistrées
- [ ] Cascade delete testée (video, tag, collection)
- [ ] Suite tests verte (domain + adapter + use case + CLI)
- [ ] `lint-imports` vert (10 contrats KEPT)
- [ ] R057 couvert end-to-end
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M011/M011-S02-SUMMARY.md` documentant :
- Signature finale de `Tag` et `Collection`
- DDL des 4 tables (UNIQUE + FK CASCADE)
- Pattern de normalisation TagName (lowercase+strip) vs CollectionName (case-preserved)
- Interface complète des 2 Protocols (TagRepository, CollectionRepository)
- Liste des 8 use cases + signature execute
- CLI signatures finales pour `vidscope tag` et `vidscope collection`
- Liste exhaustive des fichiers créés/modifiés
</output>
