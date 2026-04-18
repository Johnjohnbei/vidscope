---
plan_id: S01-P01
phase: M007/S01
subsystem: domain
tags: [domain, entities, values, tdd, m007]
requirements: [R043, R045]

dependency_graph:
  requires: []
  provides:
    - vidscope.domain.Video.description
    - vidscope.domain.Video.music_track
    - vidscope.domain.Video.music_artist
    - vidscope.domain.Hashtag
    - vidscope.domain.Mention
    - vidscope.domain.StageName.METADATA_EXTRACT
  affects:
    - S01-P02 (SQLite adapters — can now import Hashtag/Mention from domain)
    - S03-P01 (MetadataExtractStage — can use StageName.METADATA_EXTRACT)

tech_stack:
  added: []
  patterns:
    - frozen dataclass with slots=True (mirroring Creator pattern)
    - TDD RED → GREEN → verify cycle
    - additive domain extension (no breaking changes)

key_files:
  modified:
    - src/vidscope/domain/values.py
    - src/vidscope/domain/entities.py
    - src/vidscope/domain/__init__.py
    - tests/unit/domain/test_entities.py
    - tests/unit/domain/test_values.py

decisions:
  - D-01: description/music_track/music_artist as direct columns on Video (no VideoMetadata side entity)
  - D-03: Mention stores handle+platform(optional), no creator_id FK (deferred to M011)
  - Canonicalisation (lowercase/lstrip) is adapter responsibility, not dataclass

metrics:
  duration: ~15 min
  completed: 2026-04-18
  tasks_completed: 2
  files_modified: 5
---

# Phase M007 Plan S01-P01: Domain Foundations Summary

**One-liner:** Frozen dataclasses `Hashtag` and `Mention` + 3 metadata columns on `Video` + `StageName.METADATA_EXTRACT` added to domain layer, stdlib-only, 9 import-linter contracts green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T01 | Ajouter StageName.METADATA_EXTRACT | `dbf945c` | `src/vidscope/domain/values.py` |
| T02 (RED) | Tests TDD failing pour Video/Hashtag/Mention | `f59ecca` | `tests/unit/domain/test_entities.py` |
| T02 (GREEN) | Implémenter Video extension + Hashtag + Mention | `19daf5f` | `src/vidscope/domain/entities.py`, `src/vidscope/domain/__init__.py`, `tests/unit/domain/test_values.py` |

## What Was Built

**T01 — StageName.METADATA_EXTRACT**

`StageName` StrEnum étendu de 5 à 6 membres, avec `METADATA_EXTRACT = "metadata_extract"` inséré entre `ANALYZE` et `INDEX` pour respecter l'ordre canonique d'exécution : `ingest → transcribe → frames → analyze → metadata_extract → index`. Ce membre est requis par S03 pour wirer `MetadataExtractStage` sans déclencher `StageCrashError` dans `_resolve_stage_phase()`.

**T02 — Video extension + Hashtag + Mention**

- `Video` dataclass étendue avec 3 champs optionnels en fin de liste (après `creator_id`) : `description: str | None`, `music_track: str | None`, `music_artist: str | None`. Docstring mis à jour pour documenter la décision D-01 (zéro JOIN — colonnes directes sur la table `videos`).
- `Hashtag` frozen dataclass avec `slots=True` : `video_id: VideoId`, `tag: str`, `id: int | None = None`, `created_at: datetime | None = None`. La canonicalisation (`tag.lower().lstrip("#")`) est documentée comme responsabilité de l'adapter.
- `Mention` frozen dataclass avec `slots=True` : `video_id: VideoId`, `handle: str`, `platform: Platform | None = None`, `id: int | None = None`, `created_at: datetime | None = None`. Pas de `creator_id` FK (D-03 — déféré M011).
- `domain/entities.py __all__` mis à jour avec `"Hashtag"` et `"Mention"`.
- `domain/__init__.py` re-exporte `Hashtag` et `Mention` pour S01-P02 et S03.

**13 nouveaux tests** couvrant defaults, round-trip, frozen (FrozenInstanceError), slots (`__dict__` absent), et égalité par champs.

## Verification Results

```
python -m uv run pytest tests/unit/domain -q           → 117 passed
python -m uv run pytest -q                             → 748 passed, 5 deselected
python -m uv run mypy src                              → Success: no issues (89 files)
python -m uv run lint-imports                          → 9 kept, 0 broken
StageName order assertion                              → OK: 6 stages in canonical order
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fix test_execution_order_is_declaration_order in test_values.py**
- **Found during:** T02 GREEN verification
- **Issue:** `TestStageName::test_execution_order_is_declaration_order` listait 5 membres (`[INGEST, TRANSCRIBE, FRAMES, ANALYZE, INDEX]`) — cassé par l'ajout de METADATA_EXTRACT en T01.
- **Fix:** Mise à jour de la liste attendue pour inclure `StageName.METADATA_EXTRACT` entre `ANALYZE` et `INDEX`.
- **Files modified:** `tests/unit/domain/test_values.py`
- **Commit:** inclus dans `19daf5f`

### Pre-existing Issues (Out of Scope)

4 erreurs ruff pré-existantes dans `tests/unit/application/` (F401 unused import + 3x E501 line too long) — non liées aux modifications S01-P01. Documentées pour correction future.

## Known Stubs

Aucun stub — toutes les entités sont des dataclasses pures sans placeholder.

## Threat Flags

Aucune nouvelle surface réseau, endpoint, ou chemin d'auth introduit. S01-P01 est 100% stdlib-only, aucune I/O.

## Self-Check

- [x] `src/vidscope/domain/values.py` — FOUND
- [x] `src/vidscope/domain/entities.py` — FOUND
- [x] `src/vidscope/domain/__init__.py` — FOUND
- [x] `tests/unit/domain/test_entities.py` — FOUND
- [x] `tests/unit/domain/test_values.py` — FOUND
- [x] Commit `dbf945c` — FOUND
- [x] Commit `f59ecca` — FOUND
- [x] Commit `19daf5f` — FOUND

## Self-Check: PASSED
