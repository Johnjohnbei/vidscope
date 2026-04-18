---
plan_id: S01-P02
phase: M007/S01
wave: 2
depends_on: [S01-P01]
requirements: [R043, R045]
files_modified:
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/adapters/sqlite/hashtag_repository.py
  - src/vidscope/adapters/sqlite/mention_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/__init__.py
  - tests/unit/adapters/sqlite/test_hashtag_repository.py
  - tests/unit/adapters/sqlite/test_mention_repository.py
  - tests/unit/adapters/sqlite/test_video_repository.py
  - tests/unit/adapters/sqlite/test_schema.py
autonomous: true
---

## Objective

Livrer la couche persistance SQLite pour les nouveaux champs M007 : (1) schema.py — nouveau helper `_ensure_videos_metadata_columns` qui `ALTER TABLE videos ADD COLUMN description/music_track/music_artist` de façon idempotente (patron exact de `_ensure_videos_creator_id`), nouvelles tables `hashtags` et `mentions` avec FK `video_id` + index, appel dans `init_db` (2) ports — Protocols `HashtagRepository` et `MentionRepository` avec `replace_for_video`, `list_for_video`, `find_videos_by_tag`/`find_videos_by_handle` (EXISTS subqueries pour D-04) (3) adapters SQLite — `HashtagRepositorySQLite` et `MentionRepositorySQLite` en miroir exact du patron `CreatorRepositorySQLite` (4) `VideoRepositorySQLite` — `_video_to_row` / `_row_to_video` étendus pour les 3 nouvelles colonnes (5) `UnitOfWork` — 2 nouveaux attributs `hashtags` / `mentions` en port + adapter (6) tests — ≥ 8 tests par repo (seuil RESEARCH.md), CRUD + cascade delete + filter + round-trip Video avec nouveaux champs.

## Tasks

<task id="T01-schema-migration">
  <name>Étendre schema.py : ALTER TABLE videos + tables hashtags/mentions (idempotent)</name>

  <read_first>
    - `src/vidscope/adapters/sqlite/schema.py` — fichier complet, en particulier : lignes 83-103 (`videos` Table def actuelle), lignes 206-235 (`creators` Table — patron pour les nouvelles tables avec FK), lignes 279-304 (`_ensure_videos_creator_id` — patron exact à miroir pour `_ensure_videos_metadata_columns`), lignes 260-271 (`init_db` où ajouter l'appel)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Pattern migration SQLAlchemy (ALTER TABLE)" et §"Pattern schema SQLAlchemy Core"
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-01 (3 colonnes directes sur `videos`) et §D-05 (side tables hashtags/mentions avec FK `video_id`)
    - `.importlinter` — contrats `sqlite-never-imports-fs`, `llm-never-imports-other-adapters` (restent verts : on ne modifie que `adapters/sqlite/`)
  </read_first>

  <action>
  Ouvrir `src/vidscope/adapters/sqlite/schema.py`. Effectuer 4 modifications dans cet ordre :

  **Étape A — Ajouter 3 colonnes inline sur la table `videos`** (pour que `metadata.create_all` les crée sur fresh installs). Localiser la définition de `videos` (lignes 83-103) et ajouter les 3 nouvelles colonnes AVANT `Column("creator_id", ...)` :

  ```python
  videos = Table(
      "videos",
      metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("platform", String(32), nullable=False),
      Column("platform_id", String(128), nullable=False, unique=True),
      Column("url", Text, nullable=False),
      Column("author", String(255), nullable=True),
      Column("title", Text, nullable=True),
      Column("duration", Float, nullable=True),
      Column("upload_date", String(32), nullable=True),
      Column("view_count", Integer, nullable=True),
      Column("media_key", Text, nullable=True),
      Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
      Column(
          "creator_id",
          Integer,
          ForeignKey("creators.id", ondelete="SET NULL"),
          nullable=True,
      ),
      Column("description", Text, nullable=True),
      Column("music_track", String(255), nullable=True),
      Column("music_artist", String(255), nullable=True),
  )
  ```

  **Étape B — Ajouter deux nouvelles tables `hashtags` et `mentions`** APRÈS `creators` (ligne ~235) et AVANT la section `# ---------------------------------------------------------------------------\n# FTS5 virtual table DDL` :

  ```python
  # M007: hashtag side table (D-05)
  hashtags = Table(
      "hashtags",
      metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column(
          "video_id",
          Integer,
          ForeignKey("videos.id", ondelete="CASCADE"),
          nullable=False,
      ),
      # Canonical lowercase form without the leading "#" (D-04 exact match).
      Column("tag", String(255), nullable=False),
      Column(
          "created_at",
          DateTime(timezone=True),
          nullable=False,
          default=_utc_now,
      ),
  )
  Index("idx_hashtags_video_id", hashtags.c.video_id)
  Index("idx_hashtags_tag", hashtags.c.tag)

  # M007: mention side table (D-03, D-05). handle is canonical lowercase
  # without the leading "@". No creator_id FK (per D-03) — mention↔creator
  # linkage derivable via JOIN in M011 only.
  mentions = Table(
      "mentions",
      metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column(
          "video_id",
          Integer,
          ForeignKey("videos.id", ondelete="CASCADE"),
          nullable=False,
      ),
      Column("handle", String(255), nullable=False),
      Column("platform", String(32), nullable=True),  # Platform | None (D-03)
      Column(
          "created_at",
          DateTime(timezone=True),
          nullable=False,
          default=_utc_now,
      ),
  )
  Index("idx_mentions_video_id", mentions.c.video_id)
  Index("idx_mentions_handle", mentions.c.handle)
  ```

  **Étape C — Ajouter un nouveau helper `_ensure_videos_metadata_columns`** APRÈS `_ensure_videos_creator_id` (ligne ~304). Copie exacte du patron existant, en itérant sur les 3 colonnes :

  ```python
  def _ensure_videos_metadata_columns(conn: Connection) -> None:
      """Add M007 metadata columns on upgraded databases. Idempotent.

      M007/S01 adds three nullable columns on ``videos``: ``description``,
      ``music_track``, ``music_artist`` (per D-01 — no side entity). On
      fresh installs the Core ``metadata.create_all`` path declares the
      columns inline (see the ``videos`` Table definition above). On
      pre-M007 databases the ``videos`` table already exists, so
      ``create_all`` is a no-op — we must explicitly ALTER it for each
      missing column.
      """
      cols = {
          row[1]
          for row in conn.execute(text("PRAGMA table_info(videos)"))
      }
      if "description" not in cols:
          conn.execute(text("ALTER TABLE videos ADD COLUMN description TEXT"))
      if "music_track" not in cols:
          conn.execute(
              text("ALTER TABLE videos ADD COLUMN music_track VARCHAR(255)")
          )
      if "music_artist" not in cols:
          conn.execute(
              text("ALTER TABLE videos ADD COLUMN music_artist VARCHAR(255)")
          )
  ```

  **Étape D — Appeler le nouveau helper dans `init_db`** (lignes 260-271). Remplacer le corps actuel par :

  ```python
  def init_db(engine: Engine) -> None:
      """Create every table and the FTS5 virtual table. Idempotent.

      Safe to call on every startup — :meth:`MetaData.create_all` uses
      ``CREATE TABLE IF NOT EXISTS`` under the hood, and the FTS5 DDL
      plus the ``_ensure_*`` helpers both guard themselves against
      double-execution on upgraded DBs.
      """
      metadata.create_all(engine)
      with engine.begin() as conn:
          _create_fts5(conn)
          _ensure_videos_creator_id(conn)
          _ensure_videos_metadata_columns(conn)
  ```

  **Étape E — Mettre à jour `__all__`** (lignes 57-68) pour exporter `hashtags` et `mentions` en respectant l'ordre alphabétique :

  ```python
  __all__ = [
      "analyses",
      "creators",
      "frames",
      "hashtags",
      "init_db",
      "mentions",
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
    - `grep -q 'Column("description", Text, nullable=True)' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'Column("music_track", String(255), nullable=True)' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'Column("music_artist", String(255), nullable=True)' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'hashtags = Table(' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'mentions = Table(' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'def _ensure_videos_metadata_columns' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '_ensure_videos_metadata_columns(conn)' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '"hashtags"' src/vidscope/adapters/sqlite/schema.py` exit 0 (dans `__all__`)
    - `grep -q '"mentions"' src/vidscope/adapters/sqlite/schema.py` exit 0 (dans `__all__`)
    - `python -m uv run python -c "from sqlalchemy import create_engine; from vidscope.adapters.sqlite.schema import init_db; e = create_engine('sqlite:///:memory:'); init_db(e); e.connect().execute(__import__('sqlalchemy').text('SELECT sql FROM sqlite_master WHERE name=\"hashtags\"')).scalar()"` retourne non-NULL (table créée)
    - `python -m uv run pytest tests/unit/adapters/sqlite/ -x -q` exit 0 (aucune régression sur les tests schema existants)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (9 contrats verts)
  </acceptance_criteria>
</task>

<task id="T02-ports-and-uow-extension">
  <name>Ajouter HashtagRepository + MentionRepository Protocols et les wire dans UnitOfWork</name>

  <read_first>
    - `src/vidscope/ports/repositories.py` lignes 313-380 — patron `CreatorRepository` Protocol avec méthodes read/write à miroir pour les 2 nouveaux Protocols
    - `src/vidscope/ports/unit_of_work.py` lignes 31-40 (imports repos) et 52-80 (UnitOfWork Protocol attributs) — à étendre avec `hashtags` / `mentions`
    - `src/vidscope/ports/__init__.py` — re-exports à mettre à jour
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Pattern UnitOfWork extension" (montre la forme attendue) + §"Pattern side table avec FK video_id" (signatures méthodes)
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-04 (EXISTS subqueries pour facettes AND implicite)
    - `.importlinter` — `ports-are-pure` (pas d'import third-party)
  </read_first>

  <action>
  **Étape A — Étendre `src/vidscope/ports/repositories.py`**. Ajouter 2 nouveaux Protocols à la fin du fichier (après `CreatorRepository`, ligne ~380). Mettre à jour les imports depuis `vidscope.domain` en haut pour inclure `Hashtag` et `Mention`. Mettre à jour `__all__` (lignes 49-58).

  Imports à étendre (lignes 31-47) :

  ```python
  from vidscope.domain import (
      Analysis,
      Creator,
      CreatorId,
      Frame,
      Hashtag,
      Mention,
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

  `__all__` à étendre :

  ```python
  __all__ = [
      "AnalysisRepository",
      "CreatorRepository",
      "FrameRepository",
      "HashtagRepository",
      "MentionRepository",
      "PipelineRunRepository",
      "TranscriptRepository",
      "VideoRepository",
      "WatchAccountRepository",
      "WatchRefreshRepository",
  ]
  ```

  Nouveaux Protocols à ajouter à la fin du fichier :

  ```python
  @runtime_checkable
  class HashtagRepository(Protocol):
      """Persistence for :class:`~vidscope.domain.entities.Hashtag`.

      Hashtags are stored in a side table keyed by ``(video_id, tag)``.
      ``tag`` is the canonical lowercase form WITHOUT the leading ``#``
      (per M007 D-04). The repository applies the canonicalisation
      itself — callers pass raw tags from yt-dlp's ``info["tags"]``
      (already lowercase-ish but not always) and the adapter calls
      ``.lower().lstrip("#")`` before writing.
      """

      def replace_for_video(self, video_id: VideoId, tags: list[str]) -> None:
          """Replace every hashtag row for ``video_id`` with ``tags``.

          Implemented as DELETE then INSERT — idempotent on re-ingest,
          the whole list is the new truth. Empty ``tags`` removes every
          row for the video. Each tag is canonicalised by the adapter
          (lowercase + strip leading '#') before insertion.
          """
          ...

      def list_for_video(self, video_id: VideoId) -> list[Hashtag]:
          """Return every hashtag row for ``video_id`` ordered by id asc.

          Empty list on miss — never raises.
          """
          ...

      def find_video_ids_by_tag(
          self, tag: str, *, limit: int = 50
      ) -> list[VideoId]:
          """Return up to ``limit`` video ids whose hashtags include ``tag``.

          ``tag`` is canonicalised by the repository before comparison so
          callers can pass ``"#Coding"`` or ``"coding"`` interchangeably
          (per D-04). Used by the search facet ``--hashtag`` via
          EXISTS subquery (M007/S04).
          """
          ...


  @runtime_checkable
  class MentionRepository(Protocol):
      """Persistence for :class:`~vidscope.domain.entities.Mention`.

      Mentions are stored in a side table keyed by
      ``(video_id, handle)``. ``handle`` is the canonical lowercase form
      WITHOUT the leading ``@``. ``platform`` is optional per D-03. No
      ``creator_id`` FK — mention↔creator linkage is derivable via JOIN
      in M011.
      """

      def replace_for_video(
          self, video_id: VideoId, mentions: list[Mention]
      ) -> None:
          """Replace every mention row for ``video_id`` with ``mentions``.

          Implemented as DELETE then INSERT — idempotent on re-ingest.
          Empty list removes every row for the video. The repository
          canonicalises each mention's ``handle`` (lowercase + strip
          leading '@') before insertion.
          """
          ...

      def list_for_video(self, video_id: VideoId) -> list[Mention]:
          """Return every mention row for ``video_id`` ordered by id asc.

          Empty list on miss — never raises.
          """
          ...

      def find_video_ids_by_handle(
          self, handle: str, *, limit: int = 50
      ) -> list[VideoId]:
          """Return up to ``limit`` video ids mentioning ``handle``.

          ``handle`` is canonicalised before comparison (case-insensitive
          per D-04). Used by the search facet ``--mention`` via EXISTS
          subquery (M007/S04).
          """
          ...
  ```

  **Étape B — Étendre `src/vidscope/ports/unit_of_work.py`**. Mettre à jour l'import de `repositories` (lignes 31-40) pour inclure les 2 nouveaux Protocols, puis ajouter les 2 nouveaux attributs au Protocol `UnitOfWork` (lignes 52-80) :

  Imports mis à jour :

  ```python
  from vidscope.ports.repositories import (
      AnalysisRepository,
      CreatorRepository,
      FrameRepository,
      HashtagRepository,
      MentionRepository,
      PipelineRunRepository,
      TranscriptRepository,
      VideoRepository,
      WatchAccountRepository,
      WatchRefreshRepository,
  )
  ```

  Ajouter DANS le Protocol `UnitOfWork` (après `analyses` et avant `pipeline_runs` pour grouper les repos "contenu vidéo") :

  ```python
      creators: CreatorRepository
      videos: VideoRepository
      transcripts: TranscriptRepository
      frames: FrameRepository
      analyses: AnalysisRepository
      hashtags: HashtagRepository
      mentions: MentionRepository
      pipeline_runs: PipelineRunRepository
      search_index: SearchIndex
      watch_accounts: WatchAccountRepository
      watch_refreshes: WatchRefreshRepository
  ```

  **Étape C — Mettre à jour `src/vidscope/ports/__init__.py`** pour re-exporter `HashtagRepository` et `MentionRepository`. Ouvrir le fichier, localiser les imports depuis `.repositories`, ajouter les 2 nouveaux symboles dans l'ordre alphabétique, et les ajouter à `__all__`.
  </action>

  <acceptance_criteria>
    - `grep -q "class HashtagRepository(Protocol):" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "class MentionRepository(Protocol):" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def replace_for_video" src/vidscope/ports/repositories.py` retourne ≥ 2 occurrences (`grep -c` ≥ 2)
    - `grep -q "def find_video_ids_by_tag" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def find_video_ids_by_handle" src/vidscope/ports/repositories.py` exit 0
    - `grep -q '"HashtagRepository"' src/vidscope/ports/repositories.py` exit 0 (dans `__all__`)
    - `grep -q '"MentionRepository"' src/vidscope/ports/repositories.py` exit 0 (dans `__all__`)
    - `grep -q "hashtags: HashtagRepository" src/vidscope/ports/unit_of_work.py` exit 0
    - `grep -q "mentions: MentionRepository" src/vidscope/ports/unit_of_work.py` exit 0
    - `grep -q "HashtagRepository" src/vidscope/ports/__init__.py` exit 0
    - `grep -q "MentionRepository" src/vidscope/ports/__init__.py` exit 0
    - `python -m uv run python -c "from vidscope.ports import HashtagRepository, MentionRepository, UnitOfWork; print(HashtagRepository.__name__, MentionRepository.__name__)"` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `ports-are-pure` vert — pas de third-party import ajouté)
  </acceptance_criteria>
</task>

<task id="T03-sqlite-adapters-and-uow" tdd="true">
  <name>Implémenter HashtagRepositorySQLite + MentionRepositorySQLite, étendre VideoRepositorySQLite et SqliteUnitOfWork + tests</name>

  <read_first>
    - `src/vidscope/adapters/sqlite/creator_repository.py` — patron exact à miroir pour les 2 nouveaux adapters (structure + `_row_to_entity` + SQLAlchemy Core patterns + StorageError wrap)
    - `src/vidscope/adapters/sqlite/video_repository.py` — `_video_to_row` (lignes 173-188) et `_row_to_video` (lignes 191-211) à étendre avec les 3 nouvelles colonnes
    - `src/vidscope/adapters/sqlite/unit_of_work.py` — lignes 77-101 (slots déclarés + instantiation dans `__enter__`) à étendre
    - `src/vidscope/adapters/sqlite/schema.py` — localiser les Table objects `hashtags` et `mentions` (créés dans T01)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"S01 — tests cibles" (seuil ≥ 8 tests par repo)
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-04 (canonicalisation : `#Coding` == `#coding` ⇒ adapter lowercase + lstrip '#')
    - tests existants `tests/unit/adapters/sqlite/test_creator_repository.py` (si présent) — patron de test à copier pour les nouveaux repos
  </read_first>

  <behavior>
    - Test 1 (Hashtag repo): `replace_for_video(vid, ["cooking", "recipes"])` insère 2 rows ; `list_for_video(vid)` retourne 2 `Hashtag` instances avec `tag="cooking"` et `tag="recipes"` dans l'ordre d'insertion.
    - Test 2 (Hashtag repo): `replace_for_video(vid, ["#Coding"])` puis `list_for_video(vid)[0].tag == "coding"` (canonicalisation lowercase + lstrip '#').
    - Test 3 (Hashtag repo): `replace_for_video(vid, ["a"])` puis `replace_for_video(vid, ["b"])` → `list_for_video(vid)` retourne seulement `[Hashtag(..., tag="b")]` (DELETE-INSERT idempotent).
    - Test 4 (Hashtag repo): `replace_for_video(vid, [])` supprime toutes les rows ; `list_for_video(vid) == []`.
    - Test 5 (Hashtag repo): cascade delete — delete video row puis `list_for_video(vid) == []` (ondelete=CASCADE).
    - Test 6 (Hashtag repo): `find_video_ids_by_tag("cooking")` retourne la liste de VideoId matchant.
    - Test 7 (Hashtag repo): `find_video_ids_by_tag("#Cooking")` = `find_video_ids_by_tag("cooking")` (canonicalisation input).
    - Test 8 (Hashtag repo): `list_for_video` sur video inexistant retourne `[]` (jamais d'exception).
    - Test 9-16 (Mention repo): symétriques avec `handle` et lstrip '@', plus test sur `platform` optionnel (None + Platform.TIKTOK).
    - Test 17 (Video repo): `add` puis `get` d'un `Video` avec `description="hi"`, `music_track="Song"`, `music_artist="X"` → round-trip preserve les 3 champs.
    - Test 18 (Video repo): `add` d'un `Video` sans les champs M007 → `get` retourne `description=None`, `music_track=None`, `music_artist=None` (backward compat).
    - Test 19 (UoW): `with uow:` expose `uow.hashtags` et `uow.mentions` comme attributs utilisables.
    - Test 20 (schema): `init_db` idempotent — appeler 2x sur un engine ne crash pas et les tables existent.
  </behavior>

  <action>
  **Étape A — Créer `src/vidscope/adapters/sqlite/hashtag_repository.py`** (miroir exact de `creator_repository.py`) :

  ```python
  """SQLite implementation of :class:`HashtagRepository`.

  Uses SQLAlchemy Core exclusively. Every method takes a
  :class:`sqlalchemy.engine.Connection` (bound to an open transaction by
  the unit of work) so hashtag writes can be grouped atomically with
  video writes in the same :class:`IngestStage` transaction.
  """

  from __future__ import annotations

  from datetime import UTC, datetime
  from typing import Any, cast

  from sqlalchemy import delete, select
  from sqlalchemy.engine import Connection

  from vidscope.adapters.sqlite.schema import hashtags as hashtags_table
  from vidscope.domain import Hashtag, VideoId
  from vidscope.domain.errors import StorageError

  __all__ = ["HashtagRepositorySQLite"]


  def _canonicalise_tag(tag: str) -> str:
      """Return the canonical form of ``tag``: lowercase + strip leading '#'.

      Applied consistently across write and lookup paths so callers can
      pass ``"#Cooking"`` or ``"cooking"`` interchangeably (per M007 D-04).
      """
      return tag.lower().lstrip("#").strip()


  class HashtagRepositorySQLite:
      """Repository for :class:`Hashtag` backed by SQLite."""

      def __init__(self, connection: Connection) -> None:
          self._conn = connection

      # ------------------------------------------------------------------
      # Writes
      # ------------------------------------------------------------------

      def replace_for_video(self, video_id: VideoId, tags: list[str]) -> None:
          """DELETE existing rows for ``video_id`` then INSERT every tag.

          Canonicalises each tag (lowercase + strip leading '#') and
          deduplicates within the call — empty strings after
          canonicalisation are dropped silently.
          """
          try:
              self._conn.execute(
                  delete(hashtags_table).where(
                      hashtags_table.c.video_id == int(video_id)
                  )
              )
              seen: set[str] = set()
              canonicalised: list[dict[str, Any]] = []
              now = datetime.now(UTC)
              for raw in tags:
                  canon = _canonicalise_tag(raw)
                  if not canon or canon in seen:
                      continue
                  seen.add(canon)
                  canonicalised.append(
                      {
                          "video_id": int(video_id),
                          "tag": canon,
                          "created_at": now,
                      }
                  )
              if canonicalised:
                  self._conn.execute(
                      hashtags_table.insert().values(canonicalised)
                  )
          except Exception as exc:
              raise StorageError(
                  f"replace_for_video failed for hashtags of video "
                  f"{int(video_id)}: {exc}",
                  cause=exc,
              ) from exc

      # ------------------------------------------------------------------
      # Reads
      # ------------------------------------------------------------------

      def list_for_video(self, video_id: VideoId) -> list[Hashtag]:
          rows = (
              self._conn.execute(
                  select(hashtags_table)
                  .where(hashtags_table.c.video_id == int(video_id))
                  .order_by(hashtags_table.c.id.asc())
              )
              .mappings()
              .all()
          )
          return [_row_to_hashtag(row) for row in rows]

      def find_video_ids_by_tag(
          self, tag: str, *, limit: int = 50
      ) -> list[VideoId]:
          canon = _canonicalise_tag(tag)
          if not canon:
              return []
          rows = (
              self._conn.execute(
                  select(hashtags_table.c.video_id)
                  .where(hashtags_table.c.tag == canon)
                  .order_by(hashtags_table.c.id.desc())
                  .limit(limit)
              )
              .all()
          )
          return [VideoId(int(row[0])) for row in rows]


  # ---------------------------------------------------------------------------
  # Row <-> entity translation
  # ---------------------------------------------------------------------------


  def _row_to_hashtag(row: Any) -> Hashtag:
      data = cast("dict[str, Any]", dict(row))
      return Hashtag(
          id=int(data["id"]) if data.get("id") is not None else None,
          video_id=VideoId(int(data["video_id"])),
          tag=str(data["tag"]),
          created_at=_ensure_utc(data.get("created_at")),
      )


  def _ensure_utc(value: datetime | None) -> datetime | None:
      if value is None:
          return None
      if value.tzinfo is None:
          return value.replace(tzinfo=UTC)
      return value.astimezone(UTC)
  ```

  **Étape B — Créer `src/vidscope/adapters/sqlite/mention_repository.py`** (miroir symétrique, avec `handle` + `platform` optionnelle) :

  ```python
  """SQLite implementation of :class:`MentionRepository`.

  Uses SQLAlchemy Core exclusively. Mentions are stored in a side table
  keyed by ``(video_id, handle)`` with an optional ``platform`` column
  (per M007 D-03). No ``creator_id`` FK — mention↔creator linkage is
  deferred to M011.
  """

  from __future__ import annotations

  from datetime import UTC, datetime
  from typing import Any, cast

  from sqlalchemy import delete, select
  from sqlalchemy.engine import Connection

  from vidscope.adapters.sqlite.schema import mentions as mentions_table
  from vidscope.domain import Mention, Platform, VideoId
  from vidscope.domain.errors import StorageError

  __all__ = ["MentionRepositorySQLite"]


  def _canonicalise_handle(handle: str) -> str:
      """Return the canonical form of ``handle``: lowercase + strip '@'."""
      return handle.lower().lstrip("@").strip()


  class MentionRepositorySQLite:
      """Repository for :class:`Mention` backed by SQLite."""

      def __init__(self, connection: Connection) -> None:
          self._conn = connection

      def replace_for_video(
          self, video_id: VideoId, mentions: list[Mention]
      ) -> None:
          """DELETE existing rows for ``video_id`` then INSERT every mention.

          Canonicalises each handle and deduplicates by ``(handle, platform)``
          within the call.
          """
          try:
              self._conn.execute(
                  delete(mentions_table).where(
                      mentions_table.c.video_id == int(video_id)
                  )
              )
              seen: set[tuple[str, str | None]] = set()
              payloads: list[dict[str, Any]] = []
              now = datetime.now(UTC)
              for m in mentions:
                  canon = _canonicalise_handle(m.handle)
                  if not canon:
                      continue
                  plat_value = m.platform.value if m.platform is not None else None
                  key = (canon, plat_value)
                  if key in seen:
                      continue
                  seen.add(key)
                  payloads.append(
                      {
                          "video_id": int(video_id),
                          "handle": canon,
                          "platform": plat_value,
                          "created_at": now,
                      }
                  )
              if payloads:
                  self._conn.execute(
                      mentions_table.insert().values(payloads)
                  )
          except Exception as exc:
              raise StorageError(
                  f"replace_for_video failed for mentions of video "
                  f"{int(video_id)}: {exc}",
                  cause=exc,
              ) from exc

      def list_for_video(self, video_id: VideoId) -> list[Mention]:
          rows = (
              self._conn.execute(
                  select(mentions_table)
                  .where(mentions_table.c.video_id == int(video_id))
                  .order_by(mentions_table.c.id.asc())
              )
              .mappings()
              .all()
          )
          return [_row_to_mention(row) for row in rows]

      def find_video_ids_by_handle(
          self, handle: str, *, limit: int = 50
      ) -> list[VideoId]:
          canon = _canonicalise_handle(handle)
          if not canon:
              return []
          rows = (
              self._conn.execute(
                  select(mentions_table.c.video_id)
                  .where(mentions_table.c.handle == canon)
                  .order_by(mentions_table.c.id.desc())
                  .limit(limit)
              )
              .all()
          )
          return [VideoId(int(row[0])) for row in rows]


  def _row_to_mention(row: Any) -> Mention:
      data = cast("dict[str, Any]", dict(row))
      plat_raw = data.get("platform")
      platform = Platform(plat_raw) if plat_raw else None
      return Mention(
          id=int(data["id"]) if data.get("id") is not None else None,
          video_id=VideoId(int(data["video_id"])),
          handle=str(data["handle"]),
          platform=platform,
          created_at=_ensure_utc(data.get("created_at")),
      )


  def _ensure_utc(value: datetime | None) -> datetime | None:
      if value is None:
          return None
      if value.tzinfo is None:
          return value.replace(tzinfo=UTC)
      return value.astimezone(UTC)
  ```

  **Étape C — Étendre `src/vidscope/adapters/sqlite/video_repository.py`**. Ajouter les 3 colonnes dans `_video_to_row` (lignes 173-188) et `_row_to_video` (lignes 191-211) :

  Remplacer `_video_to_row` :

  ```python
  def _video_to_row(video: Video) -> dict[str, Any]:
      """Translate a domain :class:`Video` to a dict suitable for the
      ``videos`` table. ``id`` is omitted on insert; ``created_at`` is set
      to now() when absent."""
      return {
          "platform": video.platform.value,
          "platform_id": str(video.platform_id),
          "url": video.url,
          "author": video.author,
          "title": video.title,
          "duration": video.duration,
          "upload_date": video.upload_date,
          "view_count": video.view_count,
          "media_key": video.media_key,
          "created_at": video.created_at or datetime.now(UTC),
          "description": video.description,
          "music_track": video.music_track,
          "music_artist": video.music_artist,
      }
  ```

  Remplacer `_row_to_video` :

  ```python
  def _row_to_video(row: Any) -> Video:
      """Translate a SQLAlchemy row mapping to a domain :class:`Video`."""
      data = cast("dict[str, Any]", dict(row))
      return Video(
          id=VideoId(int(data["id"])),
          platform=Platform(data["platform"]),
          platform_id=PlatformId(str(data["platform_id"])),
          url=str(data["url"]),
          author=data.get("author"),
          title=data.get("title"),
          duration=data.get("duration"),
          upload_date=data.get("upload_date"),
          view_count=data.get("view_count"),
          media_key=data.get("media_key"),
          created_at=_ensure_utc(data.get("created_at")),
          creator_id=(
              CreatorId(int(data["creator_id"]))
              if data.get("creator_id") is not None
              else None
          ),
          description=data.get("description"),
          music_track=data.get("music_track"),
          music_artist=data.get("music_artist"),
      )
  ```

  **Étape D — Étendre `src/vidscope/adapters/sqlite/unit_of_work.py`**. Mettre à jour les imports + les annotations de slots (lignes 77-85) + les instanciations dans `__enter__` (lignes 93-101) :

  Imports à ajouter (après la ligne pour `CreatorRepositorySQLite`) :

  ```python
  from vidscope.adapters.sqlite.hashtag_repository import (
      HashtagRepositorySQLite,
  )
  from vidscope.adapters.sqlite.mention_repository import (
      MentionRepositorySQLite,
  )
  ```

  Et dans les ports :

  ```python
  from vidscope.ports import (
      AnalysisRepository,
      CreatorRepository,
      FrameRepository,
      HashtagRepository,
      MentionRepository,
      PipelineRunRepository,
      SearchIndex,
      TranscriptRepository,
      VideoRepository,
      WatchAccountRepository,
      WatchRefreshRepository,
  )
  ```

  Ajouter les 2 nouveaux slots (ligne 77-85) :

  ```python
          self.videos: VideoRepository
          self.creators: CreatorRepository
          self.transcripts: TranscriptRepository
          self.frames: FrameRepository
          self.analyses: AnalysisRepository
          self.hashtags: HashtagRepository
          self.mentions: MentionRepository
          self.pipeline_runs: PipelineRunRepository
          self.search_index: SearchIndex
          self.watch_accounts: WatchAccountRepository
          self.watch_refreshes: WatchRefreshRepository
  ```

  Instancier dans `__enter__` (après `self.analyses = AnalysisRepositorySQLite(...)`) :

  ```python
          self.hashtags = HashtagRepositorySQLite(self._connection)
          self.mentions = MentionRepositorySQLite(self._connection)
  ```

  **Étape E — Créer les tests (TDD).** Fichiers :

  - `tests/unit/adapters/sqlite/test_hashtag_repository.py` : 8 tests minimum couvrant replace_for_video (dedup + canonicalisation + idempotence), list_for_video (ordre + empty), find_video_ids_by_tag (canonicalisation input + limit), cascade delete depuis videos.
  - `tests/unit/adapters/sqlite/test_mention_repository.py` : 8 tests symétriques, plus tests sur `platform` optionnelle (None + Platform.TIKTOK), dedup sur `(handle, platform)`.
  - `tests/unit/adapters/sqlite/test_video_repository.py` : étendre avec 2 tests (round-trip avec les 3 nouveaux champs M007, backward compat sans les champs).
  - `tests/unit/adapters/sqlite/test_schema.py` : étendre avec test que `init_db` est idempotent (appelable 2x) et que les tables `hashtags`/`mentions` existent.

  Pour chaque test, utiliser un engine in-memory `create_engine("sqlite:///:memory:")` + `init_db(engine)` + créer un `Video` parent via `VideoRepositorySQLite.add`, puis exercer le nouveau repo sur la même `Connection` (patron exact des tests M006).
  </action>

  <acceptance_criteria>
    - Nouveau fichier `src/vidscope/adapters/sqlite/hashtag_repository.py` existe : `test -f src/vidscope/adapters/sqlite/hashtag_repository.py`
    - Nouveau fichier `src/vidscope/adapters/sqlite/mention_repository.py` existe : `test -f src/vidscope/adapters/sqlite/mention_repository.py`
    - `grep -q "class HashtagRepositorySQLite:" src/vidscope/adapters/sqlite/hashtag_repository.py` exit 0
    - `grep -q "class MentionRepositorySQLite:" src/vidscope/adapters/sqlite/mention_repository.py` exit 0
    - `grep -q "def _canonicalise_tag" src/vidscope/adapters/sqlite/hashtag_repository.py` exit 0
    - `grep -q "def _canonicalise_handle" src/vidscope/adapters/sqlite/mention_repository.py` exit 0
    - `grep -q '"description": video.description' src/vidscope/adapters/sqlite/video_repository.py` exit 0
    - `grep -q '"music_track": video.music_track' src/vidscope/adapters/sqlite/video_repository.py` exit 0
    - `grep -q "description=data.get" src/vidscope/adapters/sqlite/video_repository.py` exit 0
    - `grep -q "self.hashtags = HashtagRepositorySQLite" src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `grep -q "self.mentions = MentionRepositorySQLite" src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `test -f tests/unit/adapters/sqlite/test_hashtag_repository.py`
    - `test -f tests/unit/adapters/sqlite/test_mention_repository.py`
    - `grep -c "def test_" tests/unit/adapters/sqlite/test_hashtag_repository.py` retourne un nombre ≥ 8
    - `grep -c "def test_" tests/unit/adapters/sqlite/test_mention_repository.py` retourne un nombre ≥ 8
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_hashtag_repository.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_mention_repository.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q` exit 0
    - `python -m uv run pytest -q` exit 0 (suite complète — aucune régression)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (9 contrats verts, `sqlite-never-imports-fs` + `ports-are-pure` compris)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests par repo
python -m uv run pytest tests/unit/adapters/sqlite/test_hashtag_repository.py -x -q
python -m uv run pytest tests/unit/adapters/sqlite/test_mention_repository.py -x -q
python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q
python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q

# Smoke test schema : init_db 2x idempotent
python -m uv run python -c "
from sqlalchemy import create_engine, text
from vidscope.adapters.sqlite.schema import init_db
e = create_engine('sqlite:///:memory:')
init_db(e); init_db(e)
with e.connect() as c:
    tables = [r[0] for r in c.execute(text('SELECT name FROM sqlite_master WHERE type=\"table\"'))]
assert 'hashtags' in tables and 'mentions' in tables, tables
print('OK')
"

# Smoke test UoW expose nouveaux repos
python -m uv run python -c "
from sqlalchemy import create_engine
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
e = create_engine('sqlite:///:memory:'); init_db(e)
with SqliteUnitOfWork(e) as uow:
    assert hasattr(uow, 'hashtags') and hasattr(uow, 'mentions')
print('OK')
"

# Suite complète + quality gates
python -m uv run pytest -q
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

## Must-Haves

- Table `hashtags` existe en SQLite avec colonnes `id`, `video_id` (FK CASCADE), `tag`, `created_at` + 2 indices.
- Table `mentions` existe en SQLite avec colonnes `id`, `video_id` (FK CASCADE), `handle`, `platform` (nullable), `created_at` + 2 indices.
- Table `videos` a les colonnes `description`, `music_track`, `music_artist` après `init_db` (fresh ET upgrade via `_ensure_videos_metadata_columns`).
- `HashtagRepository` Protocol dans `vidscope.ports` avec `replace_for_video`, `list_for_video`, `find_video_ids_by_tag`.
- `MentionRepository` Protocol dans `vidscope.ports` avec `replace_for_video`, `list_for_video`, `find_video_ids_by_handle`.
- `HashtagRepositorySQLite` canonicalise (lowercase + lstrip '#') à l'écriture ET à la lecture par tag.
- `MentionRepositorySQLite` canonicalise (lowercase + lstrip '@') à l'écriture ET à la lecture par handle.
- `VideoRepositorySQLite` round-trip preserve les 3 nouveaux champs M007.
- `SqliteUnitOfWork` expose `uow.hashtags` et `uow.mentions` comme attributs utilisables.
- ≥ 8 tests par nouveau repo (seuil RESEARCH.md).
- Les 9 contrats `.importlinter` restent verts.

## Threat Model

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S01P02-01 | **Tampering (T)** — SQL injection via `tag` / `handle` | `HashtagRepositorySQLite.replace_for_video`, `MentionRepositorySQLite.replace_for_video` | LOW | mitigate | SQLAlchemy Core parametrised bindings (`.values(...)` + `.where(col == value)`) — raw SQL n'est jamais concaténé avec user input. Test de régression : un tag avec `"'; DROP TABLE videos; --"` est stocké verbatim et n'exécute rien. |
| T-S01P02-02 | **Information Disclosure (I)** | `Video.description` column (caption verbatim) | LOW | accept | Le champ stocke la description publique de la plateforme telle quelle. Aucune PII au-delà de ce que TikTok/YouTube/Instagram exposent publiquement. Stockage local single-user (R032). |
| T-S01P02-03 | **Tampering (T)** — downgrade/rollback de migration | `_ensure_videos_metadata_columns` | LOW | accept | SQLite `ALTER TABLE` ne supporte pas `DROP COLUMN` avant 3.35 — le rollback nécessite une table de remplacement. D-02 (DB migration reversibility) n'exige pas d'inverse ici car les colonnes sont nullable et additives (les anciens lecteurs les ignorent). Documenté dans la docstring du helper. |
| T-S01P02-04 | **Denial of Service (D)** — explosion de hashtags/mentions par vidéo | `replace_for_video` | LOW | mitigate | Idempotence par DELETE-then-INSERT + dédup in-memory avant insertion. Si un video reçoit 10 000 hashtags, ils seront tous insérés mais bornés par la limite yt-dlp (`info["tags"]` typiquement < 30) et par la limite I/O SQLite (~ microseconds per row). Si la source explose au-delà, caller peut tronquer en amont (non requis en M007). |
| T-S01P02-05 | **Repudiation (R)** | timestamps `created_at` | LOW | accept | `datetime.now(UTC)` stocké côté serveur. Pas d'authentification multi-utilisateur (R032) donc pas de besoin d'audit log. |
