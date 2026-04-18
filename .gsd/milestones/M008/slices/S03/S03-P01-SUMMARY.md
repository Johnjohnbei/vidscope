---
phase: M008/S03
plan: P01
subsystem: pipeline-stages-domain-repository
tags: [ocr, vision, face-counter, thumbnail, content-shape, sqlite, pipeline, classification]
dependency_graph:
  requires:
    - vidscope.ports.ocr_engine.FaceCounter (S01-P01)
    - vidscope.adapters.vision.HaarcascadeFaceCounter (S01-P01)
    - vidscope.domain.values.ContentShape (S01-P01)
    - vidscope.pipeline.stages.VisualIntelligenceStage (S02-P01)
    - vidscope.ports.repositories.VideoRepository (prior milestones)
    - videos.thumbnail_key + videos.content_shape SQLite columns (S01-P01 schema)
  provides:
    - classify_content_shape() helper (40% threshold heuristic, UNKNOWN/BROLL/TALKING_HEAD/MIXED)
    - Video.thumbnail_key + Video.content_shape entity fields
    - VideoRepository.update_visual_metadata() Protocol + SQLite implementation
    - VisualIntelligenceStage extended: thumbnail copy (R048) + face-count classification (R049)
    - is_satisfied compound check (frame_texts AND thumbnail_key AND content_shape)
    - HaarcascadeFaceCounter wired in build_container()
  affects:
    - src/vidscope/pipeline/stages/visual_intelligence.py (breaking: face_counter param added)
    - src/vidscope/infrastructure/container.py (HaarcascadeFaceCounter wired)
    - Any caller of VisualIntelligenceStage must now pass face_counter
tech_stack:
  added: []
  patterns:
    - Single-pass frame iteration (OCR + face-count in one loop, same JPGs)
    - classify_content_shape helper (pure function, testable in isolation)
    - update_visual_metadata targeted UPDATE (no wide row-rewrite)
    - Compound is_satisfied (all three: frame_texts + thumbnail_key + content_shape)
    - Defensive path-traversal check on platform_id before thumbnail store (T-M008-S03-01)
    - Empty-string thumbnail guard (T-M008-S03-06)
key_files:
  created: []
  modified:
    - src/vidscope/domain/entities.py (thumbnail_key + content_shape fields on Video)
    - src/vidscope/pipeline/stages/visual_intelligence.py (classify_content_shape + extended stage)
    - src/vidscope/ports/repositories.py (update_visual_metadata on VideoRepository Protocol)
    - src/vidscope/adapters/sqlite/video_repository.py (update_visual_metadata impl + _row_to_video)
    - src/vidscope/infrastructure/container.py (HaarcascadeFaceCounter wired)
    - tests/unit/domain/test_entities.py (TestVideoVisualMetadata)
    - tests/unit/pipeline/stages/test_visual_intelligence.py (TestClassifyContentShape + TestThumbnail + TestContentShape + TestCompoundIsSatisfied)
    - tests/unit/adapters/sqlite/test_video_repository.py (TestUpdateVisualMetadata)
    - tests/integration/pipeline/test_visual_intelligence_stage.py (TestVisualIntelligenceIntegrationS03)
key-decisions:
  - "D-M008-S03-01: Single-pass frame iteration — OCR + face-count in one loop to avoid reading JPGs twice (perf target <20s, face-count is ~10x faster than OCR)"
  - "D-M008-S03-02: classify_content_shape as module-level pure function — testable in isolation, imported by execute(); mirrors classify_* helper pattern"
  - "D-M008-S03-03: update_visual_metadata as targeted UPDATE (not full row-rewrite) — preserves all other columns, matches upsert style for minimal risk"
  - "D-M008-S03-04: is_satisfied compound check breaks backward compat with S02-P01 TestIsSatisfied::test_returns_true_when_frame_texts_exist — updated test to new semantics"
requirements-completed: [R048, R049]
duration: 8min
completed: "2026-04-18"
---

# Phase M008 Slice S03 Plan P01 Summary

**VisualIntelligenceStage étendu avec copie de la thumbnail canonique (R048) et classification content_shape par face-count heuristique 40% (R049) — VideoRepository.update_visual_metadata, Video entity fields, classify_content_shape helper, HaarcascadeFaceCounter câblé dans le container.**

## Performance

- **Duration:** ~8 minutes
- **Started:** 2026-04-18T14:08:50Z
- **Completed:** 2026-04-18T14:16:30Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- `classify_content_shape(face_counts)` helper — règle 40% : UNKNOWN/BROLL/TALKING_HEAD/MIXED
- `Video.thumbnail_key` et `Video.content_shape` ajoutés comme champs `str | None = None`
- `VideoRepository.update_visual_metadata()` Protocol + implémentation SQLite (targeted UPDATE, raises StorageError on miss)
- `VisualIntelligenceStage` étendu : une seule passe sur les frames (OCR + face-count), copie du frame du milieu (index N//2), mise à jour visuelle via `update_visual_metadata`
- `is_satisfied` compound : frame_texts ET thumbnail_key ET content_shape tous présents
- `HaarcascadeFaceCounter` instancié et injecté dans `build_container()`
- 27 nouveaux tests (13 unit + 14 unit stage + 2 integration S03)

## Task Commits

1. **T01: classify_content_shape + Video fields + update_visual_metadata** - `55c85cc` (feat)
2. **T02: Extend VisualIntelligenceStage + compound is_satisfied** - `b877f59` (feat)
3. **T03: Wire HaarcascadeFaceCounter + integration tests** - `9fa5d16` (feat)

## Files Created/Modified

- `src/vidscope/domain/entities.py` — thumbnail_key + content_shape sur Video dataclass
- `src/vidscope/pipeline/stages/visual_intelligence.py` — classify_content_shape helper + FaceCounter DI + thumbnail copy R048 + face-count R049 + compound is_satisfied
- `src/vidscope/ports/repositories.py` — update_visual_metadata sur VideoRepository Protocol
- `src/vidscope/adapters/sqlite/video_repository.py` — update_visual_metadata impl + _row_to_video lit les deux nouvelles colonnes
- `src/vidscope/infrastructure/container.py` — HaarcascadeFaceCounter instancié et passé à VisualIntelligenceStage
- `tests/unit/domain/test_entities.py` — TestVideoVisualMetadata (3 tests)
- `tests/unit/pipeline/stages/test_visual_intelligence.py` — TestClassifyContentShape (7), TestThumbnail (5), TestContentShape (5), TestCompoundIsSatisfied (3), mise à jour TestIsSatisfied
- `tests/unit/adapters/sqlite/test_video_repository.py` — TestUpdateVisualMetadata (3 tests)
- `tests/integration/pipeline/test_visual_intelligence_stage.py` — TestVisualIntelligenceIntegrationS03 (2 tests) + fix des tests S02 existants

## Decisions Made

- Single-pass frame iteration (OCR + face-count dans la même boucle) pour éviter 2 lectures disque par frame — cohérent avec l'objectif perf <20s.
- `classify_content_shape` comme fonction module-level (pas méthode de la stage) — testable en isolation, importée dans execute().
- `update_visual_metadata` UPDATE ciblé (2 colonnes seulement), pas re-write complet de la row.
- `is_satisfied` compound brise la sémantique S02 (was: frame_texts seulement) → mis à jour avec guards defensifs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TestIsSatisfied::test_returns_true_when_frame_texts_exist incompatible avec le nouveau is_satisfied compound**
- **Found during:** T02 GREEN phase
- **Issue:** Le test S02 vérifiait que `is_satisfied` retourne True dès que des frame_texts existent. Avec le compound check (qui requiert aussi thumbnail_key + content_shape), ce test échouait.
- **Fix:** Renommé en `test_returns_true_when_all_outputs_present`, mise à jour pour appeler `update_visual_metadata` et peupler les deux colonnes. Ajout de `test_returns_false_when_frame_texts_exist_but_thumbnail_missing` pour documenter explicitement le nouveau comportement.
- **Files modified:** `tests/unit/pipeline/stages/test_visual_intelligence.py`
- **Commit:** b877f59 (inclus dans T02)

**2. [Rule 1 - Bug] TestExecuteMediaResolutionErrors crée VisualIntelligenceStage sans face_counter + _FakeUoW sans videos**
- **Found during:** T02 implémentation — le constructeur du stage exige maintenant face_counter
- **Issue:** Ce test crée le stage directement (pas via `_stage()`), sans passer face_counter ni videos dans _FakeUoW.
- **Fix:** Ajout de `face_counter=_FakeFaceCounter()`, `videos=_FakeVideoRepo()`, seed video[1], et méthode `store()` sur `_BrokenStorage`.
- **Files modified:** `tests/unit/pipeline/stages/test_visual_intelligence.py`
- **Commit:** b877f59

**3. [Rule 1 - Bug] Integration tests S02 incompatibles avec nouveau constructeur + _LocalMediaStorage sans store()**
- **Found during:** T03 après wiring container — les 2 tests existants échouaient car face_counter manquant et store() absent
- **Fix:** Ajout de `store()` à `_LocalMediaStorage` (vraie copie shutil), passage de `face_counter=_StubFaceCounter()` à chaque création de stage, ajout de `ctx.platform_id` au ctx de `test_is_satisfied_after_execute`, création des fichiers frames sur disque pour que store() fonctionne.
- **Files modified:** `tests/integration/pipeline/test_visual_intelligence_stage.py`
- **Commit:** 9fa5d16

---

**Total deviations:** 3 auto-fixed (tous Rule 1 - backward compat après extension d'interface)
**Impact on plan:** Toutes les corrections nécessaires pour maintenir la suite de tests verte. Aucun scope creep.

## Known Stubs

Aucun — toute la fonctionnalité est câblée. `HaarcascadeFaceCounter` retourne 0 si opencv n'est pas installé (lazy-load) — comportement documenté et testé (résultat BROLL/UNKNOWN selon les frames disponibles).

## Threat Flags

Aucun nouveau flag non couvert par le threat model du plan. Les mitigations T-M008-S03-01 (path-traversal) et T-M008-S03-06 (empty-string thumbnail) sont implémentées dans execute().

## Self-Check: PASSED

Fichiers vérifiés :
- `src/vidscope/domain/entities.py` (thumbnail_key, content_shape) — FOUND
- `src/vidscope/pipeline/stages/visual_intelligence.py` (classify_content_shape, update_visual_metadata, face_counter) — FOUND
- `src/vidscope/ports/repositories.py` (update_visual_metadata) — FOUND
- `src/vidscope/adapters/sqlite/video_repository.py` (update_visual_metadata, _row_to_video) — FOUND
- `src/vidscope/infrastructure/container.py` (HaarcascadeFaceCounter, face_counter=face_counter) — FOUND

Commits vérifiés :
- 55c85cc T01 — FOUND
- b877f59 T02 — FOUND
- 9fa5d16 T03 — FOUND

Tests : 1036 passed, 9 deselected
mypy : Success: no issues found in 105 source files
import-linter : Contracts: 11 kept, 0 broken
