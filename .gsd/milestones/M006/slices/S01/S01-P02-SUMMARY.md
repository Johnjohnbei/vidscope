---
plan_id: S01-P02
phase: M006/S01
subsystem: ports + schema
tags: [protocol, repository, schema, sqlite, migration, creator, fk, index]
requirements: [R040, R041, R042]

dependency_graph:
  requires:
    - S01-P01 (Creator, CreatorId, PlatformUserId domain types)
  provides:
    - vidscope.ports.CreatorRepository (Protocol, 7 méthodes)
    - adapters/sqlite/schema.py::creators (Table SQLAlchemy Core)
    - adapters/sqlite/schema.py::videos.creator_id (FK nullable SET NULL)
    - adapters/sqlite/schema.py::_ensure_videos_creator_id (ALTER idempotent)
  affects:
    - S01-P03 (SqlCreatorRepository peut implémenter le Protocol contre la Table)
    - S01-P04 (UoW ajoute uow.creators slot)

tech_stack:
  added: []
  patterns:
    - Protocol @runtime_checkable appendé dans le fichier registry existant (ports/repositories.py)
    - SQLAlchemy Core Table + UniqueConstraint + Index
    - Helper idempotent _ensure_videos_creator_id (PRAGMA table_info + conditional ALTER)
    - raw SQL INSERTs dans les tests incluant created_at=CURRENT_TIMESTAMP (pattern établi)

key_files:
  created:
    - (aucun nouveau fichier)
  modified:
    - src/vidscope/ports/repositories.py
    - src/vidscope/ports/__init__.py
    - src/vidscope/adapters/sqlite/schema.py
    - tests/unit/adapters/sqlite/test_schema.py

decisions:
  - "CreatorRepository appendé dans ports/repositories.py — convention projet : un seul fichier registry pour tous les Protocols (7 existants + 1 nouveau)"
  - "videos.creator_id déclaré inline dans la Table pour les fresh installs + _ensure_videos_creator_id pour les DB M001–M005 existantes via ALTER conditionnel"
  - "INSERTs raw SQL dans les tests incluent created_at=CURRENT_TIMESTAMP car SQLAlchemy Python-side defaults ne s'appliquent pas aux text() statements"
  - "FK ON DELETE SET NULL (pas CASCADE) : supprimer un créateur ne supprime pas ses vidéos — D-02"

metrics:
  duration_seconds: 420
  completed_at: "2026-04-17T14:30:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 4
---

# Phase M006 Plan S01-P02: CreatorRepository Protocol + Schema — Summary

**One-liner:** `CreatorRepository` Protocol (7 méthodes) appendé dans le registre ports existant + table `creators` SQLAlchemy Core avec UNIQUE `(platform, platform_user_id)`, FK `videos.creator_id SET NULL`, et helper ALTER idempotent pour la migration M001–M005.

## Tasks Completed

| # | Tâche | Commit | Fichiers clés |
|---|-------|--------|---------------|
| T05 | Append CreatorRepository Protocol à ports/repositories.py | `9800b7d` | `ports/repositories.py`, `ports/__init__.py` |
| T06 | Étendre schema.py : table creators + videos.creator_id + ALTER idempotent | `9fa873f` | `adapters/sqlite/schema.py` |
| T07 | Tests schéma : TestCreatorsSchema + TestVideosCreatorIdAlter | `4b3bc2a` | `tests/unit/adapters/sqlite/test_schema.py` |

## Verification Results

```
pytest tests/unit/adapters/sqlite/test_schema.py::TestCreatorsSchema -x -q   → 7 passed
pytest tests/unit/adapters/sqlite/test_schema.py::TestVideosCreatorIdAlter -x -q → 3 passed
pytest tests/unit/adapters/sqlite/test_schema.py -x -q                       → 14 passed
pytest -q (suite complète)                                                    → 641 passed, 5 deselected
ruff check src tests                                                          → All checks passed!
mypy src                                                                      → Success: no issues found in 84 source files
lint-imports                                                                  → Contracts: 9 kept, 0 broken
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] INSERTs raw SQL échouaient sur NOT NULL creators.created_at**
- **Found during:** T07 — première exécution des tests
- **Issue:** Les INSERTs SQL bruts dans les tests ne fournissaient pas `created_at`. Le `default=_utc_now` de SQLAlchemy est un default Python-side (appliqué par le Core lors d'un `INSERT` via SQLAlchemy) mais pas un SQL-level `DEFAULT` dans le DDL — SQLite applique donc la contrainte NOT NULL et lève `IntegrityError`.
- **Fix:** Ajout de `created_at=CURRENT_TIMESTAMP` dans tous les INSERTs raw SQL des tests (`creators` et `videos`). Le même problème existait déjà pour `videos` mais ne se manifestait pas dans les tests existants (qui utilisaient le Core via les adapters, pas du SQL brut).
- **Files modified:** `tests/unit/adapters/sqlite/test_schema.py`
- **Commit:** `4b3bc2a` (inclus dans le commit T07)

## Known Stubs

None. Le Protocol `CreatorRepository` est complet (7 méthodes avec docstrings). La table `creators` est complète (13 colonnes, UNIQUE, indexes). Aucune valeur hardcodée vide ne remonte vers l'UI.

## Threat Flags

None. P02 ne livre que des structures de données (Protocol + DDL). Aucune surface réseau ni entrée utilisateur parsée. Les menaces T-P02-01..T-P02-04 du plan sont toutes mitigées par les implémentations livrées (helper idempotent testé, FK SET NULL testé, pas de logs du schéma).

## Self-Check: PASSED

| Vérification | Résultat |
|---|---|
| `ports/repositories.py` contient `class CreatorRepository(Protocol):` | FOUND |
| `ports/__init__.py` exporte `CreatorRepository` | FOUND |
| Aucun fichier `ports/creator_repository.py` créé | CONFIRMED (convention respectée) |
| `schema.py` contient `creators = Table(` | FOUND |
| `schema.py` contient `_ensure_videos_creator_id` | FOUND |
| `schema.py` contient `ForeignKey("creators.id", ondelete="SET NULL")` | FOUND |
| `schema.py` contient `"creators"` dans `__all__` | FOUND |
| Commits T05..T07 présents | FOUND (`9800b7d`, `9fa873f`, `4b3bc2a`) |
| `pytest -q` 641 passed | PASSED |
| `ruff check src tests` | PASSED |
| `mypy src` 84 fichiers | PASSED |
| `lint-imports` 9 contrats | PASSED (9 kept, 0 broken) |
