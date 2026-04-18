---
plan_id: S01-P01
phase: M006/S01
wave: 1
depends_on: []
requirements: [R040, R042]
files_modified:
  - src/vidscope/domain/values.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/pipeline.py
  - tests/unit/domain/test_values.py
  - tests/unit/domain/test_entities.py
  - tests/unit/ports/test_probe_result.py
autonomous: true
---

## Objective

Poser les fondations pures du domaine pour M006/S01 — aucun import externe, aucune I/O, aucun couplage avec l'adaptateur SQLite ou le script de backfill. Ce plan livre (1) les value objects `CreatorId` et `PlatformUserId` (2) l'entité `Creator` en dataclass frozen/slots selon la forme canonique de CONTEXT.md §D-01..D-05 (3) l'extension additive de `ProbeResult` dans `ports/pipeline.py` avec 6 champs nullable permettant au backfill (P04) d'extraire les données créateur depuis yt-dlp sans changer les appelants `cookies test` existants. Tous les exports (`domain/__init__.py`, `ports/__init__.py`) sont mis à jour. Les tests unitaires couvrent les entités, les value objects et le round-trip de la nouvelle `ProbeResult`. Tous les 9 contrats import-linter doivent rester verts : cette couche ne dépend que de stdlib.

## Tasks

<task id="T01-domain-values">
  <name>Ajouter CreatorId et PlatformUserId dans domain/values.py</name>

  <read_first>
    - `src/vidscope/domain/values.py` — patron NewType pour `VideoId` et `PlatformId` à copier
    - `.gsd/milestones/M006/slices/S01/S01-CONTEXT.md` §Creator entity final shape — confirme que `CreatorId = NewType("CreatorId", int)` (surrogate autoincrement) et `PlatformUserId = NewType("PlatformUserId", str)` (yt-dlp uploader_id, str)
    - `.importlinter` — contrat `domain-is-pure` (values.py ne doit importer que stdlib)
  </read_first>

  <action>
  Ouvrir `src/vidscope/domain/values.py`. Ajouter deux nouveaux `NewType` immédiatement après `PlatformId` (lignes ~39-41), en mirroir exact du patron existant (type + commentaire docstring d'une ligne). Le contenu à insérer textuellement :

  ```python
  CreatorId = NewType("CreatorId", int)
  """Database-assigned primary key for a :class:`Creator`. Surrogate
  autoincrement INT PK — opaque to callers, ergonomic for FKs and CLI
  arguments (per D-01)."""

  PlatformUserId = NewType("PlatformUserId", str)
  """Platform-assigned stable user identifier — yt-dlp's ``uploader_id``.
  Never changes on account rename (per D-01). Combined with
  :class:`Platform` it is the canonical UNIQUE key on the ``creators``
  table."""
  ```

  Mettre à jour `__all__` (lignes 26-33) pour inclure `"CreatorId"` et `"PlatformUserId"` en respectant l'ordre alphabétique du tuple existant :

  ```python
  __all__ = [
      "CreatorId",
      "Language",
      "Platform",
      "PlatformId",
      "PlatformUserId",
      "RunStatus",
      "StageName",
      "VideoId",
  ]
  ```

  Aucun autre import requis (`NewType` est déjà importé ligne 24).
  </action>

  <acceptance_criteria>
    - `grep -q 'CreatorId = NewType("CreatorId", int)' src/vidscope/domain/values.py` retourne 0
    - `grep -q 'PlatformUserId = NewType("PlatformUserId", str)' src/vidscope/domain/values.py` retourne 0
    - `grep -q '"CreatorId"' src/vidscope/domain/values.py` retourne 0 (présent dans `__all__`)
    - `grep -q '"PlatformUserId"' src/vidscope/domain/values.py` retourne 0 (présent dans `__all__`)
    - `python -m uv run python -c "from vidscope.domain.values import CreatorId, PlatformUserId; print(CreatorId(42), PlatformUserId('uc123'))"` sort `42 uc123`
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `domain-is-pure` vert)
  </acceptance_criteria>
</task>

<task id="T02-domain-entity">
  <name>Ajouter Creator frozen dataclass dans domain/entities.py (forme canonique CONTEXT.md §D-01..D-05)</name>

  <read_first>
    - `src/vidscope/domain/entities.py` — patron `WatchedAccount` (lignes 170-186) et `Video` (lignes 45-70) — copier `@dataclass(frozen=True, slots=True)` avec champs obligatoires puis optionnels avec défauts
    - `.gsd/milestones/M006/slices/S01/S01-CONTEXT.md` §"Creator entity final shape (canonical)" — forme exacte à coller verbatim
    - `src/vidscope/domain/values.py` — vérifier que `CreatorId` et `PlatformUserId` sont désormais importables (T01 doit être terminé — même fichier, même commit)
    - `.importlinter` — `domain-is-pure`
  </read_first>

  <action>
  Ouvrir `src/vidscope/domain/entities.py`. À la fin du fichier (après `WatchRefresh`, ligne ~208), ajouter le bloc suivant verbatim (copie conforme de S01-CONTEXT.md §Creator entity final shape) :

  ```python
  @dataclass(frozen=True, slots=True)
  class Creator:
      """A content creator — the person/account that uploaded a video.

      Identity anchors on ``(platform, platform_user_id)`` — the
      platform-issued stable id (yt-dlp's ``uploader_id``) that survives
      account renames (per D-01). ``handle`` is the human-facing @-name
      which MAY change; the repository preserves rename history by
      updating the row in place. ``id`` is a surrogate autoincrement
      populated by the repository on upsert.

      ``is_orphan`` is set to ``True`` by the backfill script when
      re-probing yt-dlp returns NOT_FOUND or AUTH_REQUIRED: every video
      still gets an FK populated, no data is lost, and the flag
      surfaces later in listings (per D-02). ``avatar_url`` is a URL
      string only — no image download, no MediaStorage write (per D-05).
      ``follower_count`` is the current scalar value only — temporal
      engagement lives in M009's ``video_stats`` / future
      ``creator_stats`` (per D-04).
      """

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
      first_seen_at: datetime | None = None
      last_seen_at: datetime | None = None
      created_at: datetime | None = None
  ```

  Mettre à jour l'import `vidscope.domain.values` (lignes 24-31) pour inclure `CreatorId` et `PlatformUserId` :

  ```python
  from vidscope.domain.values import (
      CreatorId,
      Language,
      Platform,
      PlatformId,
      PlatformUserId,
      RunStatus,
      StageName,
      VideoId,
  )
  ```

  Ajouter `"Creator"` dans `__all__` (lignes 33-42) en respectant l'ordre alphabétique :

  ```python
  __all__ = [
      "Analysis",
      "Creator",
      "Frame",
      "PipelineRun",
      "Transcript",
      "TranscriptSegment",
      "Video",
      "WatchRefresh",
      "WatchedAccount",
  ]
  ```

  Enfin, mettre à jour `src/vidscope/domain/__init__.py` pour re-exporter `Creator`, `CreatorId`, `PlatformUserId` :
  - Ajouter `Creator` à l'import depuis `.entities` (lignes 13-22)
  - Ajouter `CreatorId`, `PlatformUserId` à l'import depuis `.values` (lignes 36-43)
  - Ajouter `"Creator"`, `"CreatorId"`, `"PlatformUserId"` aux sections correspondantes de `__all__` (lignes 45-75) en respectant les groupes `# entities` / `# values`
  </action>

  <acceptance_criteria>
    - `grep -q "class Creator:" src/vidscope/domain/entities.py` exit 0
    - `grep -q "@dataclass(frozen=True, slots=True)" src/vidscope/domain/entities.py` trouve ≥ 8 occurrences (7 existantes + 1 nouvelle)
    - `grep -q "platform_user_id: PlatformUserId" src/vidscope/domain/entities.py` exit 0
    - `grep -q "is_orphan: bool = False" src/vidscope/domain/entities.py` exit 0
    - `grep -q '"Creator"' src/vidscope/domain/__init__.py` exit 0
    - `python -m uv run python -c "from vidscope.domain import Creator, CreatorId, PlatformUserId, Platform; c = Creator(platform=Platform.YOUTUBE, platform_user_id=PlatformUserId('UC123')); print(c.is_orphan, c.id)"` sort `False None`
    - `python -m uv run python -c "from vidscope.domain import Creator, Platform, PlatformUserId; c = Creator(platform=Platform.YOUTUBE, platform_user_id=PlatformUserId('x')); c.handle = 'x'"` échoue avec `dataclasses.FrozenInstanceError` (frozen)
    - `python -m uv run python -c "from vidscope.domain import Creator, Platform, PlatformUserId; c = Creator(platform=Platform.YOUTUBE, platform_user_id=PlatformUserId('x')); print(hasattr(c, '__dict__'))"` sort `False` (slots actifs)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0
  </acceptance_criteria>
</task>

<task id="T03-probe-result-port">
  <name>Étendre ProbeResult dans ports/pipeline.py avec 6 champs nullable (additive, zéro breaking change)</name>

  <read_first>
    - `src/vidscope/ports/pipeline.py` lignes 190-215 — définition actuelle de `ProbeResult` (4 champs : `status`, `url`, `detail`, `title`)
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"yt-dlp info_dict fields → Creator fields" — mapping qui dicte les noms exacts des nouveaux champs
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"Downloader.probe() return shape" — confirme que l'appelant `vidscope cookies test` ne lit que `.status` et `.title`, donc les ajouts sont additifs non-breaking
    - `.importlinter` — `ports-are-pure` (pipeline.py ne doit importer que domain + stdlib)
  </read_first>

  <action>
  Ouvrir `src/vidscope/ports/pipeline.py`. Localiser le dataclass `ProbeResult` (autour des lignes 190-215). Ajouter exactement 6 champs nullable APRÈS `title: str | None = None` (ordre : tous optionnels avec valeur par défaut `None` pour préserver la construction positionnelle existante) :

  ```python
  @dataclass(frozen=True, slots=True)
  class ProbeResult:
      """Outcome of :meth:`Downloader.probe`.

      The probe is a metadata-only call (no media download, no transcribe,
      no DB write) used by ``vidscope cookies test`` to verify that the
      configured cookies actually authenticate against a gated platform,
      and by the M006 backfill script to recover creator metadata from
      already-ingested videos.

      Attributes
      ----------
      status:
          High-level outcome — see :class:`ProbeStatus`.
      url:
          The URL that was probed.
      detail:
          Human-readable detail. On ``ok``, the resolved title or video id.
          On any failure, a short message suitable for CLI display.
      title:
          Resolved video title when ``status == ProbeStatus.OK``, ``None``
          otherwise.
      uploader:
          yt-dlp's ``uploader`` field — the human-friendly creator name
          (e.g. "MrBeast"). ``None`` when the extractor does not expose it.
          Consumed by the M006 backfill script to populate
          ``Creator.display_name``.
      uploader_id:
          yt-dlp's ``uploader_id`` field — the platform-stable id that
          survives renames. Consumed by the M006 backfill script to
          populate ``Creator.platform_user_id`` (the canonical UNIQUE key).
      uploader_url:
          Creator profile URL. Consumed as ``Creator.profile_url``.
      channel_follower_count:
          Current follower count when yt-dlp exposes it. Consumed as
          ``Creator.follower_count`` (per D-04: scalar only, no
          time-series — M009 owns temporal data).
      uploader_thumbnail:
          Creator avatar URL (first URL if yt-dlp returns a list).
          Consumed as ``Creator.avatar_url`` (per D-05: string only,
          no image download).
      uploader_verified:
          Verified-badge flag when exposed. Not consistently populated
          across extractors — ``None`` is normal.
      """

      status: ProbeStatus
      url: str
      detail: str
      title: str | None = None
      uploader: str | None = None
      uploader_id: str | None = None
      uploader_url: str | None = None
      channel_follower_count: int | None = None
      uploader_thumbnail: str | None = None
      uploader_verified: bool | None = None
  ```

  Ne pas modifier la classe `ProbeStatus` ni les autres symboles. Le `__all__` existant de `pipeline.py` (lignes 52-66) inclut déjà `"ProbeResult"` — aucune mise à jour d'export nécessaire.

  `ports/__init__.py` exporte déjà `ProbeResult` (ligne 28) — rien à changer.

  Vérifier que l'adaptateur existant `src/vidscope/adapters/ytdlp/downloader.py::probe` (lignes 264-315) compile toujours car il construit `ProbeResult` par kwargs avec seulement les anciens champs. Aucune modification de l'adaptateur ici : la moitié adaptateur (populer les nouveaux champs) est livrée en P04. T03 ne fait QUE l'extension de port.
  </action>

  <acceptance_criteria>
    - `grep -q "uploader: str | None = None" src/vidscope/ports/pipeline.py` exit 0
    - `grep -q "uploader_id: str | None = None" src/vidscope/ports/pipeline.py` exit 0
    - `grep -q "channel_follower_count: int | None = None" src/vidscope/ports/pipeline.py` exit 0
    - `grep -q "uploader_thumbnail: str | None = None" src/vidscope/ports/pipeline.py` exit 0
    - `grep -q "uploader_verified: bool | None = None" src/vidscope/ports/pipeline.py` exit 0
    - `python -m uv run python -c "from vidscope.ports import ProbeResult, ProbeStatus; r = ProbeResult(status=ProbeStatus.OK, url='x', detail='y'); print(r.uploader, r.uploader_id)"` sort `None None`
    - `python -m uv run python -c "from vidscope.ports import ProbeResult, ProbeStatus; r = ProbeResult(status=ProbeStatus.OK, url='x', detail='y', uploader='MrBeast', uploader_id='UC123', channel_follower_count=1_000_000); print(r.uploader, r.uploader_id, r.channel_follower_count)"` sort `MrBeast UC123 1000000`
    - `python -m uv run pytest tests/unit/adapters/ytdlp -x -q` exit 0 (les tests existants de `downloader.py::probe` restent verts — zéro breaking change)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `ports-are-pure` vert)
  </acceptance_criteria>
</task>

<task id="T04-tests-domain-ports">
  <name>Tests unitaires pour Creator, CreatorId, PlatformUserId et ProbeResult étendu</name>

  <read_first>
    - `tests/unit/domain/test_entities.py` lignes 1-50 — patron `TestVideo` (frozen, slots, defaults) + imports à copier
    - `tests/unit/domain/test_values.py` lignes 1-30 — patron `TestPlatform` + imports
    - `src/vidscope/domain/entities.py` — forme finale de `Creator` (après T02)
    - `src/vidscope/domain/values.py` — `CreatorId`, `PlatformUserId` (après T01)
    - `src/vidscope/ports/pipeline.py` — `ProbeResult` étendu (après T03)
  </read_first>

  <action>
  Étendre trois fichiers de tests existants + créer un nouveau fichier port-level :

  **1. `tests/unit/domain/test_values.py` — ajouter une classe `TestCreatorId` et une classe `TestPlatformUserId`** à la fin du fichier, en mirroir de `TestPlatform` :

  ```python
  class TestCreatorId:
      def test_is_int_newtype(self) -> None:
          cid = CreatorId(42)
          assert cid == 42
          assert isinstance(cid, int)

      def test_round_trip_preserves_value(self) -> None:
          assert int(CreatorId(0)) == 0
          assert int(CreatorId(999_999)) == 999_999


  class TestPlatformUserId:
      def test_is_str_newtype(self) -> None:
          puid = PlatformUserId("UC123")
          assert puid == "UC123"
          assert isinstance(puid, str)

      def test_accepts_empty_string(self) -> None:
          # NewType is type-level only; empty strings are legal at
          # runtime. Adapter-layer validation handles rejection.
          assert PlatformUserId("") == ""
  ```

  Mettre à jour l'import en haut du fichier pour inclure `CreatorId` et `PlatformUserId`.

  **2. `tests/unit/domain/test_entities.py` — ajouter une classe `TestCreator`** à la fin, en mirroir de `TestVideo` et `TestWatchedAccount` :

  ```python
  class TestCreator:
      def _minimal(self) -> Creator:
          return Creator(
              platform=Platform.YOUTUBE,
              platform_user_id=PlatformUserId("UC_ABC"),
          )

      def test_minimal_creator_has_defaults(self) -> None:
          c = self._minimal()
          assert c.id is None
          assert c.handle is None
          assert c.display_name is None
          assert c.profile_url is None
          assert c.avatar_url is None
          assert c.follower_count is None
          assert c.is_verified is None
          assert c.is_orphan is False
          assert c.first_seen_at is None
          assert c.last_seen_at is None
          assert c.created_at is None

      def test_creator_is_frozen(self) -> None:
          c = self._minimal()
          with pytest.raises(FrozenInstanceError):
              c.handle = "@new"  # type: ignore[misc]

      def test_creator_uses_slots(self) -> None:
          c = self._minimal()
          assert not hasattr(c, "__dict__")

      def test_creator_equality_by_fields(self) -> None:
          a = Creator(
              platform=Platform.YOUTUBE,
              platform_user_id=PlatformUserId("UC_ABC"),
              handle="@creator",
              display_name="The Creator",
          )
          b = Creator(
              platform=Platform.YOUTUBE,
              platform_user_id=PlatformUserId("UC_ABC"),
              handle="@creator",
              display_name="The Creator",
          )
          assert a == b

      def test_orphan_flag_round_trips(self) -> None:
          c = Creator(
              platform=Platform.INSTAGRAM,
              platform_user_id=PlatformUserId("orphan:legacy_author"),
              is_orphan=True,
          )
          assert c.is_orphan is True

      def test_full_fields_construction(self) -> None:
          now = UTC_NOW
          c = Creator(
              platform=Platform.TIKTOK,
              platform_user_id=PlatformUserId("12345"),
              id=CreatorId(7),
              handle="@test",
              display_name="Test",
              profile_url="https://tiktok.com/@test",
              avatar_url="https://cdn/test.jpg",
              follower_count=100_000,
              is_verified=True,
              is_orphan=False,
              first_seen_at=now,
              last_seen_at=now,
              created_at=now,
          )
          assert c.id == 7
          assert c.follower_count == 100_000
          assert c.is_verified is True
  ```

  Mettre à jour les imports en haut du fichier pour inclure `Creator`, `CreatorId`, `PlatformUserId`.

  **3. Créer `tests/unit/ports/__init__.py`** (fichier vide, nouveau sous-package) si absent. Vérifier avec `ls tests/unit/ports/ 2>/dev/null`. Si le dossier n'existe pas, créer le dossier + `__init__.py` vide.

  **4. Créer `tests/unit/ports/test_probe_result.py`** :

  ```python
  """Unit tests for the ProbeResult dataclass extension (M006/S01).

  ProbeResult gained 6 optional fields in M006/S01 so the backfill
  script can extract creator metadata from yt-dlp probe() without a
  second port method. Tests assert: (a) the new fields default to
  None, preserving backward compatibility for `vidscope cookies test`
  callers that only read .status and .title, (b) every field round-
  trips through construction, (c) the dataclass stays frozen.
  """

  from __future__ import annotations

  from dataclasses import FrozenInstanceError

  import pytest

  from vidscope.ports import ProbeResult, ProbeStatus


  class TestProbeResultDefaults:
      def test_minimal_construction_leaves_new_fields_none(self) -> None:
          r = ProbeResult(status=ProbeStatus.OK, url="https://x", detail="ok")
          assert r.title is None
          assert r.uploader is None
          assert r.uploader_id is None
          assert r.uploader_url is None
          assert r.channel_follower_count is None
          assert r.uploader_thumbnail is None
          assert r.uploader_verified is None

      def test_full_construction_populates_all_fields(self) -> None:
          r = ProbeResult(
              status=ProbeStatus.OK,
              url="https://youtube.com/watch?v=abc",
              detail="resolved: Intro",
              title="Intro",
              uploader="MrBeast",
              uploader_id="UCX6OQ3DkcsbYNE6H8uQQuVA",
              uploader_url="https://youtube.com/@MrBeast",
              channel_follower_count=200_000_000,
              uploader_thumbnail="https://yt3.cdn/avatar.jpg",
              uploader_verified=True,
          )
          assert r.uploader == "MrBeast"
          assert r.uploader_id == "UCX6OQ3DkcsbYNE6H8uQQuVA"
          assert r.channel_follower_count == 200_000_000
          assert r.uploader_verified is True

      def test_probe_result_is_frozen(self) -> None:
          r = ProbeResult(status=ProbeStatus.OK, url="x", detail="y")
          with pytest.raises(FrozenInstanceError):
              r.uploader = "mutate"  # type: ignore[misc]
  ```

  Respecter la convention française/anglaise : code et identifiants en anglais (voir tests existants).
  </action>

  <acceptance_criteria>
    - `python -m uv run pytest tests/unit/domain/test_values.py::TestCreatorId -x -q` exit 0
    - `python -m uv run pytest tests/unit/domain/test_values.py::TestPlatformUserId -x -q` exit 0
    - `python -m uv run pytest tests/unit/domain/test_entities.py::TestCreator -x -q` exit 0
    - `python -m uv run pytest tests/unit/ports/test_probe_result.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/domain tests/unit/ports -q` exit 0 (suite complète domaine + ports verte)
    - `python -m uv run pytest -q` exit 0 (suite complète : aucune régression)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - Nouveau fichier `tests/unit/ports/__init__.py` présent : `test -f tests/unit/ports/__init__.py`
    - Nouveau fichier `tests/unit/ports/test_probe_result.py` présent et contient au moins 3 méthodes de test (`grep -c "def test_" tests/unit/ports/test_probe_result.py` ≥ 3)
  </acceptance_criteria>
</task>

## Verification Criteria

Commandes exécutables qui prouvent la complétion de P01 (ordre : plus spécifique → plus large) :

```bash
# Tests par couche
python -m uv run pytest tests/unit/domain/test_values.py::TestCreatorId tests/unit/domain/test_values.py::TestPlatformUserId -x -q
python -m uv run pytest tests/unit/domain/test_entities.py::TestCreator -x -q
python -m uv run pytest tests/unit/ports/test_probe_result.py -x -q

# Suite complète (domaine + ports + rien de cassé ailleurs)
python -m uv run pytest -q

# Quality gates (les 4 portes du projet)
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

Les 9 contrats import-linter restent verts — ce plan n'introduit que des additions dans `vidscope.domain` et `vidscope.ports`, toutes stdlib-only.

## Must-Haves

Garanties concrètes livrées par P01 :

- `Creator` frozen dataclass avec `slots=True` existe dans `vidscope.domain.entities` avec la forme canonique CONTEXT.md §D-01..D-05 (13 champs, ordre canonique, defaults corrects dont `is_orphan: bool = False`)
- `CreatorId` et `PlatformUserId` existent dans `vidscope.domain.values` comme `NewType("CreatorId", int)` / `NewType("PlatformUserId", str)`
- `vidscope.domain.__init__` re-exporte `Creator`, `CreatorId`, `PlatformUserId` (P02 pourra `from vidscope.domain import Creator, CreatorId, PlatformUserId`)
- `ProbeResult` dans `vidscope.ports.pipeline` porte 6 champs nullable additionnels (`uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail`, `uploader_verified`) — zéro breaking change pour `vidscope cookies test`
- Les tests unitaires (`TestCreator`, `TestCreatorId`, `TestPlatformUserId`, `tests/unit/ports/test_probe_result.py`) passent — frozen + slots + defaults + round-trip complet couverts
- Les 9 contrats `.importlinter` restent verts (la couche ajoutée ne dépend que de stdlib)
- Aucun blocker pour P02 (port CreatorRepository Protocol) ni pour P04 (YtdlpDownloader.probe peut désormais populer les nouveaux champs)

## Threat Model

Surface de menace de P01 (fondations pures, pas d'I/O) :

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-P01-01 | **Tampering (T)** | `Creator` dataclass | LOW | mitigate | `frozen=True` empêche la mutation runtime. Le test `test_creator_is_frozen` vérifie que `FrozenInstanceError` est levée. Couvre les accidents dev, pas un attaquant avec `object.__setattr__`. |
| T-P01-02 | **Information Disclosure (I)** | `ProbeResult.uploader*` fields | LOW | accept | Les champs sont optionnels et ne portent que les données que yt-dlp expose publiquement (API yt-dlp publique, mêmes données que `youtube.com` elles-mêmes). Aucune PII sensible au-delà de ce qui est déjà public. |
| T-P01-03 | **Denial of Service (D)** | `CreatorId`/`PlatformUserId` NewType | NONE | accept | `NewType` est zéro-coût runtime (alias type uniquement). Pas de chemin d'exécution exploitable. |

Aucune menace majeure à ce stade : P01 n'ajoute que des structures de données pures, sans chemin d'I/O, sans parsing, sans surface réseau. Les menaces réelles (injection SQL via handle, tampering de réponses yt-dlp, perte de données sur `--apply`) apparaissent dans P03 (adaptateur SQL) et P04 (backfill). Elles sont modélisées dans les plans correspondants.
