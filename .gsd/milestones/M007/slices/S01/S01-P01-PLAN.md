---
plan_id: S01-P01
phase: M007/S01
wave: 1
depends_on: []
requirements: [R043, R045]
files_modified:
  - src/vidscope/domain/values.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - tests/unit/domain/test_values.py
  - tests/unit/domain/test_entities.py
autonomous: true
---

## Objective

Poser les fondations pures du domaine pour M007 — aucun import externe, aucune I/O, aucun couplage avec SQLAlchemy ou la pipeline. Ce plan livre (1) l'extension additive de `Video` avec 3 nouvelles colonnes (`description`, `music_track`, `music_artist`) par D-01 (2) deux nouvelles entités `Hashtag` et `Mention` en frozen dataclass avec `slots=True` (3) un nouveau membre `StageName.METADATA_EXTRACT = "metadata_extract"` dans `values.py` afin que S03 puisse wirer le stage sans conflit runner (Risk 1 de RESEARCH.md) (4) les tests unitaires pour canonicalisation (lowercase lstrip `#`/`@`), frozen, slots, round-trip. Les 9 contrats import-linter restent verts : cette couche ne dépend que de stdlib.

Note D-01 (D-03) : `MusicTrack` entity N'EST PAS créée — les 3 colonnes musicales sont ajoutées directement sur `Video` (voir CONTEXT.md §D-01). `Mention` stocke `handle: str` + `platform: Platform | None` SANS `creator_id` FK (voir CONTEXT.md §D-03).

## Tasks

<task id="T01-domain-values-extension">
  <name>Ajouter StageName.METADATA_EXTRACT dans domain/values.py</name>

  <read_first>
    - `src/vidscope/domain/values.py` lignes 84-96 — patron `StageName` StrEnum existant à étendre (5 membres actuels)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"StageName — nouveau membre" et §"Risk 1" — explique pourquoi il faut ajouter le membre DANS S01 (ordre canonique), avant S03 wire le stage
    - `src/vidscope/pipeline/runner.py` lignes 312-325 — `_resolve_stage_phase()` lève `StageCrashError` si le nom n'est pas dans l'enum, d'où l'obligation d'ajouter METADATA_EXTRACT avant le wiring S03
    - `.importlinter` — contrat `domain-is-pure` (values.py ne doit importer que stdlib)
  </read_first>

  <action>
  Ouvrir `src/vidscope/domain/values.py`. Dans la classe `StageName` (lignes 84-96), ajouter un nouveau membre `METADATA_EXTRACT` ENTRE `ANALYZE` et `INDEX` pour refléter l'ordre canonique d'exécution du pipeline (voir RESEARCH.md §"Ordre dans le pipeline" : `ingest → transcribe → frames → analyze → metadata_extract → index`).

  Remplacer le bloc existant :

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
      INDEX = "index"
  ```

  Par :

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
      METADATA_EXTRACT = "metadata_extract"
      INDEX = "index"
  ```

  Aucune autre modification dans `values.py`. `__all__` (lignes 26-35) inclut déjà `"StageName"` — pas de changement d'export.
  </action>

  <acceptance_criteria>
    - `grep -q 'METADATA_EXTRACT = "metadata_extract"' src/vidscope/domain/values.py` exit 0
    - `python -m uv run python -c "from vidscope.domain import StageName; print(StageName.METADATA_EXTRACT.value)"` affiche `metadata_extract`
    - `python -m uv run python -c "from vidscope.domain import StageName; print(list(StageName))"` liste les 6 membres dans l'ordre `[INGEST, TRANSCRIBE, FRAMES, ANALYZE, METADATA_EXTRACT, INDEX]`
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `domain-is-pure` vert)
  </acceptance_criteria>
</task>

<task id="T02-video-extension-hashtag-mention" tdd="true">
  <name>Étendre Video avec 3 colonnes (D-01) + ajouter Hashtag et Mention dans domain/entities.py</name>

  <read_first>
    - `src/vidscope/domain/entities.py` lignes 48-74 — définition actuelle de `Video` dataclass (10 champs) à étendre avec 3 nouveaux champs optionnels
    - `src/vidscope/domain/entities.py` lignes 215-248 — patron `Creator` frozen dataclass avec slots + docstring + ordre champs obligatoires/optionnels à miroir pour `Hashtag` et `Mention`
    - `src/vidscope/domain/values.py` — vérifier que `VideoId`, `Platform` sont importés
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-01 (colonnes sur Video) et §D-03 (Mention sans creator_id FK, platform optionnelle)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §S01 "Canonicalisation des hashtags" + §"Canonicalisation des mentions"
    - `.importlinter` — `domain-is-pure`
  </read_first>

  <behavior>
    - Test 1 (Video): `Video(platform=Platform.YOUTUBE, platform_id=PlatformId("x"), url="u")` construit sans erreur; `video.description is None`, `video.music_track is None`, `video.music_artist is None` (defaults).
    - Test 2 (Video): construction avec les 3 nouveaux champs `description="caption text"`, `music_track="Song"`, `music_artist="Artist"` round-trip et lit les valeurs.
    - Test 3 (Video): frozen — `video.description = "x"` lève `FrozenInstanceError`.
    - Test 4 (Hashtag): `Hashtag(video_id=VideoId(1), tag="coding")` construit, `id is None` par défaut.
    - Test 5 (Hashtag): frozen + slots — `FrozenInstanceError` sur mutation, `hasattr(h, "__dict__") is False`.
    - Test 6 (Hashtag): le dataclass stocke la valeur telle que passée (canonicalisation est responsabilité du CALLER / adapter, pas du dataclass).
    - Test 7 (Mention): `Mention(video_id=VideoId(1), handle="alice")` construit avec `platform=None`, `id=None` par défaut.
    - Test 8 (Mention): `Mention(video_id=VideoId(1), handle="alice", platform=Platform.TIKTOK)` accepte une plateforme optionnelle.
    - Test 9 (Mention): frozen + slots identique à Hashtag.
    - Test 10 (égalité): deux `Hashtag` avec mêmes champs sont égaux (`==` vrai).
  </behavior>

  <action>
  **Étape A — Étendre `Video`** dans `src/vidscope/domain/entities.py` (lignes 48-74). Ajouter 3 nouveaux champs APRÈS `creator_id: CreatorId | None = None` (ligne 70) pour préserver l'ordre des defaults :

  Remplacer le bloc existant :

  ```python
  @dataclass(frozen=True, slots=True)
  class Video:
      """A single video record ingested from a source platform.

      ``id`` is ``None`` until the repository persists the row; the
      repository returns a new instance with ``id`` populated.

      ``media_key`` is the opaque storage key resolved by :class:`MediaStorage`.
      ``None`` means the ingest stage has not completed yet.
      """

      platform: Platform
      platform_id: PlatformId
      url: str
      id: VideoId | None = None
      author: str | None = None
      title: str | None = None
      duration: float | None = None
      upload_date: str | None = None
      view_count: int | None = None
      media_key: str | None = None
      created_at: datetime | None = None
      creator_id: CreatorId | None = None

      def is_ingested(self) -> bool:
          """Return ``True`` once the ingest stage has stored a media file."""
          return self.media_key is not None
  ```

  Par la version étendue (ajouter le docstring pour les nouveaux champs + 3 champs nullable après creator_id) :

  ```python
  @dataclass(frozen=True, slots=True)
  class Video:
      """A single video record ingested from a source platform.

      ``id`` is ``None`` until the repository persists the row; the
      repository returns a new instance with ``id`` populated.

      ``media_key`` is the opaque storage key resolved by :class:`MediaStorage`.
      ``None`` means the ingest stage has not completed yet.

      ``description``, ``music_track``, ``music_artist`` carry the raw
      platform caption verbatim and the music identification reported by
      the platform (per M007 D-01). Stored as direct columns on the
      ``videos`` table — no ``VideoMetadata`` side entity exists (D-01
      rejects the side-entity alternative so ``vidscope show`` reads
      every caption/music field in a single row fetch, zero JOIN). All
      three fields are ``None`` when the platform does not expose them;
      they are NEVER populated with a synthesised placeholder (per R045).
      """

      platform: Platform
      platform_id: PlatformId
      url: str
      id: VideoId | None = None
      author: str | None = None
      title: str | None = None
      duration: float | None = None
      upload_date: str | None = None
      view_count: int | None = None
      media_key: str | None = None
      created_at: datetime | None = None
      creator_id: CreatorId | None = None
      description: str | None = None
      music_track: str | None = None
      music_artist: str | None = None

      def is_ingested(self) -> bool:
          """Return ``True`` once the ingest stage has stored a media file."""
          return self.media_key is not None
  ```

  **Étape B — Ajouter `Hashtag` et `Mention`** à la fin du fichier (après `Creator`, ligne ~249) :

  ```python
  @dataclass(frozen=True, slots=True)
  class Hashtag:
      """A hashtag attached to a video (e.g. ``"cooking"`` for ``#Cooking``).

      Stored in a side table keyed by ``(video_id, tag)`` — the same
      canonical pattern as :class:`Creator` (per M007 D-05). ``tag`` is
      the canonical lowercase form WITHOUT the leading ``#`` (per
      D-04: ``#Coding`` and ``#coding`` must match exactly after
      canonicalisation). The adapter that inserts the row (M007/S01
      ``HashtagRepositorySQLite``) is the single place responsible for
      applying ``tag.lower().lstrip("#")`` — the dataclass itself
      preserves whatever value the caller passes so tests and fixtures
      can construct instances deterministically.

      ``id`` is ``None`` until the repository persists the row; the
      repository returns a new instance with ``id`` populated.
      """

      video_id: VideoId
      tag: str
      id: int | None = None
      created_at: datetime | None = None


  @dataclass(frozen=True, slots=True)
  class Mention:
      """An ``@handle`` mention extracted from a video's description.

      Stored in a side table keyed by ``(video_id, handle)`` — same side-
      table pattern as :class:`Hashtag` (per M007 D-05). ``handle`` is
      the canonical lowercase form WITHOUT the leading ``@`` (per D-04
      exact-match facet). ``platform`` is optional: when the mention
      syntax unambiguously identifies a platform (e.g. a TikTok-only
      handle pattern) the extractor MAY populate it; otherwise ``None``
      is legitimate. Per D-03, no ``creator_id`` FK is stored — the
      Mention↔Creator linkage is derivable via JOIN at query time and
      is deliberately deferred to M011. This keeps ingest free of any
      extra DB lookups per mention.

      ``id`` is ``None`` until the repository persists the row; the
      repository returns a new instance with ``id`` populated.
      """

      video_id: VideoId
      handle: str
      platform: Platform | None = None
      id: int | None = None
      created_at: datetime | None = None
  ```

  **Étape C — Mettre à jour `__all__`** (lignes 35-45) pour inclure `"Hashtag"` et `"Mention"` en respectant l'ordre alphabétique :

  ```python
  __all__ = [
      "Analysis",
      "Creator",
      "Frame",
      "Hashtag",
      "Mention",
      "PipelineRun",
      "Transcript",
      "TranscriptSegment",
      "Video",
      "WatchRefresh",
      "WatchedAccount",
  ]
  ```

  **Étape D — Mettre à jour `src/vidscope/domain/__init__.py`** pour re-exporter `Hashtag` et `Mention`. Ouvrir le fichier, localiser les imports depuis `.entities` et les ajouter dans l'ordre alphabétique ; ajouter `"Hashtag"` et `"Mention"` à la section `# entities` de `__all__`.

  **Étape E — Écrire les tests (TDD).** Ouvrir `tests/unit/domain/test_entities.py`. En haut du fichier, mettre à jour les imports depuis `vidscope.domain` pour inclure `Hashtag` et `Mention` (vérifier aussi la présence de `VideoId`, `Platform`, `PlatformId`, `FrozenInstanceError`). À la fin du fichier, ajouter DEUX nouvelles classes de tests + étendre `TestVideo` existant :

  ```python
  class TestVideoMetadataColumns:
      """M007 D-01: description, music_track, music_artist on Video."""

      def _minimal(self) -> Video:
          return Video(
              platform=Platform.YOUTUBE,
              platform_id=PlatformId("abc"),
              url="https://youtube.com/watch?v=abc",
          )

      def test_metadata_defaults_are_none(self) -> None:
          v = self._minimal()
          assert v.description is None
          assert v.music_track is None
          assert v.music_artist is None

      def test_metadata_round_trip(self) -> None:
          v = Video(
              platform=Platform.TIKTOK,
              platform_id=PlatformId("t123"),
              url="https://tiktok.com/@x/video/t123",
              description="#Cooking at home @alice https://shop.com",
              music_track="Original sound",
              music_artist="@creator",
          )
          assert v.description == "#Cooking at home @alice https://shop.com"
          assert v.music_track == "Original sound"
          assert v.music_artist == "@creator"

      def test_description_is_frozen(self) -> None:
          v = self._minimal()
          with pytest.raises(FrozenInstanceError):
              v.description = "mutate"  # type: ignore[misc]


  class TestHashtag:
      def _minimal(self) -> Hashtag:
          return Hashtag(video_id=VideoId(1), tag="coding")

      def test_minimal_hashtag_has_defaults(self) -> None:
          h = self._minimal()
          assert h.video_id == VideoId(1)
          assert h.tag == "coding"
          assert h.id is None
          assert h.created_at is None

      def test_hashtag_preserves_caller_value_verbatim(self) -> None:
          # Canonicalisation (lowercase + strip #) is the adapter's job;
          # the dataclass stores what the caller passed.
          h = Hashtag(video_id=VideoId(1), tag="#Coding")
          assert h.tag == "#Coding"

      def test_hashtag_is_frozen(self) -> None:
          h = self._minimal()
          with pytest.raises(FrozenInstanceError):
              h.tag = "other"  # type: ignore[misc]

      def test_hashtag_uses_slots(self) -> None:
          h = self._minimal()
          assert not hasattr(h, "__dict__")

      def test_hashtag_equality_by_fields(self) -> None:
          a = Hashtag(video_id=VideoId(1), tag="coding")
          b = Hashtag(video_id=VideoId(1), tag="coding")
          assert a == b


  class TestMention:
      def _minimal(self) -> Mention:
          return Mention(video_id=VideoId(1), handle="alice")

      def test_minimal_mention_has_defaults(self) -> None:
          m = self._minimal()
          assert m.video_id == VideoId(1)
          assert m.handle == "alice"
          assert m.platform is None
          assert m.id is None
          assert m.created_at is None

      def test_mention_accepts_optional_platform(self) -> None:
          m = Mention(
              video_id=VideoId(1),
              handle="alice",
              platform=Platform.TIKTOK,
          )
          assert m.platform is Platform.TIKTOK

      def test_mention_is_frozen(self) -> None:
          m = self._minimal()
          with pytest.raises(FrozenInstanceError):
              m.handle = "other"  # type: ignore[misc]

      def test_mention_uses_slots(self) -> None:
          m = self._minimal()
          assert not hasattr(m, "__dict__")

      def test_mention_equality_by_fields(self) -> None:
          a = Mention(video_id=VideoId(1), handle="alice", platform=Platform.TIKTOK)
          b = Mention(video_id=VideoId(1), handle="alice", platform=Platform.TIKTOK)
          assert a == b
  ```

  Respecter la convention française/anglaise du projet : code et identifiants en anglais, commentaires/docstrings en anglais ici car le reste du fichier est anglais. Vérifier l'import `from dataclasses import FrozenInstanceError` est déjà présent (ajouter sinon).
  </action>

  <acceptance_criteria>
    - `grep -q "description: str | None = None" src/vidscope/domain/entities.py` exit 0
    - `grep -q "music_track: str | None = None" src/vidscope/domain/entities.py` exit 0
    - `grep -q "music_artist: str | None = None" src/vidscope/domain/entities.py` exit 0
    - `grep -q "class Hashtag:" src/vidscope/domain/entities.py` exit 0
    - `grep -q "class Mention:" src/vidscope/domain/entities.py` exit 0
    - `grep -q '"Hashtag"' src/vidscope/domain/entities.py` exit 0 (dans `__all__`)
    - `grep -q '"Mention"' src/vidscope/domain/entities.py` exit 0 (dans `__all__`)
    - `grep -q '"Hashtag"' src/vidscope/domain/__init__.py` exit 0
    - `grep -q '"Mention"' src/vidscope/domain/__init__.py` exit 0
    - `python -m uv run python -c "from vidscope.domain import Hashtag, Mention, Video, VideoId, Platform, PlatformId; v = Video(platform=Platform.YOUTUBE, platform_id=PlatformId('x'), url='u', description='d', music_track='t', music_artist='a'); print(v.description, v.music_track, v.music_artist)"` affiche `d t a`
    - `python -m uv run python -c "from vidscope.domain import Hashtag, VideoId; h = Hashtag(video_id=VideoId(1), tag='coding'); print(h.tag, h.id)"` affiche `coding None`
    - `python -m uv run python -c "from vidscope.domain import Mention, VideoId, Platform; m = Mention(video_id=VideoId(1), handle='alice', platform=Platform.TIKTOK); print(m.handle, m.platform.value)"` affiche `alice tiktok`
    - `python -m uv run pytest tests/unit/domain/test_entities.py::TestVideoMetadataColumns -x -q` exit 0
    - `python -m uv run pytest tests/unit/domain/test_entities.py::TestHashtag -x -q` exit 0
    - `python -m uv run pytest tests/unit/domain/test_entities.py::TestMention -x -q` exit 0
    - `python -m uv run pytest tests/unit/domain -q` exit 0 (aucune régression sur les tests Video/Creator existants)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (9 contrats verts, `domain-is-pure` inclus)
    - `python -m uv run ruff check src tests` exit 0
  </acceptance_criteria>
</task>

## Verification Criteria

Commandes exécutables qui prouvent la complétion de S01-P01 (ordre : plus spécifique → plus large) :

```bash
# Tests par classe
python -m uv run pytest tests/unit/domain/test_entities.py::TestVideoMetadataColumns -x -q
python -m uv run pytest tests/unit/domain/test_entities.py::TestHashtag -x -q
python -m uv run pytest tests/unit/domain/test_entities.py::TestMention -x -q

# Vérifier que StageName a bien 6 membres dans l'ordre canonique
python -m uv run python -c "from vidscope.domain import StageName; assert [s.value for s in StageName] == ['ingest','transcribe','frames','analyze','metadata_extract','index']"

# Suite complète (aucune régression)
python -m uv run pytest -q

# Quality gates (les 4 portes du projet)
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

Les 9 contrats import-linter restent verts — ce plan n'introduit que des additions dans `vidscope.domain`, stdlib-only.

## Must-Haves

Garanties concrètes livrées par S01-P01 :

- `Video` dataclass dans `vidscope.domain.entities` carry 3 nouveaux champs optionnels `description: str | None = None`, `music_track: str | None = None`, `music_artist: str | None = None` (per D-01). Aucun `VideoMetadata` side entity créé.
- `Hashtag` frozen dataclass avec `slots=True` existe dans `vidscope.domain.entities` avec les champs `video_id: VideoId`, `tag: str`, `id: int | None = None`, `created_at: datetime | None = None`. La canonicalisation est documentée comme responsabilité de l'adapter.
- `Mention` frozen dataclass avec `slots=True` existe avec `video_id: VideoId`, `handle: str`, `platform: Platform | None = None` (per D-03 — pas de `creator_id` FK), `id: int | None = None`, `created_at: datetime | None = None`.
- `StageName.METADATA_EXTRACT = "metadata_extract"` existe dans `vidscope.domain.values` entre `ANALYZE` et `INDEX` (ordre canonique d'exécution).
- `vidscope.domain.__init__` re-exporte `Hashtag` et `Mention` pour que S01-P02 + S03 puissent `from vidscope.domain import Hashtag, Mention`.
- Les tests unitaires couvrent frozen + slots + defaults + round-trip complet pour les 3 extensions (Video metadata columns, Hashtag, Mention).
- Les 9 contrats `.importlinter` restent verts (stdlib-only).
- Aucun blocker pour S01-P02 (SQL schema + repositories) ni pour S03 (wire `MetadataExtractStage` en utilisant `StageName.METADATA_EXTRACT`).

## Threat Model

Surface de menace de S01-P01 (fondations pures, pas d'I/O) :

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S01P01-01 | **Tampering (T)** | `Hashtag`, `Mention`, `Video` (nouveaux champs) | LOW | mitigate | `frozen=True` empêche la mutation runtime. Tests `test_*_is_frozen` vérifient que `FrozenInstanceError` est levée. Couvre les accidents dev, pas un attaquant avec `object.__setattr__`. |
| T-S01P01-02 | **Information Disclosure (I)** | `Video.description`, `music_track`, `music_artist` | LOW | accept | Les champs ne portent que les données que la plateforme expose publiquement (description = caption verbatim, champs musique = yt-dlp `track`/`artists`). Aucune PII sensible au-delà de ce qui est déjà public sur TikTok/YouTube/Instagram. Stockage local single-user (R032). |
| T-S01P01-03 | **Injection (T via T)** | `Hashtag.tag`, `Mention.handle` (construit avec user-controlled input côté caller) | LOW | accept | À ce stade le dataclass stocke un `str` opaque. Le risque réel (SQL injection) se matérialise au niveau adapter (SQLAlchemy Core avec paramétrage bindé ⇒ injection impossible — voir modèle de menace S01-P02). |
| T-S01P01-04 | **Denial of Service (D)** | `StageName` enum extension | NONE | accept | Aucun chemin d'exécution ajouté. Un nom inconnu dans `pipeline_runs.phase` existant ne casse rien car la colonne est TEXT (voir RESEARCH.md §Risk 1). |

Aucune menace majeure à ce stade : S01-P01 n'ajoute que des structures de données pures, sans chemin d'I/O, sans parsing, sans surface réseau. Les menaces réelles (injection SQL via hashtag canonicalisation, DoS via regex catastrophic backtracking sur description) apparaissent dans S01-P02 (adaptateur SQL) et S02 (RegexLinkExtractor). Elles sont modélisées dans les plans correspondants.
