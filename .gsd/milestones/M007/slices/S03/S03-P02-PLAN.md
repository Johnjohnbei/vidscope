---
plan_id: S03-P02
phase: M007/S03
wave: 6
depends_on: [S02-P02, S03-P01]
requirements: [R044]
files_modified:
  - src/vidscope/pipeline/stages/metadata_extract.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/pipeline/test_metadata_extract_stage.py
  - tests/unit/infrastructure/test_container.py
autonomous: true
---

## Objective

Créer le nouveau stage pipeline `MetadataExtractStage` et le wire dans le container : (1) `MetadataExtractStage` implémente `Stage` Protocol, utilise un `LinkExtractor` injecté (par DI, le container passe un `RegexLinkExtractor`), extrait les URLs depuis `video.description` (source="description") et depuis `transcript.full_text` (source="transcript"), persiste via `uow.links.add_many_for_video` ; `is_satisfied` retourne `True` si `uow.links.has_any_for_video(ctx.video_id)` (resume-safe) (2) le container instancie `RegexLinkExtractor` + `MetadataExtractStage` et l'insère dans le pipeline ENTRE `analyze_stage` et `index_stage` (3) tests unitaires couvrant is_satisfied + execute (description-only, transcript-only, both, empty) + le container wire les 6 stages dans l'ordre canonique.

## Tasks

<task id="T01-metadata-extract-stage" tdd="true">
  <name>Créer MetadataExtractStage + tests unitaires</name>

  <read_first>
    - `src/vidscope/pipeline/stages/transcribe.py` — patron Stage complet à miroir (is_satisfied + execute + typed error)
    - `src/vidscope/pipeline/stages/index.py` — patron Stage court (40 lignes) avec uow.transcripts + uow.analyses access — miroir pour notre lecture de transcript
    - `src/vidscope/ports/pipeline.py` lignes 119-149 — `Stage` Protocol contract
    - `src/vidscope/ports/link_extractor.py` — `LinkExtractor` Protocol et `RawLink` TypedDict (créés en S02-P01)
    - `src/vidscope/domain/errors.py` — `IndexingError`, `StageCrashError` existants ; pas besoin de nouveau type d'erreur pour ce stage (selon patron IndexStage qui utilise IndexingError pour ses errors)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"MetadataExtractStage — nouveau stage" et §"Ordre dans le pipeline"
    - `.gsd/milestones/M007/M007-CONTEXT.md` §"Après `TranscribeStage` — `MetadataExtractStage` nouveau lit transcript pour link extraction"
    - `src/vidscope/domain/values.py` — `StageName.METADATA_EXTRACT` (ajouté en S01-P01)
    - `src/vidscope/pipeline/stages/__init__.py` — à étendre pour exporter `MetadataExtractStage`
  </read_first>

  <behavior>
    - Test 1 (is_satisfied): `ctx.video_id=None` → retourne `False` (patron défensif).
    - Test 2 (is_satisfied): `uow.links.has_any_for_video(ctx.video_id)` retourne `True` → `is_satisfied` retourne `True` (resume-safe).
    - Test 3 (is_satisfied): `uow.links.has_any_for_video` retourne `False` → `is_satisfied` retourne `False`.
    - Test 4 (execute - description only): `video.description="visit https://shop.com"` + transcript vide → appelle `extractor.extract(video.description, source="description")`, persiste 1 Link via `uow.links.add_many_for_video`.
    - Test 5 (execute - transcript only): `video.description=None` + `transcript.full_text="check out https://docs.com"` → 1 Link avec `source="transcript"`.
    - Test 6 (execute - both): `video.description="https://a.com"` + `transcript.full_text="also https://b.com"` → 2 Link, un par source (description, transcript).
    - Test 7 (execute - both empty): `video.description=None`, transcript missing → `uow.links.add_many_for_video` appelé avec `[]` (no-op — OK) OU pas appelé du tout. **Choix : toujours appeler avec la liste (même vide) pour cohérence avec idempotence de `add_many_for_video([]) == []`**.
    - Test 8 (execute - missing video_id): `ctx.video_id=None` → lève `IndexingError` ou équivalent (patron IndexStage).
    - Test 9 (execute - missing video row): `uow.videos.get(ctx.video_id)` retourne `None` → `description=None` → extract sur `None` géré (extractor retourne `[]`).
    - Test 10 (execute - StageResult): retourne un `StageResult` avec `message` contenant le nombre de liens persistés.
  </behavior>

  <action>
  **Étape A — Créer `src/vidscope/pipeline/stages/metadata_extract.py`** :

  ```python
  """MetadataExtractStage — fifth stage of the pipeline (M007/S03).

  Extracts URLs from (description, transcript.full_text) via a
  :class:`LinkExtractor` port and persists them to the ``links`` side
  table via :attr:`UnitOfWork.links`. Positioned between
  :class:`AnalyzeStage` and :class:`IndexStage` in the canonical
  pipeline graph (see ``StageName`` enum order).

  Resume-from-failure
  -------------------
  ``is_satisfied`` returns True when ``uow.links.has_any_for_video(video_id)``
  is True — re-runs of ``vidscope add <url>`` on an already-extracted
  video skip this stage entirely.

  Idempotence caveat
  ------------------
  Unlike :class:`IngestStage` (hashtags/mentions use DELETE-INSERT),
  this stage does NOT clear existing links before inserting. The
  ``is_satisfied`` check ensures we don't double-insert in normal
  flow. If a user really wanted to re-run extraction (e.g. after a
  regex change), they'd manually DELETE the rows first. M007 is
  conservative here; M011 may revisit.
  """

  from __future__ import annotations

  from vidscope.domain import (
      IndexingError,
      Link,
      StageName,
  )
  from vidscope.ports import (
      PipelineContext,
      StageResult,
      UnitOfWork,
  )
  from vidscope.ports.link_extractor import LinkExtractor

  __all__ = ["MetadataExtractStage"]


  class MetadataExtractStage:
      """Fifth stage — extract URLs from description + transcript."""

      name: str = StageName.METADATA_EXTRACT.value

      def __init__(self, *, link_extractor: LinkExtractor) -> None:
          """Construct the stage.

          Parameters
          ----------
          link_extractor:
              Any :class:`LinkExtractor` implementation. Production uses
              :class:`~vidscope.adapters.text.RegexLinkExtractor`; tests
              inject fakes.
          """
          self._extractor = link_extractor

      # ------------------------------------------------------------------
      # Stage protocol
      # ------------------------------------------------------------------

      def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
          """Return True when at least one link already exists for
          ``ctx.video_id``. Cheap DB query — no regex re-run."""
          if ctx.video_id is None:
              return False
          return uow.links.has_any_for_video(ctx.video_id)

      def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
          """Extract URLs from description + transcript, persist them.

          Mutates nothing on ``ctx`` — downstream stages don't read the
          links list.

          Raises
          ------
          IndexingError
              When ``ctx.video_id`` is missing (ingest stage failed silently).
          """
          if ctx.video_id is None:
              raise IndexingError(
                  "metadata_extract stage requires ctx.video_id; "
                  "ingest must run first"
              )

          # 1. Read description from the videos row (M007 D-01: column).
          video = uow.videos.get(ctx.video_id)
          description = video.description if video is not None else None

          # 2. Read transcript (optional — may be None on transcription
          #    failure or instrumental video).
          transcript = uow.transcripts.get_for_video(ctx.video_id)
          transcript_text = (
              transcript.full_text
              if transcript is not None and transcript.full_text
              else None
          )

          # 3. Extract URLs from each source.
          links: list[Link] = []
          if description:
              for raw in self._extractor.extract(description, source="description"):
                  links.append(
                      Link(
                          video_id=ctx.video_id,
                          url=raw["url"],
                          normalized_url=raw["normalized_url"],
                          source=raw["source"],
                          position_ms=raw["position_ms"],
                      )
                  )
          if transcript_text:
              for raw in self._extractor.extract(transcript_text, source="transcript"):
                  links.append(
                      Link(
                          video_id=ctx.video_id,
                          url=raw["url"],
                          normalized_url=raw["normalized_url"],
                          source=raw["source"],
                          position_ms=raw["position_ms"],
                      )
                  )

          # 4. Persist. add_many_for_video dedupes by (normalized_url,
          #    source) within the call; empty list is a no-op.
          persisted = uow.links.add_many_for_video(ctx.video_id, links)

          return StageResult(
              message=f"extracted {len(persisted)} link(s) "
                      f"(description + transcript)"
          )
  ```

  **Étape B — Exporter depuis `src/vidscope/pipeline/stages/__init__.py`**. Localiser le fichier, ajouter l'import de `MetadataExtractStage` et l'ajouter à `__all__` dans l'ordre alphabétique.

  **Étape C — Tests**. Créer `tests/unit/pipeline/test_metadata_extract_stage.py` avec les 10 tests décrits dans `<behavior>`. Pattern : `FakeLinkExtractor` qui retourne des `RawLink` contrôlés par test ; `FakeUoW` avec `uow.videos.get`, `uow.transcripts.get_for_video`, `uow.links.has_any_for_video`, `uow.links.add_many_for_video` contrôlables (retourner des valeurs fixées, enregistrer les appels).
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/pipeline/stages/metadata_extract.py`
    - `grep -q "class MetadataExtractStage:" src/vidscope/pipeline/stages/metadata_extract.py` exit 0
    - `grep -q 'name: str = StageName.METADATA_EXTRACT.value' src/vidscope/pipeline/stages/metadata_extract.py` exit 0
    - `grep -q "def is_satisfied" src/vidscope/pipeline/stages/metadata_extract.py` exit 0
    - `grep -q "def execute" src/vidscope/pipeline/stages/metadata_extract.py` exit 0
    - `grep -q "uow.links.add_many_for_video" src/vidscope/pipeline/stages/metadata_extract.py` exit 0
    - `grep -q "MetadataExtractStage" src/vidscope/pipeline/stages/__init__.py` exit 0
    - `test -f tests/unit/pipeline/test_metadata_extract_stage.py`
    - `grep -c "def test_" tests/unit/pipeline/test_metadata_extract_stage.py` retourne un nombre ≥ 10
    - `python -m uv run pytest tests/unit/pipeline/test_metadata_extract_stage.py -x -q` exit 0
    - `python -m uv run python -c "from vidscope.pipeline.stages import MetadataExtractStage; from vidscope.adapters.text import RegexLinkExtractor; s = MetadataExtractStage(link_extractor=RegexLinkExtractor()); print(s.name)"` affiche `metadata_extract`
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (pipeline respecte `pipeline-has-no-adapters`)
  </acceptance_criteria>
</task>

<task id="T02-container-wire-stage">
  <name>Wire MetadataExtractStage dans build_container avec RegexLinkExtractor</name>

  <read_first>
    - `src/vidscope/infrastructure/container.py` lignes 54-72 (imports stages + ports) et lignes 202-230 (instantiation stages + PipelineRunner stages list)
    - `src/vidscope/adapters/text/__init__.py` (créé en S02-P02) — `RegexLinkExtractor` et `normalize_url` exports
    - `src/vidscope/pipeline/stages/__init__.py` — localise l'import existant de `IngestStage, TranscribeStage, FramesStage, AnalyzeStage, IndexStage` à étendre
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"runner.py / container.py — enregistrement"
    - `.importlinter` — `mcp-has-no-adapters` / `pipeline-has-no-adapters` : c'est `infrastructure` (composition root) qui peut importer les adapters, pas le pipeline
  </read_first>

  <action>
  Ouvrir `src/vidscope/infrastructure/container.py`. Effectuer 3 modifications :

  **Étape A — Étendre les imports stages** (lignes 54-62) :

  ```python
  from vidscope.pipeline.stages import (
      AnalyzeStage,
      FramesStage,
      IndexStage,
      IngestStage,
      MetadataExtractStage,
      TranscribeStage,
  )
  ```

  **Étape B — Ajouter l'import du `RegexLinkExtractor`** (après l'import de `YtdlpDownloader`, ligne 50) :

  ```python
  from vidscope.adapters.text import RegexLinkExtractor
  ```

  **Étape C — Instancier le stage et l'insérer dans la liste `stages=[...]`**. Dans `build_container()`, APRÈS `analyze_stage = AnalyzeStage(analyzer=analyzer)` (ligne 217) et AVANT `index_stage = IndexStage()` (ligne 218), ajouter :

  ```python
      link_extractor = RegexLinkExtractor()
      metadata_extract_stage = MetadataExtractStage(
          link_extractor=link_extractor,
      )
  ```

  Puis modifier la liste `stages=[...]` du `PipelineRunner(...)` (lignes 221-227) pour insérer `metadata_extract_stage` entre `analyze_stage` et `index_stage`, dans l'ORDRE CANONIQUE `StageName` :

  ```python
      pipeline_runner = PipelineRunner(
          stages=[
              ingest_stage,
              transcribe_stage,
              frames_stage,
              analyze_stage,
              metadata_extract_stage,
              index_stage,
          ],
          unit_of_work_factory=_uow_factory,
          clock=clock,
      )
  ```

  Aucune modification du `Container` dataclass — `link_extractor` reste une variable locale (pas besoin de l'exposer comme champ Container tant qu'aucun use case ne l'appelle hors du stage, ce qui est le cas en M007).
  </action>

  <acceptance_criteria>
    - `grep -q "from vidscope.adapters.text import RegexLinkExtractor" src/vidscope/infrastructure/container.py` exit 0
    - `grep -q "MetadataExtractStage" src/vidscope/infrastructure/container.py` exit 0
    - `grep -q "metadata_extract_stage = MetadataExtractStage" src/vidscope/infrastructure/container.py` exit 0
    - `grep -q "link_extractor = RegexLinkExtractor()" src/vidscope/infrastructure/container.py` exit 0
    - `python -m uv run python -c "
  from vidscope.infrastructure.container import build_container
  c = build_container()
  names = c.pipeline_runner.stage_names
  assert names == ('ingest', 'transcribe', 'frames', 'analyze', 'metadata_extract', 'index'), names
  print('OK stages:', names)
  "` affiche les 6 stages dans l'ordre canonique
    - `python -m uv run pytest tests/unit/infrastructure/test_container.py -x -q` exit 0 (tests existants passent ; ajouter ou étendre un test qui vérifie la présence de `metadata_extract` dans `stage_names` si le test existe)
    - `python -m uv run pytest -q` exit 0 (aucune régression)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (infrastructure est la composition root et peut importer `adapters.text` — aucun contrat violé)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests stage
python -m uv run pytest tests/unit/pipeline/test_metadata_extract_stage.py -x -q

# Smoke test : pipeline contient les 6 stages dans l'ordre canonique
python -m uv run python -c "
from vidscope.infrastructure.container import build_container
c = build_container()
assert c.pipeline_runner.stage_names == (
    'ingest', 'transcribe', 'frames', 'analyze', 'metadata_extract', 'index'
), c.pipeline_runner.stage_names
print('OK:', c.pipeline_runner.stage_names)
"

# Suite complète + quality gates
python -m uv run pytest -q
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

## Must-Haves

- Nouveau fichier `src/vidscope/pipeline/stages/metadata_extract.py` avec `MetadataExtractStage` class.
- `MetadataExtractStage.name = StageName.METADATA_EXTRACT.value == "metadata_extract"`.
- `MetadataExtractStage.__init__(link_extractor: LinkExtractor)` — DI du port.
- `is_satisfied` délègue à `uow.links.has_any_for_video(ctx.video_id)` (resume-safe, cheap DB query).
- `execute` lit `video.description` + `transcript.full_text` et appelle `extractor.extract(source="description"|"transcript")`, persiste via `uow.links.add_many_for_video`.
- `build_container()` instancie `RegexLinkExtractor()` et `MetadataExtractStage(link_extractor=link_extractor)`.
- Le `PipelineRunner` a 6 stages dans l'ordre canonique : `['ingest', 'transcribe', 'frames', 'analyze', 'metadata_extract', 'index']`.
- Tests ≥ 10 sur le stage.
- Les 10 contrats `.importlinter` restent verts.

## Threat Model

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S03P02-01 | **Denial of Service (D)** — transcript très long → regex ralenti | `MetadataExtractStage.execute` → `extractor.extract(transcript_text)` | MEDIUM | mitigate | Transcripts de shorts < 5000 chars en pratique ; regex linéaire non-catastrophic (cf. T-S02P02-01). Worst case borné : `finditer` sur 10k chars ≈ ms. Pas de chunking nécessaire en M007. |
| T-S03P02-02 | **Tampering (T)** — description/transcript contenant SQL-like strings | `uow.links.add_many_for_video` | LOW | mitigate | Bindings SQLAlchemy Core (cf. T-S02P01-01). |
| T-S03P02-03 | **Information Disclosure (I)** — liens transcript pouvant révéler URLs prononcées hors-caption | `links.url` + `source="transcript"` | LOW | accept | Le transcript est local et single-user (R032). Les URLs dans le transcript sont le résultat direct de la décision utilisateur d'ingérer une vidéo publique. Aucune divulgation nouvelle. |
| T-S03P02-04 | **Denial of Service (D)** — réexécution coûteuse lors re-runs | `is_satisfied` | LOW | mitigate | `has_any_for_video` est une query SQLite (`SELECT count(*) ... WHERE video_id=?`) indexée par `idx_links_video_id` → O(log n). Skip est instantané. |
| T-S03P02-05 | **Repudiation (R)** — pas de trace quelle regex version a extrait quelle URL | `links` table | LOW | accept | M007 ne stocke pas la version du regex. Si besoin à l'avenir, une colonne `extractor_version` pourrait être ajoutée. Acceptable pour outil perso. |
