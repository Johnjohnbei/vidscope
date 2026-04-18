---
plan_id: S01-P03
phase: M006/S01
wave: 3
depends_on: [S01-P01, S01-P02]
requirements: [R040, R042]
files_modified:
  - src/vidscope/adapters/sqlite/creator_repository.py
  - src/vidscope/adapters/sqlite/__init__.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/ports/repositories.py
  - tests/unit/adapters/sqlite/test_creator_repository.py
  - tests/unit/adapters/sqlite/test_unit_of_work.py
  - tests/unit/adapters/sqlite/test_video_repository.py
autonomous: true
---

## Objective

Livrer la couche concrète SQLite pour `CreatorRepository` et câbler le write-through cache sur `videos.author` (D-03). Trois mouvements synchrones :

1. **`SqlCreatorRepository`** — implémentation complète du Protocol P02 (T05), miroir ligne-pour-ligne de `VideoRepositorySQLite` (patron upsert `sqlite_insert().on_conflict_do_update()` sur les colonnes `(platform, platform_user_id)`), translators `_creator_to_row` / `_row_to_creator`, helpers UTC `_ensure_utc_for_read/write`, wrapping `StorageError(msg, cause=exc)`.
2. **UoW wiring** — `SqliteUnitOfWork` expose `self.creators: CreatorRepository`, construit dans `__enter__` sur la connexion partagée (une seule transaction couvre creator + video writes, conformément à la garantie de S02 pour `IngestStage`).
3. **Write-through cache (D-03)** — `VideoRepository.upsert_by_platform_id` reçoit un kwarg optionnel `creator: Creator | None = None`. Quand `creator is not None`, la payload écrite inclut `author = creator.display_name` ET `creator_id = int(creator.id)` dans le MÊME INSERT/UPDATE (atomique). Quand `creator is None`, le comportement existant est strictement préservé (les appelants M001–M005 non migrés continuent de fonctionner). La signature du Protocol `VideoRepository.upsert_by_platform_id` est mise à jour pour refléter le kwarg (additive, backward-compat).

Test de régression obligatoire (CONTEXT.md §specifics) : upsert creator avec `display_name="A"`, upsert video avec `creator` → `videos.author == "A"`. Re-upsert creator avec `display_name="B"`, re-upsert video → `videos.author == "B"`. Vérifie que le cache ne peut pas diverger.

**Container reste INCHANGÉ** (conformément à S01-RESEARCH.md §"Container wiring" Open Q4 : les 7 repos existants ne sont pas des champs de `Container` mais per-UoW ; `creator_repository` suit la même convention).

## Tasks

<task id="T08-sql-creator-repository">
  <name>Implémenter SqlCreatorRepository (miroir de VideoRepositorySQLite) et re-exporter</name>

  <read_first>
    - `src/vidscope/adapters/sqlite/video_repository.py` — TEMPLATE EXACT à suivre : constructor prend `Connection` (ligne 27), `upsert_by_platform_id` utilise `sqlite_insert().on_conflict_do_update()` (lignes 53-85), translators `_video_to_row`/`_row_to_video` (lignes 136-169), wrapping `StorageError(msg, cause=exc)` sur chaque bloc `try/except`. Tout ceci doit être mirroré.
    - `src/vidscope/adapters/sqlite/watch_account_repository.py` — SECOND TEMPLATE à suivre : helpers `_ensure_utc_for_write`/`_ensure_utc_for_read` (lignes 129-140) à COPIER verbatim pour `first_seen_at`, `last_seen_at`, `created_at`.
    - `src/vidscope/adapters/sqlite/schema.py` — après P02, la Table `creators` est importable comme `from vidscope.adapters.sqlite.schema import creators as creators_table`.
    - `src/vidscope/ports/repositories.py` — signature du `CreatorRepository` Protocol (après P02) — ordre et noms exacts des méthodes.
    - `src/vidscope/domain/__init__.py` — `Creator`, `CreatorId`, `PlatformUserId`, `Platform` sont re-exportés (après P01).
    - `src/vidscope/adapters/sqlite/__init__.py` — patron de re-export à étendre.
    - `.importlinter` — contrat `sqlite-never-imports-fs` et `domain-is-pure` / `ports-are-pure` (nouveau fichier importe uniquement `sqlalchemy` + `vidscope.domain` + `vidscope.domain.errors`).
  </read_first>

  <action>
  Créer `src/vidscope/adapters/sqlite/creator_repository.py` avec ce contenu (miroir strict du patron `VideoRepositorySQLite` + translators UTC de `WatchAccountRepositorySQLite`) :

  ```python
  """SQLite implementation of :class:`CreatorRepository`.

  Uses SQLAlchemy Core exclusively. Every method takes a
  :class:`sqlalchemy.engine.Connection` (bound to an open transaction by
  the unit of work) so creator writes can be grouped atomically with
  video writes — this is the structural contract that makes the
  write-through cache on ``videos.author`` (D-03) safe.
  """

  from __future__ import annotations

  from datetime import UTC, datetime
  from typing import Any, cast

  from sqlalchemy import func, select
  from sqlalchemy.dialects.sqlite import insert as sqlite_insert
  from sqlalchemy.engine import Connection

  from vidscope.adapters.sqlite.schema import creators as creators_table
  from vidscope.domain import Creator, CreatorId, Platform, PlatformUserId
  from vidscope.domain.errors import StorageError

  __all__ = ["CreatorRepositorySQLite"]


  class CreatorRepositorySQLite:
      """Repository for :class:`Creator` backed by SQLite."""

      def __init__(self, connection: Connection) -> None:
          self._conn = connection

      # ------------------------------------------------------------------
      # Writes
      # ------------------------------------------------------------------

      def upsert(self, creator: Creator) -> Creator:
          """Insert or update the row matching ``(platform, platform_user_id)``.

          Uses SQLite's ``INSERT ... ON CONFLICT DO UPDATE`` with the
          compound index elements ``["platform", "platform_user_id"]``
          (D-01 canonical UNIQUE). ``created_at`` and ``first_seen_at``
          are preserved on update (archaeology); every other field is
          overwritten by the incoming row.
          """
          payload = _creator_to_row(creator)
          stmt = sqlite_insert(creators_table).values(**payload)
          # On conflict, update every field EXCEPT the ones that must
          # survive as historical anchors.
          preserved = {"created_at", "first_seen_at"}
          update_map = {
              key: stmt.excluded[key]
              for key in payload
              if key not in preserved
          }
          stmt = stmt.on_conflict_do_update(
              index_elements=["platform", "platform_user_id"],
              set_=update_map,
          )
          try:
              self._conn.execute(stmt)
          except Exception as exc:
              raise StorageError(
                  f"upsert failed for creator "
                  f"{creator.platform.value}/{creator.platform_user_id}: {exc}",
                  cause=exc,
              ) from exc

          stored = self.find_by_platform_user_id(
              creator.platform, creator.platform_user_id
          )
          if stored is None:
              raise StorageError(
                  f"upsert succeeded but row missing for "
                  f"{creator.platform.value}/{creator.platform_user_id}"
              )
          return stored

      # ------------------------------------------------------------------
      # Reads
      # ------------------------------------------------------------------

      def get(self, creator_id: CreatorId) -> Creator | None:
          row = (
              self._conn.execute(
                  select(creators_table).where(
                      creators_table.c.id == int(creator_id)
                  )
              )
              .mappings()
              .first()
          )
          return _row_to_creator(row) if row else None

      def find_by_platform_user_id(
          self, platform: Platform, platform_user_id: PlatformUserId
      ) -> Creator | None:
          row = (
              self._conn.execute(
                  select(creators_table).where(
                      creators_table.c.platform == platform.value,
                      creators_table.c.platform_user_id == str(platform_user_id),
                  )
              )
              .mappings()
              .first()
          )
          return _row_to_creator(row) if row else None

      def find_by_handle(
          self, platform: Platform, handle: str
      ) -> Creator | None:
          # Most recently seen first: a renamed handle may collide with
          # an old row; newest wins for display.
          row = (
              self._conn.execute(
                  select(creators_table)
                  .where(
                      creators_table.c.platform == platform.value,
                      creators_table.c.handle == handle,
                  )
                  .order_by(creators_table.c.last_seen_at.desc().nulls_last())
                  .limit(1)
              )
              .mappings()
              .first()
          )
          return _row_to_creator(row) if row else None

      def list_by_platform(
          self, platform: Platform, *, limit: int = 50
      ) -> list[Creator]:
          rows = (
              self._conn.execute(
                  select(creators_table)
                  .where(creators_table.c.platform == platform.value)
                  .order_by(creators_table.c.last_seen_at.desc().nulls_last())
                  .limit(limit)
              )
              .mappings()
              .all()
          )
          return [_row_to_creator(row) for row in rows]

      def list_by_min_followers(
          self, min_count: int, *, limit: int = 50
      ) -> list[Creator]:
          rows = (
              self._conn.execute(
                  select(creators_table)
                  .where(creators_table.c.follower_count >= min_count)
                  .order_by(creators_table.c.follower_count.desc())
                  .limit(limit)
              )
              .mappings()
              .all()
          )
          return [_row_to_creator(row) for row in rows]

      def count(self) -> int:
          total = self._conn.execute(
              select(func.count()).select_from(creators_table)
          ).scalar()
          return int(total or 0)


  # ---------------------------------------------------------------------------
  # Row <-> entity translation
  # ---------------------------------------------------------------------------


  def _creator_to_row(creator: Creator) -> dict[str, Any]:
      """Translate a domain :class:`Creator` to a dict suitable for the
      ``creators`` table. ``id`` is omitted on insert.
      """
      now = datetime.now(UTC)
      return {
          "platform": creator.platform.value,
          "platform_user_id": str(creator.platform_user_id),
          "handle": creator.handle,
          "display_name": creator.display_name,
          "profile_url": creator.profile_url,
          "avatar_url": creator.avatar_url,
          "follower_count": creator.follower_count,
          "is_verified": creator.is_verified,
          "is_orphan": creator.is_orphan,
          "first_seen_at": (
              _ensure_utc_for_write(creator.first_seen_at)
              if creator.first_seen_at is not None
              else now
          ),
          "last_seen_at": (
              _ensure_utc_for_write(creator.last_seen_at)
              if creator.last_seen_at is not None
              else now
          ),
          "created_at": (
              _ensure_utc_for_write(creator.created_at)
              if creator.created_at is not None
              else now
          ),
      }


  def _row_to_creator(row: Any) -> Creator:
      data = cast("dict[str, Any]", dict(row))
      return Creator(
          id=CreatorId(int(data["id"])),
          platform=Platform(data["platform"]),
          platform_user_id=PlatformUserId(str(data["platform_user_id"])),
          handle=data.get("handle"),
          display_name=data.get("display_name"),
          profile_url=data.get("profile_url"),
          avatar_url=data.get("avatar_url"),
          follower_count=data.get("follower_count"),
          is_verified=data.get("is_verified"),
          is_orphan=bool(data.get("is_orphan") or False),
          first_seen_at=_ensure_utc_for_read(data.get("first_seen_at")),
          last_seen_at=_ensure_utc_for_read(data.get("last_seen_at")),
          created_at=_ensure_utc_for_read(data.get("created_at")),
      )


  def _ensure_utc_for_write(value: datetime) -> datetime:
      if value.tzinfo is None:
          return value.replace(tzinfo=UTC)
      return value.astimezone(UTC)


  def _ensure_utc_for_read(value: datetime | None) -> datetime | None:
      if value is None:
          return None
      if value.tzinfo is None:
          return value.replace(tzinfo=UTC)
      return value.astimezone(UTC)
  ```

  Mettre à jour `src/vidscope/adapters/sqlite/__init__.py` pour re-exporter `CreatorRepositorySQLite` :
  - Ajouter `from vidscope.adapters.sqlite.creator_repository import CreatorRepositorySQLite`
  - Ajouter `"CreatorRepositorySQLite"` dans `__all__` en ordre alphabétique
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/adapters/sqlite/creator_repository.py`
    - `grep -q "class CreatorRepositorySQLite:" src/vidscope/adapters/sqlite/creator_repository.py` exit 0
    - `grep -q "def upsert(self, creator: Creator) -> Creator:" src/vidscope/adapters/sqlite/creator_repository.py` exit 0
    - `grep -q 'index_elements=\["platform", "platform_user_id"\]' src/vidscope/adapters/sqlite/creator_repository.py` exit 0
    - `grep -q 'preserved = {"created_at", "first_seen_at"}' src/vidscope/adapters/sqlite/creator_repository.py` exit 0
    - `grep -q "CreatorRepositorySQLite" src/vidscope/adapters/sqlite/__init__.py` exit 0
    - `python -m uv run python -c "from vidscope.adapters.sqlite import CreatorRepositorySQLite; print(CreatorRepositorySQLite.__name__)"` sort `CreatorRepositorySQLite`
    - `python -m uv run python -c "from vidscope.ports import CreatorRepository; from vidscope.adapters.sqlite import CreatorRepositorySQLite; assert hasattr(CreatorRepositorySQLite, 'upsert'); assert hasattr(CreatorRepositorySQLite, 'find_by_platform_user_id'); print('OK')"` sort `OK`
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `sqlite-never-imports-fs` vert ; seuls `sqlalchemy` + `vidscope.domain` + `vidscope.domain.errors` importés)
  </acceptance_criteria>
</task>

<task id="T09-uow-creators-wiring">
  <name>Exposer uow.creators dans SqliteUnitOfWork (slot + construction __enter__)</name>

  <read_first>
    - `src/vidscope/adapters/sqlite/unit_of_work.py` — ligne 73-80 (slots de repos typés par Protocol) + ligne 85-95 (construction dans `__enter__`). Patron exact à suivre.
    - `src/vidscope/ports/__init__.py` — `CreatorRepository` est re-exporté après P02.
    - `src/vidscope/adapters/sqlite/creator_repository.py` — `CreatorRepositorySQLite` créé par T08.
  </read_first>

  <action>
  Modifier `src/vidscope/adapters/sqlite/unit_of_work.py` en TROIS endroits :

  **1. Import de l'adaptateur** — ajouter en ordre alphabétique dans le bloc d'imports `vidscope.adapters.sqlite.*` (lignes 24-39) :

  ```python
  from vidscope.adapters.sqlite.creator_repository import (
      CreatorRepositorySQLite,
  )
  ```

  (Insérer juste après l'import de `analysis_repository`.)

  **2. Import du Protocol** — ajouter `CreatorRepository` dans l'import groupé depuis `vidscope.ports` (lignes 41-50) en ordre alphabétique :

  ```python
  from vidscope.ports import (
      AnalysisRepository,
      CreatorRepository,
      FrameRepository,
      PipelineRunRepository,
      SearchIndex,
      TranscriptRepository,
      VideoRepository,
      WatchAccountRepository,
      WatchRefreshRepository,
  )
  ```

  **3. Slot + construction** — ajouter `self.creators: CreatorRepository` dans la déclaration des slots (après `self.videos`, ligne ~73-80) :

  ```python
  self.videos: VideoRepository
  self.creators: CreatorRepository
  self.transcripts: TranscriptRepository
  # ... reste inchangé
  ```

  Et construire l'instance dans `__enter__` (après la ligne qui construit `self.videos`, ligne ~88) :

  ```python
  self.videos = VideoRepositorySQLite(self._connection)
  self.creators = CreatorRepositorySQLite(self._connection)
  self.transcripts = TranscriptRepositorySQLite(self._connection)
  # ... reste inchangé
  ```

  Ne pas modifier la signature de `__init__` ni `__exit__`. `Container` reste intouché (S01-RESEARCH Open Q4).
  </action>

  <acceptance_criteria>
    - `grep -q "from vidscope.adapters.sqlite.creator_repository import" src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `grep -q "CreatorRepository," src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `grep -q "self.creators: CreatorRepository" src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `grep -q "self.creators = CreatorRepositorySQLite" src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `python -m uv run python -c "import tempfile; from pathlib import Path; from vidscope.adapters.sqlite.schema import init_db; from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork; from vidscope.infrastructure.sqlite_engine import build_engine; from vidscope.ports import CreatorRepository; d=tempfile.mkdtemp(); eng=build_engine(Path(d)/'t.db'); init_db(eng); uow=SqliteUnitOfWork(eng)$(printf '\nwith uow:\n    assert isinstance(uow.creators, CreatorRepository); print(\"OK\")')"` — plus simplement vérifier via pytest (voir T10)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0
  </acceptance_criteria>
</task>

<task id="T10-video-repository-write-through">
  <name>Write-through D-03 : VideoRepository.upsert_by_platform_id accepte creator kwarg (Protocol + adapter)</name>

  <read_first>
    - `src/vidscope/ports/repositories.py` lignes 76-80 — signature actuelle `upsert_by_platform_id(self, video: Video) -> Video` du Protocol `VideoRepository`. À étendre additivement avec kwarg optionnel.
    - `src/vidscope/adapters/sqlite/video_repository.py` lignes 53-85 — implémentation actuelle `upsert_by_platform_id`, translator `_video_to_row` ligne 136-151. À étendre.
    - `.gsd/milestones/M006/slices/S01/S01-CONTEXT.md` §D-03 — règle : write-through au niveau repository, application code ne touche JAMAIS `videos.author` directement ; `creator.display_name` copié dans `videos.author` dans la MÊME transaction.
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"Write-Through Cache Enforcement (D-03)" — Option A retenue : kwarg optionnel sur upsert, `creator=None` préserve le comportement M001–M005.
    - `src/vidscope/domain/__init__.py` — `Creator` est importable (après P01).
  </read_first>

  <action>
  Modifier DEUX fichiers :

  **1. `src/vidscope/ports/repositories.py`** — mettre à jour la signature du Protocol `VideoRepository.upsert_by_platform_id` (lignes 76-80) pour accepter le kwarg optionnel :

  ```python
  def upsert_by_platform_id(
      self, video: Video, creator: Creator | None = None
  ) -> Video:
      """Insert ``video`` or update the existing row matching
      ``(platform, platform_id)``. Returns the resulting entity with
      ``id`` populated. Idempotent.

      When ``creator`` is provided, the repository structurally enforces
      the write-through cache on ``videos.author`` (D-03): within the
      same SQL statement, ``video.author = creator.display_name`` and
      ``video.creator_id = int(creator.id)``. Application code MUST NOT
      write ``video.author`` directly — the repository is the single
      source of truth for the cache.

      When ``creator`` is None (the default), the existing behavior is
      preserved: ``video.author`` is taken from the ``video`` argument
      as-is, ``video.creator_id`` is left untouched. This keeps M001–M005
      callers working without modification until M006/S02 wires creators
      through the ingest stage.
      """
      ...
  ```

  **2. `src/vidscope/adapters/sqlite/video_repository.py`** — modifier `upsert_by_platform_id` (lignes 53-85) pour accepter et honorer le kwarg :

  ```python
  def upsert_by_platform_id(
      self, video: Video, creator: Creator | None = None
  ) -> Video:
      """Insert or update the row matching ``(platform, platform_id)``.

      See :class:`VideoRepository.upsert_by_platform_id` for the
      write-through cache contract on ``videos.author`` when ``creator``
      is provided (D-03).
      """
      payload = _video_to_row(video)

      # D-03 write-through: when a creator is passed, the repository
      # owns both `author` (denormalised cache) and `creator_id` (FK).
      # They ARE written in the same SQL statement → atomic.
      if creator is not None:
          if creator.display_name is not None:
              payload["author"] = creator.display_name
          if creator.id is not None:
              payload["creator_id"] = int(creator.id)

      stmt = sqlite_insert(videos_table).values(**payload)
      # On conflict, update every field except id and created_at.
      update_map = {
          key: stmt.excluded[key]
          for key in payload
          if key not in ("created_at",)
      }
      stmt = stmt.on_conflict_do_update(
          index_elements=["platform_id"],
          set_=update_map,
      )
      try:
          self._conn.execute(stmt)
      except Exception as exc:
          raise StorageError(
              f"upsert failed for video {video.platform_id}: {exc}",
              cause=exc,
          ) from exc

      stored = self.get_by_platform_id(video.platform, video.platform_id)
      if stored is None:
          raise StorageError(
              f"upsert succeeded but row missing for {video.platform_id}"
          )
      return stored
  ```

  Étendre `_video_to_row` (lignes 136-151) pour inclure `creator_id` dans la payload de base (toujours présent comme clé, mais valeur `video.creator_id` ne sera jamais lu depuis `Video` — le domain `Video` n'expose pas `creator_id`). Solution propre : laisser `_video_to_row` inchangé ; le kwarg `creator` ajoute `creator_id` à la payload uniquement quand pertinent. Ceci évite de muter le domain `Video` dans S01 (cela ferait partie de S02 quand l'ingest stage passera un creator).

  Mettre à jour l'import de `vidscope.domain` (ligne 18) pour inclure `Creator` :

  ```python
  from vidscope.domain import Creator, Platform, PlatformId, Video, VideoId
  ```

  **Note de sémantique** : si `creator.id is None` (creator non encore persisté), le kwarg `creator` est utilisé MAIS `creator_id` n'est pas écrit — seul `author` est mis à jour. Le test de régression D-03 couvrira ce cas (creator déjà upserté via `CreatorRepository`, donc `id` est peuplé).
  </action>

  <acceptance_criteria>
    - `grep -q "def upsert_by_platform_id" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "creator: Creator | None = None" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "creator: Creator | None = None" src/vidscope/adapters/sqlite/video_repository.py` exit 0
    - `grep -q "payload\[\"author\"\] = creator.display_name" src/vidscope/adapters/sqlite/video_repository.py` exit 0
    - `grep -q "payload\[\"creator_id\"\] = int(creator.id)" src/vidscope/adapters/sqlite/video_repository.py` exit 0
    - Les appelants existants (sans `creator=`) passent : `python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/pipeline tests/unit/application -x -q` exit 0 (les stages et use cases qui appellent `upsert_by_platform_id(video)` ne sont PAS cassés — kwarg optionnel)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0
  </acceptance_criteria>
</task>

<task id="T11-tests-creator-repo-uow-writethrough">
  <name>Tests adapter : SqlCreatorRepository CRUD + UoW shared-txn + write-through regression (D-03)</name>

  <read_first>
    - `tests/unit/adapters/sqlite/test_watch_account_repository.py` — patron EXACT à mirroir pour `test_creator_repository.py` (add, get, find_by_*, duplicate raises, same-handle-different-platforms, list ordering). Lire au moins lignes 1-100.
    - `tests/unit/adapters/sqlite/test_unit_of_work.py` — patron pour le test transactionnel partagé (rollback leaves neither row).
    - `tests/unit/adapters/sqlite/test_video_repository.py` lignes 1-80 — patron pour tests de repository à étendre avec `TestWriteThroughAuthor`.
    - `tests/unit/adapters/sqlite/conftest.py` — fixture `engine` réutilisable.
    - `src/vidscope/adapters/sqlite/creator_repository.py` — forme définitive après T08.
  </read_first>

  <action>
  Créer UN fichier neuf et étendre DEUX fichiers existants :

  **1. Créer `tests/unit/adapters/sqlite/test_creator_repository.py`** :

  ```python
  """Tests for CreatorRepositorySQLite (M006/S01)."""

  from __future__ import annotations

  from datetime import UTC, datetime

  import pytest
  from sqlalchemy import Engine

  from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
  from vidscope.domain import Creator, CreatorId, Platform, PlatformUserId
  from vidscope.domain.errors import StorageError

  UTC_NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)


  def _sample_creator(
      *,
      platform: Platform = Platform.YOUTUBE,
      platform_user_id: str = "UC_ABC",
      handle: str | None = "@creator",
      display_name: str | None = "The Creator",
      follower_count: int | None = 1_000,
      is_orphan: bool = False,
  ) -> Creator:
      return Creator(
          platform=platform,
          platform_user_id=PlatformUserId(platform_user_id),
          handle=handle,
          display_name=display_name,
          profile_url=f"https://youtube.com/{handle}" if handle else None,
          avatar_url="https://yt3.cdn/avatar.jpg",
          follower_count=follower_count,
          is_verified=True,
          is_orphan=is_orphan,
      )


  class TestCreatorRepositoryWrites:
      def test_upsert_insert_round_trip(self, engine: Engine) -> None:
          with SqliteUnitOfWork(engine) as uow:
              stored = uow.creators.upsert(_sample_creator())
              assert stored.id is not None
              assert stored.platform is Platform.YOUTUBE
              assert stored.display_name == "The Creator"
              assert stored.is_orphan is False
              assert stored.created_at is not None
              assert stored.first_seen_at is not None

          with SqliteUnitOfWork(engine) as uow:
              found = uow.creators.find_by_platform_user_id(
                  Platform.YOUTUBE, PlatformUserId("UC_ABC")
              )
              assert found is not None
              assert found.display_name == "The Creator"

      def test_upsert_is_idempotent_across_transactions(
          self, engine: Engine
      ) -> None:
          with SqliteUnitOfWork(engine) as uow:
              first = uow.creators.upsert(_sample_creator())

          with SqliteUnitOfWork(engine) as uow:
              second = uow.creators.upsert(_sample_creator(display_name="Renamed"))
              assert second.id == first.id  # same surrogate id
              assert second.display_name == "Renamed"

          with SqliteUnitOfWork(engine) as uow:
              assert uow.creators.count() == 1

      def test_same_platform_user_id_on_different_platforms_ok(
          self, engine: Engine
      ) -> None:
          with SqliteUnitOfWork(engine) as uow:
              a = uow.creators.upsert(
                  _sample_creator(platform=Platform.YOUTUBE, platform_user_id="shared")
              )
              b = uow.creators.upsert(
                  _sample_creator(platform=Platform.TIKTOK, platform_user_id="shared")
              )
              assert a.id != b.id
              assert uow.creators.count() == 2

      def test_upsert_preserves_created_at_on_update(
          self, engine: Engine
      ) -> None:
          with SqliteUnitOfWork(engine) as uow:
              initial = uow.creators.upsert(_sample_creator())
              original_created = initial.created_at

          with SqliteUnitOfWork(engine) as uow:
              updated = uow.creators.upsert(_sample_creator(display_name="New"))
              assert updated.created_at == original_created  # preserved

      def test_is_orphan_round_trips(self, engine: Engine) -> None:
          with SqliteUnitOfWork(engine) as uow:
              orphan = uow.creators.upsert(
                  _sample_creator(
                      platform=Platform.INSTAGRAM,
                      platform_user_id="orphan:legacy_author",
                      is_orphan=True,
                  )
              )
              assert orphan.is_orphan is True

          with SqliteUnitOfWork(engine) as uow:
              found = uow.creators.find_by_platform_user_id(
                  Platform.INSTAGRAM, PlatformUserId("orphan:legacy_author")
              )
              assert found is not None
              assert found.is_orphan is True


  class TestCreatorRepositoryReads:
      def test_get_missing_returns_none(self, engine: Engine) -> None:
          with SqliteUnitOfWork(engine) as uow:
              assert uow.creators.get(CreatorId(999)) is None

      def test_find_by_handle(self, engine: Engine) -> None:
          with SqliteUnitOfWork(engine) as uow:
              uow.creators.upsert(
                  _sample_creator(platform=Platform.TIKTOK, handle="@tiktoker")
              )
          with SqliteUnitOfWork(engine) as uow:
              found = uow.creators.find_by_handle(Platform.TIKTOK, "@tiktoker")
              assert found is not None
              assert found.handle == "@tiktoker"
              assert (
                  uow.creators.find_by_handle(Platform.YOUTUBE, "@tiktoker")
                  is None
              )

      def test_list_by_platform(self, engine: Engine) -> None:
          with SqliteUnitOfWork(engine) as uow:
              uow.creators.upsert(_sample_creator(platform_user_id="a"))
              uow.creators.upsert(_sample_creator(platform_user_id="b"))
              uow.creators.upsert(
                  _sample_creator(platform=Platform.TIKTOK, platform_user_id="c")
              )

          with SqliteUnitOfWork(engine) as uow:
              yts = uow.creators.list_by_platform(Platform.YOUTUBE)
              tiks = uow.creators.list_by_platform(Platform.TIKTOK)
              assert len(yts) == 2
              assert len(tiks) == 1

      def test_list_by_min_followers_excludes_nulls(
          self, engine: Engine
      ) -> None:
          with SqliteUnitOfWork(engine) as uow:
              uow.creators.upsert(
                  _sample_creator(platform_user_id="big", follower_count=100_000)
              )
              uow.creators.upsert(
                  _sample_creator(platform_user_id="small", follower_count=100)
              )
              uow.creators.upsert(
                  _sample_creator(platform_user_id="null", follower_count=None)
              )

          with SqliteUnitOfWork(engine) as uow:
              top = uow.creators.list_by_min_followers(1_000)
              ids = [c.platform_user_id for c in top]
              assert ids == [PlatformUserId("big")]
              # small (<1000) and null are excluded.

      def test_count(self, engine: Engine) -> None:
          with SqliteUnitOfWork(engine) as uow:
              assert uow.creators.count() == 0
              uow.creators.upsert(_sample_creator())
              assert uow.creators.count() == 1
  ```

  **2. Étendre `tests/unit/adapters/sqlite/test_unit_of_work.py`** — ajouter une nouvelle classe `TestCreatorInTransaction` :

  ```python
  class TestCreatorInTransaction:
      """UoW exposes creators and shares the transaction with videos.

      This is the structural contract that makes the D-03 write-through
      safe: both repos use the same Connection, so a creator upsert +
      video upsert commit or roll back together.
      """

      def test_uow_exposes_creator_repository(self, engine: Engine) -> None:
          from vidscope.ports import CreatorRepository

          with SqliteUnitOfWork(engine) as uow:
              assert isinstance(uow.creators, CreatorRepository)

      def test_creator_and_video_share_transaction_rollback(
          self, engine: Engine
      ) -> None:
          from vidscope.domain import Creator, PlatformUserId

          class BoomError(RuntimeError):
              pass

          with pytest.raises(BoomError), SqliteUnitOfWork(engine) as uow:
              uow.creators.upsert(
                  Creator(
                      platform=Platform.YOUTUBE,
                      platform_user_id=PlatformUserId("UC_ROLL"),
                      display_name="Rolled",
                  )
              )
              uow.videos.add(
                  Video(
                      platform=Platform.YOUTUBE,
                      platform_id=PlatformId("roll_v1"),
                      url="https://x/roll",
                  )
              )
              raise BoomError("abort after both writes")

          # Neither row persisted.
          with SqliteUnitOfWork(engine) as uow:
              assert uow.creators.count() == 0
              assert uow.videos.count() == 0

      def test_creator_and_video_share_transaction_commit(
          self, engine: Engine
      ) -> None:
          from vidscope.domain import Creator, PlatformUserId

          with SqliteUnitOfWork(engine) as uow:
              uow.creators.upsert(
                  Creator(
                      platform=Platform.YOUTUBE,
                      platform_user_id=PlatformUserId("UC_OK"),
                      display_name="Ok",
                  )
              )
              uow.videos.add(
                  Video(
                      platform=Platform.YOUTUBE,
                      platform_id=PlatformId("ok_v1"),
                      url="https://x/ok",
                  )
              )

          with SqliteUnitOfWork(engine) as uow:
              assert uow.creators.count() == 1
              assert uow.videos.count() == 1
  ```

  **3. Étendre `tests/unit/adapters/sqlite/test_video_repository.py`** — ajouter une nouvelle classe `TestWriteThroughAuthor` à la fin du fichier :

  ```python
  class TestWriteThroughAuthor:
      """D-03 write-through cache regression: videos.author tracks
      creators.display_name when upsert_by_platform_id(video, creator=...)
      is used. Application code must NEVER write videos.author directly.
      """

      def test_upsert_with_creator_copies_display_name_to_author(
          self, engine: Engine
      ) -> None:
          from vidscope.domain import Creator, PlatformUserId

          with SqliteUnitOfWork(engine) as uow:
              creator = uow.creators.upsert(
                  Creator(
                      platform=Platform.YOUTUBE,
                      platform_user_id=PlatformUserId("UC_WT"),
                      display_name="Display A",
                  )
              )
              video = uow.videos.upsert_by_platform_id(
                  _sample_video(
                      platform_id=PlatformId("wt_v1"),
                      author="stale-will-be-overwritten",
                  ),
                  creator=creator,
              )
              assert video.author == "Display A"
              assert video.id is not None

      def test_rename_creator_propagates_to_videos_author(
          self, engine: Engine
      ) -> None:
          """The regression guard mandated by CONTEXT.md §specifics."""
          from vidscope.domain import Creator, PlatformUserId

          with SqliteUnitOfWork(engine) as uow:
              creator_a = uow.creators.upsert(
                  Creator(
                      platform=Platform.YOUTUBE,
                      platform_user_id=PlatformUserId("UC_RN"),
                      display_name="A",
                  )
              )
              uow.videos.upsert_by_platform_id(
                  _sample_video(platform_id=PlatformId("rn_v1")),
                  creator=creator_a,
              )

          with SqliteUnitOfWork(engine) as uow:
              found = uow.videos.get_by_platform_id(
                  Platform.YOUTUBE, PlatformId("rn_v1")
              )
              assert found is not None
              assert found.author == "A"

              # Rename the creator
              creator_b = uow.creators.upsert(
                  Creator(
                      platform=Platform.YOUTUBE,
                      platform_user_id=PlatformUserId("UC_RN"),
                      display_name="B",
                  )
              )
              uow.videos.upsert_by_platform_id(
                  _sample_video(platform_id=PlatformId("rn_v1")),
                  creator=creator_b,
              )

          with SqliteUnitOfWork(engine) as uow:
              found = uow.videos.get_by_platform_id(
                  Platform.YOUTUBE, PlatformId("rn_v1")
              )
              assert found is not None
              assert found.author == "B"  # write-through propagated

      def test_upsert_without_creator_preserves_existing_author(
          self, engine: Engine
      ) -> None:
          """M001–M005 callers still work unchanged (kwarg defaults to
          None → author is taken from the video argument as-is)."""
          with SqliteUnitOfWork(engine) as uow:
              v = uow.videos.upsert_by_platform_id(
                  _sample_video(
                      platform_id=PlatformId("legacy_v1"),
                      author="Legacy Author",
                  ),
                  # no creator kwarg
              )
              assert v.author == "Legacy Author"
  ```
  </action>

  <acceptance_criteria>
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py::TestCreatorRepositoryWrites -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py::TestCreatorRepositoryReads -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_unit_of_work.py::TestCreatorInTransaction -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py::TestWriteThroughAuthor -x -q` exit 0
    - `grep -q "test_rename_creator_propagates_to_videos_author" tests/unit/adapters/sqlite/test_video_repository.py` exit 0
    - `grep -q "test_upsert_without_creator_preserves_existing_author" tests/unit/adapters/sqlite/test_video_repository.py` exit 0
    - `grep -q "test_creator_and_video_share_transaction_rollback" tests/unit/adapters/sqlite/test_unit_of_work.py` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite -q` exit 0 (toute la couche adapter SQLite verte)
    - `python -m uv run pytest -q` exit 0 (suite complète verte, aucune régression)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (9 contrats verts)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests par couche (spécifique → large)
python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py -x -q
python -m uv run pytest tests/unit/adapters/sqlite/test_unit_of_work.py::TestCreatorInTransaction -x -q
python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py::TestWriteThroughAuthor -x -q

# Couche adapter SQLite complète
python -m uv run pytest tests/unit/adapters/sqlite -q

# Aucune régression pipeline/application/cli (les appelants existants de upsert_by_platform_id sans creator= doivent rester verts)
python -m uv run pytest tests/unit/pipeline tests/unit/application tests/unit/cli -q

# Suite complète
python -m uv run pytest -q

# 4 quality gates
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

## Must-Haves

- `CreatorRepositorySQLite` existe dans `src/vidscope/adapters/sqlite/creator_repository.py` et implémente entièrement le Protocol `CreatorRepository` (7 méthodes : upsert, get, find_by_platform_user_id, find_by_handle, list_by_platform, list_by_min_followers, count)
- Upsert utilise `sqlite_insert().on_conflict_do_update(index_elements=["platform", "platform_user_id"])` — respecte D-01
- Upsert préserve `created_at` ET `first_seen_at` sur update (archaeology) ; actualise tout le reste
- Row↔entity translators (`_creator_to_row`, `_row_to_creator`) gèrent UTC round-trip pour les 3 timestamps
- Chaque opération SQL est enveloppée dans `try/except` avec `StorageError(msg, cause=exc) from exc`
- `CreatorRepositorySQLite` re-exporté par `vidscope.adapters.sqlite.__init__`
- `SqliteUnitOfWork` expose `self.creators: CreatorRepository` construit sur la connexion partagée — creator + video writes dans la même transaction (commit OU rollback atomique)
- `Container` reste INCHANGÉ (per-UoW wiring, pas de champ `creator_repository` sur Container — research Q4)
- `VideoRepository.upsert_by_platform_id` (Protocol + adaptateur) accepte `creator: Creator | None = None` ; quand fourni, écrit `author = creator.display_name` et `creator_id = int(creator.id)` dans la MÊME SQL (atomique)
- Les appelants M001–M005 (sans kwarg) continuent de fonctionner — backward-compat 100%
- Test de régression D-03 `test_rename_creator_propagates_to_videos_author` vert : rename `display_name` A→B + re-upsert video → `videos.author` passe de A à B
- Tests transactionnels UoW : rollback laisse NI creator NI video ; commit persiste les deux
- 9 contrats import-linter verts ; mypy strict vert ; ruff vert ; pytest complet vert
- P04 peut désormais appeler `uow.creators.upsert(...)` puis `uow.videos.upsert_by_platform_id(video, creator=...)` dans la même transaction

## Threat Model

Surface de menace concrète : ce plan introduit le premier write path SQL pour créateurs, donc l'ensemble des menaces de CONTEXT.md §specifics s'applique (sauf la partie backfill, qui est P04).

| # | STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-P03-01 | **Tampering (T)** — SQL injection via handle/display_name | `CreatorRepositorySQLite.upsert` | HIGH | mitigate | SQLAlchemy Core paramétrise TOUTES les valeurs via `.values(**payload)` et `stmt.excluded[...]` : aucune concaténation de chaîne. Les entrées utilisateur (`handle`, `display_name`, `profile_url`, `avatar_url`) passent directement en bind parameters. Pas de `text()` sur un chemin où une donnée utilisateur transite. Sanity : `grep -n "text(" src/vidscope/adapters/sqlite/creator_repository.py` doit retourner 0 ligne (le helper idempotent est en `schema.py`, pas ici). |
| T-P03-02 | **Tampering (T)** — Write-through divergence (D-03) | `VideoRepository.upsert_by_platform_id` | MEDIUM | mitigate | Le repository est la seule route qui écrit `videos.author` quand `creator` est passé. Test de régression `test_rename_creator_propagates_to_videos_author` + `test_upsert_with_creator_copies_display_name_to_author` verrouillent le comportement. Application code qui instancierait `Video(author="bad")` et l'upserterait sans creator verrait son author préservé — acceptable pour M001–M005 backward-compat ; S02 forcera le passage de creator via IngestStage. |
| T-P03-03 | **Repudiation (R)** — Perte d'archaeology | `upsert` preserve logic | LOW | mitigate | `created_at` ET `first_seen_at` explicitement exclus de `update_map`. Test `test_upsert_preserves_created_at_on_update` pin l'invariant. `last_seen_at` ET `display_name` SONT écrasés (sémantique : "dernière observation gagne"). |
| T-P03-04 | **Denial of Service (D)** — list_by_min_followers unbounded | reads | LOW | mitigate | Paramètre `limit: int = 50` obligatoire (même convention que `VideoRepository.list_recent`). L'appelant ne peut pas demander une liste non-bornée. |
| T-P03-05 | **Elevation of Privilege (E)** — slot remplacement sur `SqliteUnitOfWork` | UoW | NONE | accept | D032 (single-user local tool) : pas de surface multi-utilisateur. Le remplacement de `uow.creators` par une classe malicieuse nécessiterait déjà un exec local — au-delà du modèle de menace. |

**Note spéciale write-through** : une préoccupation pratique distincte du threat model classique — un appelant futur pourrait oublier de passer `creator=` et écraser `videos.author` avec une chaîne stale. Mitigation : (a) la régression test D-03 est la sanity ; (b) S02 forcera le passage systématique via un refactor de `IngestStage` — documenté dans la carry-over note P04. Zero blocker pour S01.
