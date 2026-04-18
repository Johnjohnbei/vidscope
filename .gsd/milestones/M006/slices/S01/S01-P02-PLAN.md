---
plan_id: S01-P02
phase: M006/S01
wave: 2
depends_on: [S01-P01]
requirements: [R040, R041, R042]
files_modified:
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/adapters/sqlite/schema.py
  - tests/unit/adapters/sqlite/test_schema.py
autonomous: true
---

## Objective

**Couverture requirements :** R040 (structural foundation : CreatorRepository Protocol + creators table), R041 (**partial only** — ce plan livre les méthodes read du Protocol (find_by_platform_user_id, find_by_handle, list_by_platform, list_by_min_followers) que S03 consommera pour implémenter vidscope creator show/list/videos + MCP tool. S01 ne livre AUCUN CLI ni MCP — R041 reste officiellement non-clos jusqu'à S03), R042 (foundation : la colonne videos.creator_id et le FK SET NULL qui permettent le backfill sans perdre de données).

Étendre la couche port avec le Protocol `CreatorRepository` (ajouté dans `ports/repositories.py` — **PAS** dans un nouveau fichier `ports/creator_repository.py`, c'est la convention du projet, 7 repos vivent déjà dans ce fichier — voir S01-RESEARCH.md §"Port Organization Decision"). Étendre `adapters/sqlite/schema.py` avec (1) la table `creators` déclarée dans `metadata` (fresh installs via `metadata.create_all`) (2) la colonne `videos.creator_id` inline `ForeignKey("creators.id", ondelete="SET NULL")` sur la déclaration Table (fresh installs) (3) un helper idempotent `_ensure_videos_creator_id(conn)` qui émet un `ALTER TABLE videos ADD COLUMN creator_id INTEGER REFERENCES creators(id) ON DELETE SET NULL` uniquement quand la colonne est absente (upgrade path pour les DB M001–M005). Les index (`idx_creators_handle`, `idx_videos_creator_id`) sont déclarés sur les Tables. Tests de schéma étendus : table présente, UNIQUE (platform, platform_user_id) active, FK on-delete SET NULL effective, helper idempotent sur re-run.

## Tasks

<task id="T05-creator-repository-protocol">
  <name>Append CreatorRepository Protocol à ports/repositories.py (convention existante : tous les repos dans un fichier)</name>

  <read_first>
    - `src/vidscope/ports/repositories.py` — les 7 Protocols existants (`VideoRepository` ligne 58, `WatchAccountRepository` ligne 214, etc.) à suivre comme patron ; docstring de haut de fichier ligne 1-25 qui dicte les conventions (retourne entité avec id peuplé, None sur miss jamais raise, list_recent avec limit explicite, etc.)
    - `src/vidscope/ports/__init__.py` — patron de re-export à étendre (ligne 34-42 groupe l'import depuis `repositories`)
    - `src/vidscope/domain/__init__.py` — vérifier que `Creator`, `CreatorId`, `PlatformUserId` sont bien re-exportés (livré par P01)
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"Minimal CreatorRepository Protocol signature" — signatures idiomatiques validées (upsert, find_by_platform_user_id, find_by_handle, get, list_by_platform, list_by_min_followers, count)
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"Port Organization Decision" — confirme qu'on n'ouvre PAS `ports/creator_repository.py`
    - `.importlinter` — contrat `ports-are-pure` : nouvelles imports uniquement depuis `vidscope.domain` et `typing`
  </read_first>

  <action>
  Ouvrir `src/vidscope/ports/repositories.py`. À la fin du fichier (après `WatchRefreshRepository` ligne ~275), ajouter le Protocol `CreatorRepository` :

  ```python
  @runtime_checkable
  class CreatorRepository(Protocol):
      """Persistence for :class:`~vidscope.domain.entities.Creator`.

      Identity anchors on ``(platform, platform_user_id)`` — the
      platform-stable id that survives account renames (per D-01).
      ``creators.id`` remains a surrogate autoincrement INT PK so FKs
      and CLI arguments stay ergonomic. ``handle`` is stored but NOT
      unique — the @-name may change, and the repository upserts
      through ``platform_user_id`` only.

      Adapters must enforce the compound UNIQUE constraint on
      ``(platform, platform_user_id)`` via :meth:`upsert`.
      """

      def upsert(self, creator: Creator) -> Creator:
          """Insert ``creator`` or update the existing row matching
          ``(platform, platform_user_id)``. Returns the resulting
          entity with ``id`` populated. Idempotent.

          Fields present on ``creator`` overwrite the existing row;
          ``created_at`` and ``first_seen_at`` are preserved on update
          (archaeology), ``last_seen_at`` is refreshed.
          """
          ...

      def get(self, creator_id: CreatorId) -> Creator | None:
          """Return the creator with ``id == creator_id``, or ``None``."""
          ...

      def find_by_platform_user_id(
          self, platform: Platform, platform_user_id: PlatformUserId
      ) -> Creator | None:
          """Return the creator matching ``(platform, platform_user_id)``
          or ``None``. This is the canonical identity lookup (per D-01)."""
          ...

      def find_by_handle(
          self, platform: Platform, handle: str
      ) -> Creator | None:
          """Return the creator matching ``(platform, handle)`` or ``None``.

          Handle is non-unique across time (rename history) but unique at
          any given moment per platform. On handle collisions (shouldn't
          happen in practice because handles are platform-enforced
          unique), return the most recently seen row.
          """
          ...

      def list_by_platform(
          self, platform: Platform, *, limit: int = 50
      ) -> list[Creator]:
          """Return up to ``limit`` creators on ``platform``, most
          recently seen first."""
          ...

      def list_by_min_followers(
          self, min_count: int, *, limit: int = 50
      ) -> list[Creator]:
          """Return up to ``limit`` creators with
          ``follower_count >= min_count``, highest-follower first. Rows
          where ``follower_count IS NULL`` are excluded."""
          ...

      def count(self) -> int:
          """Return the total number of creators in the store."""
          ...
  ```

  Mettre à jour l'import de `vidscope.domain` en haut du fichier (lignes 31-44) pour inclure `Creator`, `CreatorId`, `PlatformUserId` dans l'ordre alphabétique :

  ```python
  from vidscope.domain import (
      Analysis,
      Creator,
      CreatorId,
      Frame,
      PipelineRun,
      Platform,
      PlatformId,
      PlatformUserId,
      RunStatus,
      StageName,
      Transcript,
      Video,
      VideoId,
      WatchedAccount,
      WatchRefresh,
  )
  ```

  Ajouter `"CreatorRepository"` dans `__all__` (lignes 46-54) en ordre alphabétique :

  ```python
  __all__ = [
      "AnalysisRepository",
      "CreatorRepository",
      "FrameRepository",
      "PipelineRunRepository",
      "TranscriptRepository",
      "VideoRepository",
      "WatchAccountRepository",
      "WatchRefreshRepository",
  ]
  ```

  Enfin, mettre à jour `src/vidscope/ports/__init__.py` pour re-exporter `CreatorRepository` :
  - Ajouter `CreatorRepository` à l'import groupé depuis `.repositories` (lignes 34-42) en ordre alphabétique
  - Ajouter `"CreatorRepository"` dans `__all__` (lignes 46-71) en ordre alphabétique
  </action>

  <acceptance_criteria>
    - `grep -q "class CreatorRepository(Protocol):" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def upsert(self, creator: Creator) -> Creator:" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def find_by_platform_user_id" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def find_by_handle" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def list_by_platform" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def list_by_min_followers" src/vidscope/ports/repositories.py` exit 0
    - `grep -q '"CreatorRepository"' src/vidscope/ports/__init__.py` exit 0
    - Aucun fichier `src/vidscope/ports/creator_repository.py` n'est créé : `test ! -f src/vidscope/ports/creator_repository.py`
    - `python -m uv run python -c "from vidscope.ports import CreatorRepository; print(CreatorRepository.__name__)"` sort `CreatorRepository`
    - `python -m uv run python -c "from vidscope.ports import CreatorRepository; assert hasattr(CreatorRepository, 'upsert'); assert hasattr(CreatorRepository, 'find_by_platform_user_id')"` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `ports-are-pure` vert — CreatorRepository n'importe que domain + typing)
    - `python -m uv run pytest -q` exit 0 (zéro régression)
  </acceptance_criteria>
</task>

<task id="T06-schema-creators-table">
  <name>Étendre schema.py : table creators + videos.creator_id inline + ALTER idempotent (forme canonique CONTEXT.md §D-01)</name>

  <read_first>
    - `src/vidscope/adapters/sqlite/schema.py` lignes 81-95 — définition actuelle `videos` Table ; ligne 170-183 — patron `watched_accounts` avec compound `UniqueConstraint` ; ligne 148-167 — `pipeline_runs` avec `ForeignKey("videos.id", ondelete="SET NULL")` (précédent exact pour notre nullable FK) ; lignes 205-229 — `init_db` idempotent avec FTS5 raw DDL (précédent pour raw SQL à côté de Core)
    - `.gsd/milestones/M006/slices/S01/S01-CONTEXT.md` §"SQL migration shape (canonical)" — forme SQL exacte à reproduire
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"Recommended shape for '003_creators'" — approche SQLAlchemy Core + helper ALTER idempotent (pas d'Alembic)
    - `src/vidscope/infrastructure/sqlite_engine.py` lignes 51-60 — listener `PRAGMA foreign_keys=ON` déjà actif pour chaque connexion
  </read_first>

  <action>
  Ouvrir `src/vidscope/adapters/sqlite/schema.py`. Faire TROIS modifications :

  **1. Ajouter la colonne `creator_id` à la Table `videos` existante** (lignes 81-95). Après `Column("created_at", ...)`, ajouter :

  ```python
      Column(
          "creator_id",
          Integer,
          ForeignKey("creators.id", ondelete="SET NULL"),
          nullable=True,
      ),
  ```

  Attention : la Table `creators` doit être déclarée APRÈS `videos` dans le fichier mais SQLAlchemy résout les FK par nom au moment de `create_all`, donc l'ordre de déclaration dans le fichier n'est pas bloquant. Le test `test_fresh_install_has_creator_id` vérifiera que la colonne est bien présente après `metadata.create_all`.

  **2. Ajouter la Table `creators` après la Table `watch_refreshes`** (ligne ~194), juste avant le commentaire `# FTS5 virtual table DDL` (~ligne 197) :

  ```python
  # M006: creators registry
  creators = Table(
      "creators",
      metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("platform", String(32), nullable=False),
      Column("platform_user_id", String(255), nullable=False),
      Column("handle", String(255), nullable=True),          # non-unique (D-01)
      Column("display_name", Text, nullable=True),
      Column("profile_url", Text, nullable=True),
      Column("avatar_url", Text, nullable=True),             # URL string only (D-05)
      Column("follower_count", Integer, nullable=True),      # scalar (D-04)
      Column("is_verified", Boolean, nullable=True),
      Column("is_orphan", Boolean, nullable=False, default=False),
      Column("first_seen_at", DateTime(timezone=True), nullable=True),
      Column("last_seen_at", DateTime(timezone=True), nullable=True),
      Column(
          "created_at",
          DateTime(timezone=True),
          nullable=False,
          default=_utc_now,
      ),
      # Compound UNIQUE on (platform, platform_user_id) — D-01 canonical
      # identity. Same uploader_id on different platforms is allowed
      # (no cross-platform identity resolution in M006).
      UniqueConstraint(
          "platform",
          "platform_user_id",
          name="uq_creators_platform_user_id",
      ),
  )

  # Indexes on both sides of the creator<->video relationship.
  Index("idx_creators_handle", creators.c.platform, creators.c.handle)
  Index("idx_videos_creator_id", videos.c.creator_id)
  ```

  Ajouter `Index` à l'import SQLAlchemy en haut du fichier (ligne 38-53) :

  ```python
  from sqlalchemy import (
      JSON,
      Boolean,
      Column,
      DateTime,
      Engine,
      Float,
      ForeignKey,
      Index,
      Integer,
      MetaData,
      String,
      Table,
      Text,
      UniqueConstraint,
      text,
  )
  ```

  **3. Ajouter le helper idempotent `_ensure_videos_creator_id(conn)` et l'appeler dans `init_db`**. Localiser `init_db` (ligne 215-224) et `_create_fts5` (ligne 227-229). Modifier `init_db` pour appeler le nouveau helper après `_create_fts5` :

  ```python
  def init_db(engine: Engine) -> None:
      """Create every table and the FTS5 virtual table. Idempotent.

      Safe to call on every startup — :meth:`MetaData.create_all` uses
      ``CREATE TABLE IF NOT EXISTS`` under the hood, and the FTS5 DDL
      plus the ``_ensure_videos_creator_id`` helper both guard
      themselves against double-execution on upgraded DBs.
      """
      metadata.create_all(engine)
      with engine.begin() as conn:
          _create_fts5(conn)
          _ensure_videos_creator_id(conn)
  ```

  Ajouter le helper après `_create_fts5` :

  ```python
  def _ensure_videos_creator_id(conn: Connection) -> None:
      """Add ``videos.creator_id`` on upgraded databases. Idempotent.

      M006/S01 adds a nullable FK column ``videos.creator_id``. On fresh
      installs the Core ``metadata.create_all`` path declares the column
      inline (see the ``videos`` Table definition above). On pre-M006
      databases the ``videos`` table already exists, so ``create_all``
      is a no-op — we must explicitly ALTER it.

      SQLite supports ``ALTER TABLE ADD COLUMN ... REFERENCES`` as of
      3.26 (2018). The inline ``ON DELETE SET NULL`` is honored because
      ``PRAGMA foreign_keys`` is enabled on every connection by
      ``sqlite_engine._apply_sqlite_pragmas``.
      """
      cols = {
          row[1]
          for row in conn.execute(text("PRAGMA table_info(videos)"))
      }
      if "creator_id" in cols:
          return
      conn.execute(
          text(
              "ALTER TABLE videos ADD COLUMN creator_id INTEGER "
              "REFERENCES creators(id) ON DELETE SET NULL"
          )
      )
  ```

  Mettre à jour `__all__` (lignes 56-66) pour inclure `"creators"` en ordre alphabétique :

  ```python
  __all__ = [
      "analyses",
      "creators",
      "frames",
      "init_db",
      "metadata",
      "pipeline_runs",
      "transcripts",
      "videos",
      "watch_refreshes",
      "watched_accounts",
  ]
  ```
  </action>

  <acceptance_criteria>
    - `grep -q 'creators = Table(' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '"platform_user_id"' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q "uq_creators_platform_user_id" src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q "idx_creators_handle" src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q "idx_videos_creator_id" src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q "def _ensure_videos_creator_id" src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'ForeignKey("creators.id", ondelete="SET NULL")' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '"creators"' src/vidscope/adapters/sqlite/schema.py` exit 0 (présent dans `__all__`)
    - `python -m uv run python -c "import tempfile; from pathlib import Path; from vidscope.adapters.sqlite.schema import init_db, metadata; from vidscope.infrastructure.sqlite_engine import build_engine; from sqlalchemy import inspect; d=tempfile.mkdtemp(); eng=build_engine(Path(d)/'t.db'); init_db(eng); names=set(inspect(eng).get_table_names()); assert 'creators' in names, names; cols={c['name'] for c in inspect(eng).get_columns('videos')}; assert 'creator_id' in cols, cols; print('OK')"` sort `OK`
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q` exit 0 (les tests existants restent verts, les nouveaux ajoutés dans T07 passent)
  </acceptance_criteria>
</task>

<task id="T07-schema-tests">
  <name>Tests schéma : table creators, UNIQUE, FK SET NULL, ALTER idempotent (fresh install + upgrade path)</name>

  <read_first>
    - `tests/unit/adapters/sqlite/test_schema.py` — fichier existant avec `TestInitDb` (4 méthodes). Ajouter de nouvelles classes ; ne pas modifier les existantes.
    - `tests/unit/adapters/sqlite/conftest.py` — fixture `engine` (`tmp_path / 'test.db'` + `init_db`). Réutiliser.
    - `src/vidscope/adapters/sqlite/schema.py` — forme définitive après T06
    - `src/vidscope/infrastructure/sqlite_engine.py` — `build_engine` et listener PRAGMA
  </read_first>

  <action>
  Étendre `tests/unit/adapters/sqlite/test_schema.py`. Ajouter DEUX nouvelles classes à la fin du fichier :

  ```python
  class TestCreatorsSchema:
      """Schema-level tests for the creators table (M006/S01)."""

      def test_creators_table_exists(self, engine: Engine) -> None:
          names = set(inspect(engine).get_table_names())
          assert "creators" in names

      def test_videos_creator_id_column_exists(self, engine: Engine) -> None:
          cols = {c["name"] for c in inspect(engine).get_columns("videos")}
          assert "creator_id" in cols

      def test_creators_unique_platform_user_id_enforced(
          self, engine: Engine
      ) -> None:
          from sqlalchemy.exc import IntegrityError

          with engine.begin() as conn:
              conn.execute(
                  text(
                      "INSERT INTO creators (platform, platform_user_id, is_orphan) "
                      "VALUES ('youtube', 'UC_ABC', 0)"
                  )
              )
          # Same (platform, platform_user_id) must fail the compound UNIQUE.
          with pytest.raises(IntegrityError), engine.begin() as conn:
              conn.execute(
                  text(
                      "INSERT INTO creators (platform, platform_user_id, is_orphan) "
                      "VALUES ('youtube', 'UC_ABC', 0)"
                  )
              )

      def test_same_platform_user_id_across_platforms_ok(
          self, engine: Engine
      ) -> None:
          # D-01 scope: no cross-platform identity resolution.
          with engine.begin() as conn:
              conn.execute(
                  text(
                      "INSERT INTO creators (platform, platform_user_id, is_orphan) "
                      "VALUES ('youtube', 'shared_id', 0)"
                  )
              )
              conn.execute(
                  text(
                      "INSERT INTO creators (platform, platform_user_id, is_orphan) "
                      "VALUES ('tiktok', 'shared_id', 0)"
                  )
              )
              total = conn.execute(
                  text("SELECT COUNT(*) FROM creators")
              ).scalar()
              assert total == 2

      def test_videos_creator_id_set_null_on_creator_delete(
          self, engine: Engine
      ) -> None:
          with engine.begin() as conn:
              conn.execute(
                  text(
                      "INSERT INTO creators (id, platform, platform_user_id, is_orphan) "
                      "VALUES (100, 'youtube', 'UC_DEL', 0)"
                  )
              )
              conn.execute(
                  text(
                      "INSERT INTO videos "
                      "(platform, platform_id, url, creator_id) "
                      "VALUES ('youtube', 'v_del', 'https://x', 100)"
                  )
              )

              # Delete creator — videos row must survive with creator_id = NULL
              conn.execute(text("DELETE FROM creators WHERE id = 100"))
              row = conn.execute(
                  text(
                      "SELECT creator_id FROM videos WHERE platform_id = 'v_del'"
                  )
              ).first()
              assert row is not None
              assert row[0] is None  # ON DELETE SET NULL fired

      def test_idx_creators_handle_exists(self, engine: Engine) -> None:
          indexes = inspect(engine).get_indexes("creators")
          names = {idx["name"] for idx in indexes}
          assert "idx_creators_handle" in names

      def test_idx_videos_creator_id_exists(self, engine: Engine) -> None:
          indexes = inspect(engine).get_indexes("videos")
          names = {idx["name"] for idx in indexes}
          assert "idx_videos_creator_id" in names


  class TestVideosCreatorIdAlter:
      """Tests for ``_ensure_videos_creator_id`` idempotency.

      Two paths must work:
      1. Fresh install — videos.creator_id declared inline on the Table.
      2. Upgrade path — pre-M006 videos table exists WITHOUT the column;
         _ensure_videos_creator_id must ALTER it in.
      """

      def test_ensure_idempotent_on_fresh_install(
          self, engine: Engine
      ) -> None:
          # engine fixture already ran init_db once. Run it again.
          from vidscope.adapters.sqlite.schema import init_db

          init_db(engine)
          init_db(engine)  # third call, still no error
          cols = {c["name"] for c in inspect(engine).get_columns("videos")}
          assert "creator_id" in cols

      def test_upgrade_path_adds_creator_id(self, tmp_path) -> None:
          """Simulate a pre-M006 DB: create videos WITHOUT creator_id,
          then run init_db and assert the column gets added.
          """
          from vidscope.adapters.sqlite.schema import init_db
          from vidscope.infrastructure.sqlite_engine import build_engine

          db_path = tmp_path / "pre_m006.db"
          eng = build_engine(db_path)

          # Pre-M006 minimal videos table (no creator_id)
          with eng.begin() as conn:
              conn.execute(
                  text(
                      "CREATE TABLE videos ("
                      "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                      "platform TEXT NOT NULL, "
                      "platform_id TEXT NOT NULL UNIQUE, "
                      "url TEXT NOT NULL, "
                      "author TEXT, "
                      "title TEXT, "
                      "duration REAL, "
                      "upload_date TEXT, "
                      "view_count INTEGER, "
                      "media_key TEXT, "
                      "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                      ")"
                  )
              )
              # Seed one row so we know data survives the ALTER
              conn.execute(
                  text(
                      "INSERT INTO videos (platform, platform_id, url, author) "
                      "VALUES ('youtube', 'legacy_v1', 'https://x', 'Old Author')"
                  )
              )

          # Now run init_db — should add creator_id without losing data
          init_db(eng)

          cols = {c["name"] for c in inspect(eng).get_columns("videos")}
          assert "creator_id" in cols

          with eng.connect() as conn:
              row = conn.execute(
                  text(
                      "SELECT author, creator_id FROM videos "
                      "WHERE platform_id = 'legacy_v1'"
                  )
              ).first()
              assert row is not None
              assert row[0] == "Old Author"  # data preserved
              assert row[1] is None  # new column defaults to NULL

      def test_ensure_creator_id_helper_directly_idempotent(
          self, tmp_path
      ) -> None:
          """Call _ensure_videos_creator_id twice explicitly to pin
          the PRAGMA table_info guard.
          """
          from vidscope.adapters.sqlite.schema import (
              _ensure_videos_creator_id,
              init_db,
          )
          from vidscope.infrastructure.sqlite_engine import build_engine

          eng = build_engine(tmp_path / "idem.db")
          init_db(eng)
          with eng.begin() as conn:
              _ensure_videos_creator_id(conn)  # second call, no error
              _ensure_videos_creator_id(conn)  # third call, no error
  ```

  Mettre à jour les imports en haut de `test_schema.py` pour inclure `pytest` si absent (pour `pytest.raises`). Les imports existants (`Engine`, `inspect`, `text`) restent.
  </action>

  <acceptance_criteria>
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py::TestCreatorsSchema -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py::TestVideosCreatorIdAlter -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q` exit 0 (toutes les classes : existantes + nouvelles)
    - `grep -q "test_ensure_idempotent_on_fresh_install" tests/unit/adapters/sqlite/test_schema.py` exit 0
    - `grep -q "test_upgrade_path_adds_creator_id" tests/unit/adapters/sqlite/test_schema.py` exit 0
    - `grep -q "test_videos_creator_id_set_null_on_creator_delete" tests/unit/adapters/sqlite/test_schema.py` exit 0
    - `grep -q "test_same_platform_user_id_across_platforms_ok" tests/unit/adapters/sqlite/test_schema.py` exit 0
    - `python -m uv run pytest -q` exit 0 (suite complète verte)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests par couche
python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py::TestCreatorsSchema -x -q
python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py::TestVideosCreatorIdAlter -x -q

# Suite complète (schema + ports + aucune régression)
python -m uv run pytest -q

# Quality gates
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports

# Inspection SQL directe (sanity check)
python -m uv run python -c "from sqlalchemy import inspect; import tempfile; from pathlib import Path; from vidscope.adapters.sqlite.schema import init_db; from vidscope.infrastructure.sqlite_engine import build_engine; d=tempfile.mkdtemp(); eng=build_engine(Path(d)/'t.db'); init_db(eng); i=inspect(eng); print('tables:', sorted(i.get_table_names())); print('videos cols:', sorted(c['name'] for c in i.get_columns('videos'))); print('creators indexes:', [x['name'] for x in i.get_indexes('creators')])"
```

## Must-Haves

- `CreatorRepository` Protocol existe dans `vidscope.ports.repositories` et est re-exporté par `vidscope.ports` (`from vidscope.ports import CreatorRepository` fonctionne)
- Signatures du Protocol : `upsert`, `get`, `find_by_platform_user_id`, `find_by_handle`, `list_by_platform`, `list_by_min_followers`, `count` (7 méthodes)
- Aucun fichier `ports/creator_repository.py` créé (la convention du projet est un fichier unique)
- Table `creators` déclarée dans `schema.py::metadata` avec la forme SQL canonique (CONTEXT.md §D-01) : 13 colonnes, `UniqueConstraint("platform", "platform_user_id")`, `Index("idx_creators_handle")`
- Colonne `videos.creator_id` déclarée inline `ForeignKey("creators.id", ondelete="SET NULL")` + `Index("idx_videos_creator_id")` sur fresh installs
- Helper `_ensure_videos_creator_id(conn)` idempotent ajoute la colonne sur les DB M001–M005 existantes via `PRAGMA table_info(videos)` + `ALTER TABLE` conditionnel
- Tests schéma couvrent : présence table, UNIQUE actif, FK SET NULL effective, index présents, fresh install OK, upgrade path OK (données M001–M005 survivent), idempotence sur appels répétés
- 9 contrats import-linter restent verts
- P03 peut désormais implémenter `SqlCreatorRepository` contre le Protocol et la Table

## Threat Model

| # | STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-P02-01 | **Tampering (T)** — Schema drift | `init_db` sur DB existante | MEDIUM | mitigate | `_ensure_videos_creator_id` est strictement conditionnel (`if "creator_id" in cols: return`). Le test `test_ensure_creator_id_helper_directly_idempotent` pin cette invariante. Si un attaquant modifie la DB pour créer une colonne `creator_id` du mauvais type, SQLite la préservera — mais le risque est confiné au tool local (D032 : single-user local tool). |
| T-P02-02 | **Data corruption** — FK orphans | Contrainte FK `videos.creator_id → creators.id` | MEDIUM | mitigate | `ON DELETE SET NULL` choisi (pas `CASCADE`) pour préserver les vidéos si un créateur est supprimé. Listener `PRAGMA foreign_keys=ON` garanti sur chaque connexion (`sqlite_engine.py:57`). Test `test_videos_creator_id_set_null_on_creator_delete` vérifie le comportement. |
| T-P02-03 | **Availability** — init_db lent sur grosses DB | Helper ALTER | LOW | accept | `ALTER TABLE ADD COLUMN` en SQLite est O(1) (pas de rewrite). `PRAGMA table_info` est instantané. Acceptable. |
| T-P02-04 | **Information Disclosure (I)** — logging du schéma | `init_db` | NONE | accept | `init_db` n'émet aucun log ; les données du schéma ne sont pas sensibles (publiques dans la doc). |

Pas de surface réseau ni d'entrée utilisateur parsée dans ce plan : les injections SQL potentielles sur `handle`/`display_name` apparaissent dans P03 (repository write path) et sont mitigées là-bas par les paramètres SQLAlchemy Core.
