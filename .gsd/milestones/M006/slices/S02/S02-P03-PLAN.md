---
plan_id: S02-P03
phase: M006/S02
plan: 03
type: execute
wave: 2
depends_on: [S02-P01]
files_modified:
  - src/vidscope/pipeline/stages/ingest.py
  - tests/unit/pipeline/stages/test_ingest.py
  - scripts/verify-m006-s02.sh
autonomous: true
requirements: [R040, R001]
must_haves:
  truths:
    - "IngestStage.execute() upserts the creator from outcome.creator_info before the video row"
    - "Creator upsert and video upsert share a single UoW transaction (D-04)"
    - "A video upsert failure rolls back the creator upsert (atomicity)"
    - "When outcome.creator_info is None, ingest succeeds with video.creator_id=NULL and logs a WARNING with the video URL (D-02)"
    - "Re-ingest on the same URL reuses the existing creator row (D-03 full upsert idempotent)"
    - "video.creator_id and video.author are set atomically via uow.videos.upsert_by_platform_id(video, creator=creator) — D-03 write-through cache from S01-P03 is triggered"
    - "Pre-existing IngestStage tests continue to pass (backward compat via D-02 None path)"
  artifacts:
    - path: "src/vidscope/pipeline/stages/ingest.py"
      provides: "IngestStage.execute wires creator upsert before video upsert"
      contains: "uow.creators.upsert"
    - path: "tests/unit/pipeline/stages/test_ingest.py"
      provides: "TestCreatorWiring class — happy path, D-02 none, D-03 full upsert, D-04 rollback"
      contains: "class TestCreatorWiring"
    - path: "scripts/verify-m006-s02.sh"
      provides: "End-to-end harness for M006/S02: quality gates + S02 targeted tests"
      min_lines: 80
  key_links:
    - from: "src/vidscope/pipeline/stages/ingest.py"
      to: "uow.creators.upsert"
      via: "CreatorInfo → Creator construction + upsert call"
      pattern: "uow\\.creators\\.upsert"
    - from: "src/vidscope/pipeline/stages/ingest.py"
      to: "uow.videos.upsert_by_platform_id"
      via: "creator= kwarg passed when creator_info is not None"
      pattern: "upsert_by_platform_id\\(.*creator=creator"
    - from: "src/vidscope/pipeline/stages/ingest.py"
      to: "logging"
      via: "WARNING log on D-02 None path with video URL"
      pattern: "logger\\.warning|_logger\\.warning"
---

<objective>
Câbler `IngestStage.execute()` à la fondation Creator de S01 : chaque ingestion réussie upsert le creator puis écrit la vidéo avec `creator_id` populé, le tout dans une seule transaction UoW (D-04). Quand `creator_info is None` (D-02), l'ingest réussit avec `creator_id=NULL` et un WARNING est loggé incluant l'URL de la vidéo.

**Ce plan clôt M006/S02.** Après exécution, chaque nouveau `vidscope add <url>` peuple automatiquement `creators` + `videos.creator_id` + `videos.author` (cache D-03) sans appel réseau supplémentaire.

Purpose: R040 exige que chaque vidéo ingérée soit liée à un `Creator`. S01 a livré la fondation (entity, repo, schema, backfill). S02-P01 a livré le contrat `CreatorInfo`. S02-P02 l'a peuplé au niveau adapter. Il reste le câblage pipeline.

Contrainte architecturale : `pipeline/stages/ingest.py` ne peut importer que `vidscope.ports` et `vidscope.domain` (contrat `pipeline-has-no-adapters`). Le type `CreatorInfo` est dans `ports`, `Creator` et `PlatformUserId` sont dans `domain` — toutes les dépendances sont légales.

Output:
1. `IngestStage.execute()` étendu avec creator upsert (Task 1)
2. 7+ nouveaux tests de câblage creator (Task 2)
3. `scripts/verify-m006-s02.sh` — harness complet M006/S02 (Task 3)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/STATE.md
@.gsd/REQUIREMENTS.md
@.gsd/milestones/M006/slices/S02/S02-CONTEXT.md
@.gsd/milestones/M006/slices/S02/S02-P01-PLAN.md
@.gsd/milestones/M006/slices/S02/S02-P02-PLAN.md
@src/vidscope/pipeline/stages/ingest.py
@src/vidscope/ports/pipeline.py
@src/vidscope/adapters/sqlite/video_repository.py
@src/vidscope/adapters/sqlite/creator_repository.py
@src/vidscope/adapters/sqlite/unit_of_work.py
@src/vidscope/domain/entities.py
@tests/unit/pipeline/stages/test_ingest.py
@.importlinter
@scripts/verify-s01.sh

<interfaces>
<!-- Current IngestStage.execute (lines 97-182 of src/vidscope/pipeline/stages/ingest.py) -->

```python
def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
    # 1. Validate URL + detect platform
    detected_platform = detect_platform(ctx.source_url)
    with tempfile.TemporaryDirectory(prefix="vidscope-ingest-", dir=str(self._cache_dir)) as tmp:
        # 2. Download
        outcome = self._downloader.download(ctx.source_url, tmp)
        # 3. Validate platform match
        if outcome.platform is not detected_platform: raise IngestError(...)
        # 4. Copy media to storage
        source_path = Path(outcome.media_path)
        if not source_path.exists(): raise IngestError(...)
        media_key = _build_media_key(...)
        stored_key = self._media_storage.store(media_key, source_path)
        # 5. Build Video entity
        video = Video(
            platform=outcome.platform,
            platform_id=outcome.platform_id,
            url=outcome.url,
            author=outcome.author,
            title=outcome.title,
            duration=outcome.duration,
            upload_date=outcome.upload_date,
            view_count=outcome.view_count,
            media_key=stored_key,
        )
        # 6. Upsert video (idempotent)
        persisted = uow.videos.upsert_by_platform_id(video)  # <-- NO creator today
        # 7. Mutate context
        ctx.video_id = persisted.id
        ctx.platform = persisted.platform
        ctx.platform_id = persisted.platform_id
        ctx.media_key = persisted.media_key
    return StageResult(message=f"ingested {persisted.platform.value}/{persisted.platform_id}" + ...)
```

<!-- What exists in S01 that this plan consumes -->

From src/vidscope/domain/entities.py (lines 214-247):
```python
@dataclass(frozen=True, slots=True)
class Creator:
    platform: Platform
    platform_user_id: PlatformUserId
    id: CreatorId | None = None
    handle: str | None = None
    display_name: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    follower_count: int | None = None
    is_verified: bool | None = None
    is_orphan: bool = False
    # first_seen_at, last_seen_at, created_at: autopopulated by repo
```

From src/vidscope/adapters/sqlite/creator_repository.py::upsert (lines 36-76) — FULL UPSERT (D-03):
Signature: `def upsert(self, creator: Creator) -> Creator` — returns Creator with populated `id`.
Behaviour: `ON CONFLICT DO UPDATE SET handle=..., display_name=..., follower_count=..., avatar_url=..., last_seen_at=...` (every field except `created_at` and `first_seen_at` is overwritten).

From src/vidscope/adapters/sqlite/video_repository.py::upsert_by_platform_id (lines 53-97) — WRITE-THROUGH (D-03):
Signature: `def upsert_by_platform_id(self, video: Video, creator: Creator | None = None) -> Video`
Behaviour: when `creator is not None`:
  - `payload["author"] = creator.display_name` (if display_name not None)
  - `payload["creator_id"] = int(creator.id)` (if id not None)
Both written atomically in the same SQL statement.

From src/vidscope/adapters/sqlite/unit_of_work.py (lines 77-102):
`uow.creators: CreatorRepository` and `uow.videos: VideoRepository` share the same `Connection` and `Transaction`. Commit at clean exit of `__exit__`, rollback on exception.

From src/vidscope/domain (values.py): `PlatformUserId = NewType("PlatformUserId", str)`

<!-- Logging pattern: currently NO logger exists in pipeline/*.py. Use stdlib logging at module level. -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
<name>Task 1: Étendre IngestStage.execute avec creator upsert + D-02 WARNING + D-04 transaction</name>

<read_first>
- `src/vidscope/pipeline/stages/ingest.py` intégralité (206 lignes) — on ajoute un bloc entre l'étape 4 (media store) et l'étape 6 (video upsert)
- `src/vidscope/ports/pipeline.py` — `CreatorInfo` et `IngestOutcome.creator_info` (disponibles après S02-P01)
- `src/vidscope/domain/entities.py` lignes 214-247 — `Creator` dataclass à construire depuis `CreatorInfo`
- `src/vidscope/domain/values.py` ligne ~50 — `PlatformUserId = NewType("PlatformUserId", str)`
- `src/vidscope/adapters/sqlite/video_repository.py` lignes 53-97 — comprendre la sémantique `upsert_by_platform_id(video, creator=...)` avant de l'appeler
- `src/vidscope/adapters/sqlite/creator_repository.py` lignes 36-76 — confirmer que `upsert` retourne un `Creator` avec `id` populé
- `.importlinter` §`pipeline-has-no-adapters` — contrainte : pas d'import `vidscope.adapters` depuis `pipeline/`. On n'importe que `Creator`, `PlatformUserId` depuis `vidscope.domain` et `CreatorInfo` depuis `vidscope.ports`
- `.gsd/milestones/M006/slices/S02/S02-CONTEXT.md` §D-02 — spec WARNING log
- `.gsd/milestones/M006/slices/S02/S02-CONTEXT.md` §D-04 — spec transaction unique
</read_first>

<behavior>
- Test 1 (D-04 happy path): `outcome.creator_info` présent → `uow.creators.upsert` est appelé UNE fois AVANT `uow.videos.upsert_by_platform_id`, et `creator=` lui est passé → après le `with SqliteUnitOfWork` block : `uow.creators.count() == 1`, `video.creator_id == creator.id`, `video.author == creator.display_name`
- Test 2 (D-02 None path): `outcome.creator_info is None` → `uow.creators.count()` reste à 0, `video.creator_id IS NULL`, `video.author` = `outcome.author` (pas de D-03 write-through quand pas de creator), un WARNING est loggé incluant `ctx.source_url`
- Test 3 (D-04 rollback): si `uow.videos.upsert_by_platform_id` échoue (ex : `StorageError`), `uow.creators.count()` reste à 0 (la transaction UoW a rollback l'upsert creator aussi)
- Test 4 (D-03 idempotent): deux exécutions du stage sur la même URL → `uow.creators.count() == 1` (pas de doublon, full upsert rafraîchit les champs)
- Test 5 (D-03 refresh follower_count): deuxième ingest avec `follower_count` différent → la ligne creator reflète la nouvelle valeur (test via `uow.creators.find_by_platform_user_id`)
- Test 6 (rétrocompat existing): les tests historiques avec `creator_info=None` dans leur FakeDownloader continuent de passer
- Test 7 (WARNING message contient URL): logger WARNING pour D-02 contient `ctx.source_url` brut pour faciliter le diagnostic
</behavior>

<action>
**Modifier `src/vidscope/pipeline/stages/ingest.py`** — ajouter l'import logging, le logger module-level, l'import `Creator`/`PlatformUserId` depuis `vidscope.domain`, et le bloc creator upsert dans `execute()`.

1. **Lignes 28-46** (imports actuels) — remplacer le bloc par :
   ```python
   from __future__ import annotations

   import logging
   import tempfile
   from pathlib import Path

   from vidscope.domain import (
       Creator,
       IngestError,
       Platform,
       PlatformUserId,
       StageName,
       Video,
       detect_platform,
   )
   from vidscope.ports import (
       CreatorInfo,
       Downloader,
       MediaStorage,
       PipelineContext,
       StageResult,
       UnitOfWork,
   )

   __all__ = ["IngestStage"]

   _logger = logging.getLogger(__name__)
   ```

2. **Remplacer la méthode `execute()`** (lignes 97-182) — nouveau corps complet :
   ```python
   def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
       """Download the video, store the media file, upsert the creator
       (when yt-dlp exposed one), and upsert the videos row. Mutates
       ``ctx`` with video_id / platform / platform_id / media_key on
       success.

       Creator wiring (M006/S02)
       -------------------------
       When :attr:`IngestOutcome.creator_info` is populated (yt-dlp
       exposed ``uploader_id``), the stage upserts a :class:`Creator`
       via :attr:`uow.creators` BEFORE the video upsert. The same UoW
       holds both writes, so a video upsert failure rolls back the
       creator upsert — no orphan creator rows survive a failed ingest
       (D-04).

       When ``creator_info is None`` (D-02: compilations, extractors
       that don't expose ``uploader_id``), the stage logs a WARNING and
       proceeds: the video is saved with ``creator_id=NULL``, and
       ``videos.author`` keeps the raw uploader string from
       ``outcome.author``. No exception is raised — this is a
       legitimate ingest outcome.

       Raises
       ------
       IngestError
           Any failure from the downloader, platform detection, or
           storage. The PipelineRunner catches and persists.
       """
       # 1. Validate the URL and detect the platform eagerly so we
       #    don't even call the downloader on obvious garbage.
       detected_platform = detect_platform(ctx.source_url)

       # 2. Download into an ephemeral subdir of the cache. The
       #    tempdir is cleaned up automatically at the end of
       #    this method regardless of success/failure.
       with tempfile.TemporaryDirectory(
           prefix="vidscope-ingest-", dir=str(self._cache_dir)
       ) as tmp:
           outcome = self._downloader.download(ctx.source_url, tmp)

           # The downloader should already set outcome.platform, but
           # we sanity-check it against our own detection. Mismatch
           # means yt-dlp and our detector disagree on what this URL
           # is — surface it instead of silently trusting yt-dlp.
           if outcome.platform is not detected_platform:
               raise IngestError(
                   f"platform mismatch for {ctx.source_url!r}: "
                   f"url parser says {detected_platform.value}, "
                   f"downloader says {outcome.platform.value}",
                   retryable=False,
               )

           # 3. Copy the downloaded file into MediaStorage under a
           #    stable key. Keep the extension from the downloader
           #    so later stages (transcribe, frames) can dispatch
           #    on it if they want.
           source_path = Path(outcome.media_path)
           if not source_path.exists():
               raise IngestError(
                   f"downloader reported media at {source_path} but "
                   f"the file does not exist",
                   retryable=False,
               )

           media_key = _build_media_key(
               platform=outcome.platform,
               platform_id=outcome.platform_id,
               source_path=source_path,
           )
           stored_key = self._media_storage.store(media_key, source_path)

           # 4. Build the domain Video entity with every piece of
           #    metadata the downloader gave us plus the storage key.
           video = Video(
               platform=outcome.platform,
               platform_id=outcome.platform_id,
               url=outcome.url,
               author=outcome.author,
               title=outcome.title,
               duration=outcome.duration,
               upload_date=outcome.upload_date,
               view_count=outcome.view_count,
               media_key=stored_key,
           )

           # 5. Upsert creator (D-01) BEFORE video (D-04 transaction
           #    order). When creator_info is None, skip creator upsert
           #    entirely and log a WARNING (D-02).
           creator: Creator | None = None
           if outcome.creator_info is not None:
               creator = uow.creators.upsert(
                   _creator_from_info(outcome.creator_info, outcome.platform)
               )
           else:
               _logger.warning(
                   "ingest: yt-dlp exposed no uploader_id for %s; "
                   "video will be saved with creator_id=NULL",
                   ctx.source_url,
               )

           # 6. Upsert the videos row. Passing creator= triggers the
           #    D-03 write-through cache in VideoRepository: author +
           #    creator_id are set atomically in the same SQL statement.
           #    platform_id uniqueness makes this idempotent — a second
           #    run updates instead of raising.
           persisted = uow.videos.upsert_by_platform_id(video, creator=creator)

           # 7. Mutate the pipeline context so downstream stages
           #    (transcribe, frames, analyze) can read what we
           #    produced.
           ctx.video_id = persisted.id
           ctx.platform = persisted.platform
           ctx.platform_id = persisted.platform_id
           ctx.media_key = persisted.media_key

       message = (
           f"ingested {persisted.platform.value}/{persisted.platform_id}"
           + (f" — {persisted.title}" if persisted.title else "")
       )
       return StageResult(message=message)
   ```

3. **Ajouter le helper `_creator_from_info` à la fin du fichier** (juste avant ou après `_build_media_key`) :
   ```python
   def _creator_from_info(info: CreatorInfo, platform: Platform) -> Creator:
       """Build a domain :class:`Creator` from a :class:`CreatorInfo` TypedDict.

       Pure function — no I/O, no port dependency beyond the type. The
       ``Creator`` carries ``id=None`` because this is the INPUT to
       :meth:`CreatorRepository.upsert`; the repo assigns the surrogate
       id and returns a new :class:`Creator` with ``id`` populated.

       ``is_orphan`` is always ``False`` here — the orphan path is a
       backfill concern (S01-P04), not a live-ingest one. Live ingest
       always has ``platform_user_id`` at this point (D-02 short-circuit
       ensures we don't reach this helper when ``creator_info is None``).
       """
       return Creator(
           platform=platform,
           platform_user_id=PlatformUserId(info["platform_user_id"]),
           handle=info["handle"],
           display_name=info["display_name"],
           profile_url=info["profile_url"],
           avatar_url=info["avatar_url"],
           follower_count=info["follower_count"],
           is_verified=info["is_verified"],
           is_orphan=False,
       )
   ```

Ne pas modifier `is_satisfied()`, `_build_media_key`, ni les docstrings de classe (les mettre à jour dans la docstring de `execute` suffit).

**Note architecturale** : l'import `from vidscope.domain import Creator, PlatformUserId` est légal (domain est inward), et `from vidscope.ports import CreatorInfo` est légal (ports est inward). Aucun import de `vidscope.adapters`. `lint-imports` doit rester vert (9 contrats).
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/pipeline/stages/test_ingest.py -x -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "^import logging" src/vidscope/pipeline/stages/ingest.py` exit 0
- `grep -q "^_logger = logging.getLogger(__name__)" src/vidscope/pipeline/stages/ingest.py` exit 0
- `grep -q "from vidscope.domain import" src/vidscope/pipeline/stages/ingest.py` exit 0 et la liste inclut `Creator` et `PlatformUserId`
- `grep -q "from vidscope.ports import" src/vidscope/pipeline/stages/ingest.py` exit 0 et la liste inclut `CreatorInfo`
- `grep -q "uow.creators.upsert" src/vidscope/pipeline/stages/ingest.py` exit 0
- `grep -q "upsert_by_platform_id(video, creator=creator)" src/vidscope/pipeline/stages/ingest.py` exit 0
- `grep -q "def _creator_from_info" src/vidscope/pipeline/stages/ingest.py` exit 0
- `grep -q "_logger.warning" src/vidscope/pipeline/stages/ingest.py` exit 0
- `grep -q "creator_id=NULL" src/vidscope/pipeline/stages/ingest.py` exit 0 (présent dans le WARNING message)
- `grep -q "ctx.source_url" src/vidscope/pipeline/stages/ingest.py` exit 0 (présent dans le WARNING format args)
- `grep -v "vidscope.adapters" src/vidscope/pipeline/stages/ingest.py > /dev/null && ! grep -q "vidscope.adapters" src/vidscope/pipeline/stages/ingest.py` exit 0 (aucun import d'adapters — contrainte architecture)
- `python -m uv run lint-imports` exit 0 (9 contrats, `pipeline-has-no-adapters` reste vert)
- `python -m uv run mypy src` exit 0
- `python -m uv run pytest tests/unit/pipeline/stages/test_ingest.py -x -q` exit 0 (tests existants toujours verts — rétrocompat via D-02 None path)
</acceptance_criteria>

<done>
`IngestStage.execute` appelle `uow.creators.upsert` avant `uow.videos.upsert_by_platform_id(video, creator=creator)`, dans une seule UoW transaction. D-02 logge un WARNING avec l'URL. Les 10 tests existants restent verts. 9 contrats import-linter verts.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 2: Tests TestCreatorWiring — happy path, D-02, D-03 idempotent, D-04 rollback</name>

<read_first>
- `tests/unit/pipeline/stages/test_ingest.py` intégralité (396 lignes) — pattern `FakeDownloader`, `_youtube_outcome_factory`, fixtures `engine`, `media_storage`, `cache_dir`
- `src/vidscope/ports/pipeline.py` — `CreatorInfo` TypedDict (pour construire des outcome factories avec creator_info)
- `src/vidscope/pipeline/stages/ingest.py` (après Task 1) — la nouvelle sémantique de `execute`
- `src/vidscope/adapters/sqlite/unit_of_work.py` — `uow.creators`, `uow.videos` sur la même connexion
- `src/vidscope/domain/entities.py` — `Creator` dataclass (pour assertions)
- `src/vidscope/domain/values.py` — `PlatformUserId`, `Platform.YOUTUBE`
</read_first>

<action>
**Modifier `tests/unit/pipeline/stages/test_ingest.py`** pour ajouter :

1. **Dans le bloc d'imports (lignes 9-27), ajouter `caplog` support et les imports Creator/PlatformUserId** :

   Remplacer le bloc existant par :
   ```python
   """Tests for :class:`IngestStage`.

   Uses a fake Downloader, a real LocalMediaStorage under tmp_path, and
   a real SqliteUnitOfWork against an in-memory schema. The goal is to
   exercise the full wiring the stage relies on — ports to adapters —
   without calling yt-dlp or touching the network.
   """

   from __future__ import annotations

   import logging
   from dataclasses import dataclass
   from pathlib import Path

   import pytest
   from sqlalchemy import Engine

   from vidscope.adapters.fs.local_media_storage import LocalMediaStorage
   from vidscope.adapters.sqlite.schema import init_db
   from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
   from vidscope.domain import (
       Creator,
       IngestError,
       Platform,
       PlatformId,
       PlatformUserId,
   )
   from vidscope.infrastructure.sqlite_engine import build_engine
   from vidscope.pipeline.stages.ingest import IngestStage
   from vidscope.ports import CreatorInfo, IngestOutcome, PipelineContext
   ```

2. **Ajouter une nouvelle factory `_youtube_outcome_with_creator_factory`** sous `_youtube_outcome_factory` (lignes 56-74 actuelles) — la rendre paramétrable sur `creator_info` :
   ```python
   def _youtube_outcome_with_creator_factory(
       platform_id: str = "abc123",
       *,
       creator_info: CreatorInfo | None = None,
   ):  # type: ignore[no-untyped-def]
       """Same as _youtube_outcome_factory but allows injecting a CreatorInfo.

       When ``creator_info`` is None, the returned outcome.creator_info
       is None → the D-02 code path in IngestStage fires (WARNING log +
       video with creator_id=NULL).
       """

       def build(destination_dir: str) -> IngestOutcome:
           dest = Path(destination_dir) / f"{platform_id}.mp4"
           dest.write_bytes(b"fake mp4 content")
           return IngestOutcome(
               platform=Platform.YOUTUBE,
               platform_id=PlatformId(platform_id),
               url=f"https://www.youtube.com/watch?v={platform_id}",
               media_path=str(dest),
               title="Fake video title",
               author="Fake Channel",
               duration=42.0,
               upload_date="20260401",
               view_count=1000,
               creator_info=creator_info,
           )

       return build


   def _sample_creator_info(uploader_id: str = "UC_fake") -> CreatorInfo:
       return CreatorInfo(
           platform_user_id=uploader_id,
           handle="Fake Channel",
           display_name="Fake Channel",
           profile_url=f"https://youtube.com/c/{uploader_id}",
           avatar_url="https://yt3.ggpht.com/fake.jpg",
           follower_count=12345,
           is_verified=False,
       )
   ```

3. **Ajouter la classe `TestCreatorWiring` à la fin du fichier** (après `TestStageIdentity`) :
   ```python
   # ---------------------------------------------------------------------------
   # M006/S02-P03 — Creator wiring (D-01, D-02, D-03, D-04)
   # ---------------------------------------------------------------------------


   class TestCreatorWiring:
       """IngestStage integration with the Creator foundation from S01.

       - D-01: creator_info present → creator upsert + video.creator_id
       - D-02: creator_info None → ingest OK, creator_id=NULL, WARNING log
       - D-03: re-ingest → creator row refreshed, no duplicate
       - D-04: single UoW transaction, rollback on video failure
       """

       def test_execute_with_creator_info_upserts_creator_and_links_video(
           self,
           engine: Engine,
           media_storage: LocalMediaStorage,
           cache_dir: Path,
       ) -> None:
           """D-01 happy path: outcome carries creator_info → creator
           row written, video.creator_id set, video.author populated
           from creator.display_name (D-03 write-through cache)."""
           downloader = FakeDownloader(
               outcome_factory=_youtube_outcome_with_creator_factory(
                   "vid_d01",
                   creator_info=_sample_creator_info("UC_d01"),
               )
           )
           stage = IngestStage(
               downloader=downloader,
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           ctx = PipelineContext(
               source_url="https://www.youtube.com/watch?v=vid_d01"
           )

           with SqliteUnitOfWork(engine) as uow:
               stage.execute(ctx, uow)

           with SqliteUnitOfWork(engine) as uow:
               # Exactly one creator written
               assert uow.creators.count() == 1
               creator = uow.creators.find_by_platform_user_id(
                   Platform.YOUTUBE, PlatformUserId("UC_d01")
               )
               assert creator is not None
               assert creator.display_name == "Fake Channel"
               assert creator.follower_count == 12345

               # Video linked to creator
               video = uow.videos.get(ctx.video_id)  # type: ignore[arg-type]
               assert video is not None
               # D-03 write-through: author = creator.display_name
               assert video.author == "Fake Channel"
               # creator_id set atomically in the same SQL statement
               # (read from the raw row to confirm the FK is wired)
               conn = uow._connection  # type: ignore[attr-defined]
               from sqlalchemy import text

               creator_id = conn.execute(
                   text("SELECT creator_id FROM videos WHERE id = :id"),
                   {"id": int(video.id)},  # type: ignore[arg-type]
               ).scalar()
               assert creator_id is not None
               assert int(creator_id) == int(creator.id)  # type: ignore[arg-type]

       def test_execute_without_creator_info_saves_video_with_null_creator_id(
           self,
           engine: Engine,
           media_storage: LocalMediaStorage,
           cache_dir: Path,
           caplog: pytest.LogCaptureFixture,
       ) -> None:
           """D-02: creator_info None → ingest succeeds, creator_id=NULL,
           WARNING logged with the video URL."""
           downloader = FakeDownloader(
               outcome_factory=_youtube_outcome_with_creator_factory(
                   "vid_d02",
                   creator_info=None,
               )
           )
           stage = IngestStage(
               downloader=downloader,
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           url = "https://www.youtube.com/watch?v=vid_d02"
           ctx = PipelineContext(source_url=url)

           with (
               caplog.at_level(
                   logging.WARNING, logger="vidscope.pipeline.stages.ingest"
               ),
               SqliteUnitOfWork(engine) as uow,
           ):
               stage.execute(ctx, uow)

           with SqliteUnitOfWork(engine) as uow:
               # Zero creators written (D-02)
               assert uow.creators.count() == 0

               # Video exists but creator_id IS NULL
               video = uow.videos.get(ctx.video_id)  # type: ignore[arg-type]
               assert video is not None
               # author kept as outcome.author (no D-03 write-through
               # when creator is None)
               assert video.author == "Fake Channel"

               conn = uow._connection  # type: ignore[attr-defined]
               from sqlalchemy import text

               creator_id = conn.execute(
                   text("SELECT creator_id FROM videos WHERE id = :id"),
                   {"id": int(video.id)},  # type: ignore[arg-type]
               ).scalar()
               assert creator_id is None

           # WARNING was logged, and includes the URL
           warning_records = [
               r for r in caplog.records if r.levelno == logging.WARNING
           ]
           assert len(warning_records) >= 1
           assert any(url in r.getMessage() for r in warning_records), (
               f"expected WARNING to include the URL {url!r}, got: "
               f"{[r.getMessage() for r in warning_records]}"
           )

       def test_re_execute_with_updated_follower_count_refreshes_creator(
           self,
           engine: Engine,
           media_storage: LocalMediaStorage,
           cache_dir: Path,
       ) -> None:
           """D-03 idempotent: second ingest with updated follower_count
           refreshes the creator row in-place (no duplicate, fresh value)."""
           # First run: follower_count=12345 (from _sample_creator_info default)
           stage = IngestStage(
               downloader=FakeDownloader(
                   outcome_factory=_youtube_outcome_with_creator_factory(
                       "vid_d03",
                       creator_info=_sample_creator_info("UC_d03"),
                   )
               ),
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           ctx1 = PipelineContext(
               source_url="https://www.youtube.com/watch?v=vid_d03"
           )
           with SqliteUnitOfWork(engine) as uow:
               stage.execute(ctx1, uow)

           # Second run: updated follower_count
           updated_info = CreatorInfo(
               platform_user_id="UC_d03",
               handle="Fake Channel",
               display_name="Fake Channel",
               profile_url="https://youtube.com/c/UC_d03",
               avatar_url="https://yt3.ggpht.com/fake.jpg",
               follower_count=99999,  # bumped
               is_verified=True,  # now verified
           )
           stage2 = IngestStage(
               downloader=FakeDownloader(
                   outcome_factory=_youtube_outcome_with_creator_factory(
                       "vid_d03",
                       creator_info=updated_info,
                   )
               ),
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           ctx2 = PipelineContext(
               source_url="https://www.youtube.com/watch?v=vid_d03"
           )
           with SqliteUnitOfWork(engine) as uow:
               stage2.execute(ctx2, uow)

           with SqliteUnitOfWork(engine) as uow:
               # Still exactly one creator row (full upsert, no duplicate)
               assert uow.creators.count() == 1
               creator = uow.creators.find_by_platform_user_id(
                   Platform.YOUTUBE, PlatformUserId("UC_d03")
               )
               assert creator is not None
               assert creator.follower_count == 99999
               assert creator.is_verified is True
               # And still one video
               assert uow.videos.count() == 1

       def test_video_upsert_failure_rolls_back_creator(
           self,
           engine: Engine,
           media_storage: LocalMediaStorage,
           cache_dir: Path,
           monkeypatch: pytest.MonkeyPatch,
       ) -> None:
           """D-04: single transaction — if uow.videos.upsert_by_platform_id
           raises, the creator upsert is rolled back too. No orphan
           creator rows survive a failed ingest."""
           downloader = FakeDownloader(
               outcome_factory=_youtube_outcome_with_creator_factory(
                   "vid_d04",
                   creator_info=_sample_creator_info("UC_d04_rollback"),
               )
           )
           stage = IngestStage(
               downloader=downloader,
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           ctx = PipelineContext(
               source_url="https://www.youtube.com/watch?v=vid_d04"
           )

           # Force the video upsert to raise. We patch on the concrete
           # SQLite repo class so every new VideoRepositorySQLite
           # instance inherits the broken method.
           from vidscope.adapters.sqlite.video_repository import (
               VideoRepositorySQLite,
           )

           def _boom(
               self: object, video: object, creator: object = None
           ) -> None:
               raise RuntimeError("simulated video upsert failure")

           monkeypatch.setattr(
               VideoRepositorySQLite, "upsert_by_platform_id", _boom
           )

           with pytest.raises(RuntimeError, match="simulated"):
               with SqliteUnitOfWork(engine) as uow:
                   stage.execute(ctx, uow)

           # The UoW __exit__ rollback must have undone the creator upsert
           with SqliteUnitOfWork(engine) as uow:
               assert uow.creators.count() == 0
               assert uow.videos.count() == 0

       def test_two_videos_same_creator_share_one_creator_row(
           self,
           engine: Engine,
           media_storage: LocalMediaStorage,
           cache_dir: Path,
       ) -> None:
           """Two different videos from the same uploader → one creator
           row, two videos both linking to it."""
           info = _sample_creator_info("UC_shared")
           stage = IngestStage(
               downloader=FakeDownloader(
                   outcome_factory=_youtube_outcome_with_creator_factory(
                       "vid_shared_1", creator_info=info
                   )
               ),
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           ctx1 = PipelineContext(
               source_url="https://www.youtube.com/watch?v=vid_shared_1"
           )
           with SqliteUnitOfWork(engine) as uow:
               stage.execute(ctx1, uow)

           stage2 = IngestStage(
               downloader=FakeDownloader(
                   outcome_factory=_youtube_outcome_with_creator_factory(
                       "vid_shared_2", creator_info=info
                   )
               ),
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           ctx2 = PipelineContext(
               source_url="https://www.youtube.com/watch?v=vid_shared_2"
           )
           with SqliteUnitOfWork(engine) as uow:
               stage2.execute(ctx2, uow)

           with SqliteUnitOfWork(engine) as uow:
               assert uow.creators.count() == 1
               assert uow.videos.count() == 2
               creator = uow.creators.find_by_platform_user_id(
                   Platform.YOUTUBE, PlatformUserId("UC_shared")
               )
               assert creator is not None
               # Both videos link to this single creator
               conn = uow._connection  # type: ignore[attr-defined]
               from sqlalchemy import text

               rows = conn.execute(
                   text(
                       "SELECT creator_id FROM videos "
                       "WHERE platform_id IN ('vid_shared_1', 'vid_shared_2')"
                   )
               ).all()
               creator_ids = {r[0] for r in rows}
               assert creator_ids == {int(creator.id)}  # type: ignore[arg-type]

       def test_existing_happy_path_still_works_with_none_creator_info(
           self,
           engine: Engine,
           media_storage: LocalMediaStorage,
           cache_dir: Path,
       ) -> None:
           """Regression: the ORIGINAL _youtube_outcome_factory (no
           creator_info kwarg → defaults to None in IngestOutcome) still
           produces a valid ingest via the D-02 code path."""
           downloader = FakeDownloader(
               outcome_factory=_youtube_outcome_factory("regression_abc")
           )
           stage = IngestStage(
               downloader=downloader,
               media_storage=media_storage,
               cache_dir=cache_dir,
           )
           ctx = PipelineContext(
               source_url="https://www.youtube.com/watch?v=regression_abc"
           )

           with SqliteUnitOfWork(engine) as uow:
               result = stage.execute(ctx, uow)

           assert result.skipped is False
           with SqliteUnitOfWork(engine) as uow:
               assert uow.videos.count() == 1
               assert uow.creators.count() == 0  # D-02 path

       def test_creator_from_info_constructs_domain_creator(self) -> None:
           """_creator_from_info (private helper) builds a Creator from a
           CreatorInfo without I/O. Unit-test the mapping in isolation."""
           from vidscope.pipeline.stages.ingest import _creator_from_info

           info = _sample_creator_info("UC_pure")
           creator = _creator_from_info(info, Platform.TIKTOK)

           assert isinstance(creator, Creator)
           assert creator.platform is Platform.TIKTOK
           assert creator.platform_user_id == "UC_pure"
           assert creator.handle == "Fake Channel"
           assert creator.display_name == "Fake Channel"
           assert creator.follower_count == 12345
           assert creator.is_orphan is False
           assert creator.id is None  # id assigned by repo on upsert
   ```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/pipeline/stages/test_ingest.py::TestCreatorWiring -x -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "class TestCreatorWiring" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "def _youtube_outcome_with_creator_factory" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "def _sample_creator_info" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "test_execute_with_creator_info_upserts_creator_and_links_video" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "test_execute_without_creator_info_saves_video_with_null_creator_id" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "test_re_execute_with_updated_follower_count_refreshes_creator" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "test_video_upsert_failure_rolls_back_creator" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "test_two_videos_same_creator_share_one_creator_row" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "test_existing_happy_path_still_works_with_none_creator_info" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `grep -q "test_creator_from_info_constructs_domain_creator" tests/unit/pipeline/stages/test_ingest.py` exit 0
- `python -m uv run pytest tests/unit/pipeline/stages/test_ingest.py::TestCreatorWiring -x -q` exit 0 (7 nouveaux tests verts)
- `python -m uv run pytest tests/unit/pipeline/stages/test_ingest.py -x -q` exit 0 (tous les tests IngestStage verts, y compris les existants `TestHappyPath`, `TestErrorPaths`, `TestStageIdentity`)
- `python -m uv run pytest -q` exit 0 (suite complète — aucune régression)
- `python -m uv run ruff check src tests` exit 0
- `python -m uv run mypy src` exit 0
</acceptance_criteria>

<done>
7 nouveaux tests `TestCreatorWiring` couvrent D-01 happy, D-02 None + WARNING, D-03 idempotent refresh, D-04 rollback, partage creator entre vidéos, rétrocompat `_youtube_outcome_factory` sans creator_info, et pure mapping `_creator_from_info`. Aucun test existant modifié.
</done>
</task>

<task type="auto" tdd="false">
<name>Task 3: Créer scripts/verify-m006-s02.sh — harness complet M006/S02</name>

<read_first>
- `scripts/verify-s01.sh` intégralité (123 lignes) — template bash exact à mirror : `set -euo pipefail`, `run_step()`, `trap cleanup`, couleurs TTY, summary
- `scripts/verify-s02.sh` lignes 1-30 — confirmer que verify-s02.sh appartient à M001/S02 (PAS à toucher ; raison du nommage `verify-m006-s02.sh`)
- `.gsd/milestones/M006/slices/S02/S02-CONTEXT.md` — must-haves à verrouiller dans les steps
</read_first>

<action>
**Créer `scripts/verify-m006-s02.sh`** (nouveau fichier ; `verify-s02.sh` existe déjà pour M001/S02 — ne PAS l'écraser) :

```bash
#!/usr/bin/env bash
# End-to-end verification of M006/S02 — Ingest stage populates creator.
#
# Runs every check that proves S02's success criteria hold on a
# clean environment. S02 is a pure-pipeline-layer change (no CLI,
# no MCP, no live-network requirement) so this script is fully
# offline — the fakes in tests/unit/pipeline/stages/test_ingest.py
# simulate the yt-dlp info_dict contract.
#
# Usage
# -----
#     bash scripts/verify-m006-s02.sh                    # full run
#     bash scripts/verify-m006-s02.sh --skip-full-suite  # M006/S02 targeted tests only
#
# Exit codes
# ----------
# 0 — every required step passed
# 1 — at least one required step failed
#
# Portability
# -----------
# Works on Windows git-bash, macOS, and Linux via `python -m uv run`.

set -euo pipefail

SKIP_FULL_SUITE=false
for arg in "$@"; do
    case "${arg}" in
        --skip-full-suite) SKIP_FULL_SUITE=true ;;
        -h|--help)
            sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "unknown argument: ${arg}" >&2
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -t 1 ]]; then
    BOLD="\033[1m" GREEN="\033[0;32m" RED="\033[0;31m"
    YELLOW="\033[0;33m" CYAN="\033[0;36m" DIM="\033[2m" RESET="\033[0m"
else
    BOLD="" GREEN="" RED="" YELLOW="" CYAN="" DIM="" RESET=""
fi

step_count=0
failed_steps=()

run_step() {
    local name="$1"
    shift
    step_count=$((step_count + 1))
    printf "\n${CYAN}${BOLD}[%02d] %s${RESET}\n" "${step_count}" "${name}"
    printf "${DIM}\$ %s${RESET}\n" "$*"
    if "$@"; then
        printf "${GREEN}✓${RESET} %s\n" "${name}"
    else
        local exit_code=$?
        printf "${RED}✗${RESET} %s (exit %d)\n" "${name}" "${exit_code}"
        failed_steps+=("${name}")
    fi
}

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-m006-s02-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT

export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

printf "${BOLD}Repo:${RESET}     %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}  %s\n" "${TMP_DATA_DIR}"

# --- 1. Dependency sync ---
run_step "uv sync" python -m uv sync

# --- 2. Quality gates (all green) ---
run_step "ruff check" python -m uv run ruff check src tests scripts
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter (9 contracts, pipeline-has-no-adapters key)" \
    python -m uv run lint-imports

# --- 3. M006/S02 targeted tests — each task's must-haves ---
run_step "P01 CreatorInfo contract tests" \
    python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py -x -q
run_step "P02 YtdlpDownloader creator extraction" \
    python -m uv run pytest \
      tests/unit/adapters/ytdlp/test_downloader.py::TestCreatorInfoExtraction -x -q
run_step "P03 IngestStage creator wiring (D-01/D-02/D-03/D-04)" \
    python -m uv run pytest \
      tests/unit/pipeline/stages/test_ingest.py::TestCreatorWiring -x -q

# --- 4. Regression guards — existing tests must still pass ---
run_step "regression: IngestStage happy/error/identity" \
    python -m uv run pytest \
      tests/unit/pipeline/stages/test_ingest.py::TestHappyPath \
      tests/unit/pipeline/stages/test_ingest.py::TestErrorPaths \
      tests/unit/pipeline/stages/test_ingest.py::TestStageIdentity -x -q
run_step "regression: YtdlpDownloader existing suite" \
    python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q
run_step "regression: S01 foundation tests stay green" \
    python -m uv run pytest \
      tests/unit/adapters/sqlite/test_creator_repository.py \
      tests/unit/adapters/sqlite/test_video_repository.py::TestWriteThroughAuthor \
      tests/unit/adapters/sqlite/test_unit_of_work.py -x -q

# --- 5. Full suite (can be skipped for fast iteration) ---
if [[ "${SKIP_FULL_SUITE}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[full pytest suite] skipped${RESET}\n"
else
    run_step "full pytest suite" python -m uv run pytest -q
fi

# --- Summary ---
printf "\n${BOLD}=== Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ M006/S02 verification PASSED${RESET}\n"
    printf "${DIM}Every new vidscope add <url> now upserts a creator row (when yt-dlp exposes uploader_id) and links it via videos.creator_id — D-01/D-02/D-03/D-04 all enforced.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ M006/S02 verification FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
```

Ne pas modifier `scripts/verify-s01.sh` ni `scripts/verify-s02.sh` (ce dernier appartient à M001/S02).

Sur Windows git-bash, le bit d'exécution n'est pas requis pour l'invocation via `bash scripts/verify-m006-s02.sh`. Le test d'acceptance utilise cette forme.
</action>

<verify>
  <automated>bash scripts/verify-m006-s02.sh --help</automated>
</verify>

<acceptance_criteria>
- `test -f scripts/verify-m006-s02.sh`
- `test -f scripts/verify-s01.sh` (preserved — non-regression on S01 harness)
- `test -f scripts/verify-s02.sh` (preserved — M001/S02 harness untouched)
- `grep -q "set -euo pipefail" scripts/verify-m006-s02.sh` exit 0
- `grep -q "lint-imports" scripts/verify-m006-s02.sh` exit 0
- `grep -q "TestCreatorInfoExtraction" scripts/verify-m006-s02.sh` exit 0
- `grep -q "TestCreatorWiring" scripts/verify-m006-s02.sh` exit 0
- `grep -q "test_pipeline_creator_info.py" scripts/verify-m006-s02.sh` exit 0
- `grep -q "TestWriteThroughAuthor" scripts/verify-m006-s02.sh` exit 0
- `bash scripts/verify-m006-s02.sh --help` exit 0 et affiche "full run" / "targeted tests only"
- `bash scripts/verify-m006-s02.sh --skip-full-suite` exit 0 (tous les steps ciblés + quality gates verts)
- `bash scripts/verify-m006-s02.sh` exit 0 (full run incluant pytest suite complète — tout vert)
</acceptance_criteria>

<done>
`scripts/verify-m006-s02.sh` exécutable via bash, affiche help, `--skip-full-suite` green, run complet green. Le nommage `verify-m006-s02.sh` évite de casser le `verify-s02.sh` existant de M001/S02.
</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| outcome (ports) → IngestStage | `creator_info` est un dict non trusté côté type-system (TypedDict n'est pas runtime-checked) |
| IngestStage → CreatorRepository | Les valeurs `display_name`, `handle`, etc. proviennent ultimement de yt-dlp et transitent par `Creator` → SQL |
| UoW transaction boundary | Un rollback doit annuler creator + video ensemble (atomicity invariant) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-S02P03-01 | **Integrity (I)** — orphan creator row si video upsert échoue entre-temps | `IngestStage.execute()` entre lignes "uow.creators.upsert" et "uow.videos.upsert_by_platform_id" | HIGH | mitigate | D-04 : les deux upserts utilisent le MÊME `uow` qui expose `uow.creators` et `uow.videos` sur la MÊME `Connection` (garanti par `SqliteUnitOfWork.__enter__`). Si l'exécution de `execute()` lève, `SqliteUnitOfWork.__exit__` appelle `_transaction.rollback()` — les deux écritures disparaissent. **Test verrou : `test_video_upsert_failure_rolls_back_creator` assert `uow.creators.count() == 0` après un échec simulé.** |
| T-S02P03-02 | **Tampering (T)** — `platform_user_id` malicieux dans `CreatorInfo` | `_creator_from_info` → `CreatorRepositorySQLite.upsert` | LOW | mitigate | Chaîne déjà testée en S01-P04 T-P04-01 et T-P04-02 : `sqlite_insert().values(**payload)` utilise des bind parameters — pas d'interpolation SQL. `PlatformUserId` est un `NewType(str)` donc accepte n'importe quelle string littérale. Stockée verbatim, pas interprétée. Répété ici pour traçabilité. |
| T-S02P03-03 | **Information Disclosure (I)** — WARNING log leak l'URL de la vidéo (potentiellement une URL privée sous cookies gating) | `_logger.warning("ingest: yt-dlp exposed no uploader_id for %s; ...")` | LOW | accept | L'URL est celle que l'utilisateur a explicitement passée à `vidscope add` : elle est déjà dans `ctx.source_url`, déjà dans les logs `pipeline_runs.source_url`, et c'est précisément ce dont l'utilisateur a besoin pour diagnostiquer le cas D-02. Aucune information supplémentaire n'est divulguée. |
| T-S02P03-04 | **Denial of Service (D)** — creator_info avec des valeurs très larges remplissent la ligne creator (strings de 10MB) | `uow.creators.upsert` côté SQL | LOW | accept | yt-dlp ne renvoie pas des champs de cette taille en pratique (handle < 100 chars, display_name < 256 chars, URLs < 2048 chars). SQLite TEXT est illimité mais l'attaquant devrait contrôler un compte YouTube/TikTok avec des champs UI-limitrophe. Risque faible pour un tool personnel local. Accepted. |
| T-S02P03-05 | **Elevation of Privilege (E)** — pipeline imports adapters directement (violation contrat `pipeline-has-no-adapters`) | `src/vidscope/pipeline/stages/ingest.py` | HIGH | mitigate | Tous les imports ajoutés sont légaux : `Creator`, `PlatformUserId` depuis `vidscope.domain`, `CreatorInfo` depuis `vidscope.ports`. Aucun `vidscope.adapters.*`. Contrat `pipeline-has-no-adapters` verrouillé par `lint-imports` en quality gate et par verify-m006-s02.sh step "import-linter (9 contracts)". **Test verrou : `grep -v "vidscope.adapters" src/vidscope/pipeline/stages/ingest.py` exit 0 vérifie l'absence de cet import.** |
| T-S02P03-06 | **Repudiation** — creator refresh silencieusement écrase des champs (D-03 full upsert overwrite) | `CreatorRepositorySQLite.upsert` ON CONFLICT DO UPDATE | LOW | accept | D-03 choix explicite de l'utilisateur (CONTEXT.md §D-03) : `follower_count` et `display_name` changent par design — les rafraîchir coûte rien. `created_at` et `first_seen_at` SONT préservés (archéologie). Accepted, documenté dans la docstring du stage. |
</threat_model>

<verification>
```bash
# Plan 03 spécifique — chaque catégorie de tests
python -m uv run pytest tests/unit/pipeline/stages/test_ingest.py::TestCreatorWiring -x -q
python -m uv run pytest tests/unit/pipeline/stages/test_ingest.py -x -q

# Harness complet M006/S02
bash scripts/verify-m006-s02.sh

# Non-régression M006/S01 (fondations)
bash scripts/verify-s01.sh --skip-backfill-smoke

# Non-régression globale
python -m uv run pytest -q

# 9 contrats architecture
python -m uv run lint-imports

# Quality gates
python -m uv run ruff check src tests scripts
python -m uv run mypy src
```
</verification>

<success_criteria>
- `IngestStage.execute()` câble creator upsert AVANT video upsert dans la même UoW (D-04)
- D-02 path : `outcome.creator_info is None` → WARNING log avec URL, video avec `creator_id=NULL`, zéro creator row
- D-03 path : re-ingest même `platform_user_id` → 1 seule ligne creator (full upsert rafraîchit `follower_count`, `display_name`, etc. ; `created_at` / `first_seen_at` préservés)
- D-04 path : échec de `upsert_by_platform_id` → rollback total (zéro creator, zéro video)
- Cache D-03 `videos.author` : `video.author == creator.display_name` quand creator fourni (write-through via `upsert_by_platform_id(video, creator=creator)`)
- 7 nouveaux tests `TestCreatorWiring` + le test pur `test_creator_from_info_constructs_domain_creator` tous verts
- Tests existants `TestHappyPath`, `TestErrorPaths`, `TestStageIdentity` restent verts (rétrocompat via D-02 None path)
- 9 contrats import-linter verts (`pipeline-has-no-adapters` vérifié)
- `scripts/verify-m006-s02.sh` exit 0 — harness shippable pour M006/S02
- mypy strict vert, ruff vert
- Suite complète pytest verte
</success_criteria>

<output>
À la fin du plan, créer `.gsd/milestones/M006/slices/S02/S02-P03-SUMMARY.md` résumant :
- Fichiers modifiés (`pipeline/stages/ingest.py`, `tests/unit/pipeline/stages/test_ingest.py`, `scripts/verify-m006-s02.sh`)
- Shape finale de `execute()` (étape 5 creator upsert insérée entre media store et video upsert)
- Liste des 7 tests `TestCreatorWiring` + le test de mapping pur
- Confirmation D-01/D-02/D-03/D-04 verrouillés par tests
- Confirmation rétrocompat (les 10 tests existants de `test_ingest.py` verts)
- Handoff pour M006/S03 (CLI `vidscope creator show/list/videos` — lire `videos.creator_id` et `creators` table)
- Coverage matrix finale S02 (D-01/D-02/D-03/D-04 × Plans P01/P02/P03) pour la SUMMARY de slice S02
</output>
</content>
</invoke>