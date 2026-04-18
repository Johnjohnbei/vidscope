---
plan_id: S03-P01
phase: M006/S03
plan: 01
subsystem: application
tags: [use-cases, creator, list, get, videos]
dependency_graph:
  requires:
    - M006/S01-P03  # CreatorRepositorySQLite + UoW wiring
    - M006/S01-P02  # CreatorRepository Protocol
    - M006/S02-P01  # CreatorInfo TypedDict dans ports
  provides:
    - GetCreatorUseCase           # consommé par S03-P02 (CLI) et S03-P03 (MCP)
    - ListCreatorsUseCase         # consommé par S03-P02 (CLI) et S03-P03 (MCP)
    - ListCreatorVideosUseCase    # consommé par S03-P02 (CLI) et S03-P03 (MCP)
    - VideoRepository.list_by_creator  # consommé par ListCreatorVideosUseCase
  affects:
    - src/vidscope/ports/repositories.py
    - src/vidscope/adapters/sqlite/video_repository.py
    - src/vidscope/application/__init__.py
tech_stack:
  added: []
  patterns:
    - frozen dataclass Result DTO (GetCreatorResult, ListCreatorsResult, ListCreatorVideosResult)
    - UnitOfWorkFactory constructor injection
    - dual-filter client-side (platform + min_followers combined en Python)
    - limit clamp [1,200] contre DoS (T-S03P01-02)
key_files:
  created:
    - src/vidscope/application/get_creator.py
    - src/vidscope/application/list_creators.py
    - src/vidscope/application/list_creator_videos.py
    - tests/unit/application/test_get_creator.py
    - tests/unit/application/test_list_creators.py
    - tests/unit/application/test_list_creator_videos.py
  modified:
    - src/vidscope/ports/repositories.py
    - src/vidscope/adapters/sqlite/video_repository.py
    - src/vidscope/application/__init__.py
decisions:
  - "Dual-filter (platform + min_followers) combiné en Python côté use case pour éviter une requête composée dans l'adapter"
  - "limit clampé à [1,200] dans ListCreatorsUseCase et ListCreatorVideosUseCase (T-S03P01-02)"
  - "total dans ListCreatorVideosResult obtenu via list_by_creator(limit=10000) — simple et correct pour les volumes attendus"
  - "Tri no-filter dans ListCreatorsUseCase via union des 3 plateformes triée par last_seen_at desc en Python"
metrics:
  duration: "~25 min"
  completed: "2026-04-17"
  tasks: 5
  files_changed: 9
---

# Phase M006 Plan S03-P01 : Couche application créateur — Summary

**One-liner :** 3 use cases creator (GetCreator, ListCreators, ListCreatorVideos) + VideoRepository.list_by_creator, 20 tests verts, couche application prête pour CLI (P02) et MCP (P03).

## Fichiers créés / modifiés

| Fichier | Action | Description |
|---------|--------|-------------|
| `src/vidscope/ports/repositories.py` | modifié | Ajout `VideoRepository.list_by_creator(creator_id, *, limit=50)` dans le Protocol |
| `src/vidscope/adapters/sqlite/video_repository.py` | modifié | Implémentation `list_by_creator` + import `CreatorId` |
| `src/vidscope/application/get_creator.py` | créé | `GetCreatorUseCase` + `GetCreatorResult` |
| `src/vidscope/application/list_creators.py` | créé | `ListCreatorsUseCase` + `ListCreatorsResult` |
| `src/vidscope/application/list_creator_videos.py` | créé | `ListCreatorVideosUseCase` + `ListCreatorVideosResult` |
| `src/vidscope/application/__init__.py` | modifié | Export des 6 nouveaux symboles publics |
| `tests/unit/application/test_get_creator.py` | créé | 6 tests GetCreatorUseCase |
| `tests/unit/application/test_list_creators.py` | créé | 8 tests ListCreatorsUseCase |
| `tests/unit/application/test_list_creator_videos.py` | créé | 6 tests ListCreatorVideosUseCase |

## Shape finale des use cases

### GetCreatorUseCase

```python
class GetCreatorUseCase:
    def execute(self, platform: Platform, handle: str) -> GetCreatorResult: ...

@dataclass(frozen=True, slots=True)
class GetCreatorResult:
    found: bool
    creator: Creator | None = None
```

Résolution `(platform, handle)` via `uow.creators.find_by_handle`. Retourne `found=False` sans lever d'exception si absent.

### ListCreatorsUseCase

```python
class ListCreatorsUseCase:
    def execute(
        self, *, platform: Platform | None = None,
        min_followers: int | None = None, limit: int = 20
    ) -> ListCreatorsResult: ...

@dataclass(frozen=True, slots=True)
class ListCreatorsResult:
    creators: tuple[Creator, ...]
    total: int
```

- Sans filtre : union des 3 plateformes triée par `last_seen_at desc`
- Filtre `platform` seul : `list_by_platform`
- Filtre `min_followers` seul : `list_by_min_followers`
- Dual-filter : `list_by_platform(limit=200)` + filtrage Python sur `follower_count`
- `limit` clampé à `[1, 200]`

### ListCreatorVideosUseCase

```python
class ListCreatorVideosUseCase:
    def execute(
        self, platform: Platform, handle: str, *, limit: int = 20
    ) -> ListCreatorVideosResult: ...

@dataclass(frozen=True, slots=True)
class ListCreatorVideosResult:
    found: bool
    creator: Creator | None = None
    videos: tuple[Video, ...] = ()
    total: int = 0
```

Résolution : `find_by_handle` → `list_by_creator(creator.id, limit=limit)`. `total` via `list_by_creator(limit=10000)`. `limit` clampé à `[1, 200]`.

### VideoRepository.list_by_creator

```python
# Protocol (ports/repositories.py)
def list_by_creator(self, creator_id: CreatorId, *, limit: int = 50) -> list[Video]: ...

# Adapter (adapters/sqlite/video_repository.py)
def list_by_creator(self, creator_id: CreatorId, *, limit: int = 50) -> list[Video]:
    # SELECT ... WHERE creator_id == int(creator_id) ORDER BY created_at DESC LIMIT limit
```

## Résultats de vérification

- `python -m uv run pytest -q` : **718 passed, 5 deselected** (aucune régression)
- `python -m uv run mypy src` : **Success: no issues found in 88 source files**
- `python -m uv run lint-imports` : **9 kept, 0 broken**

## Commits atomiques

| Hash | Message |
|------|---------|
| `2047fed` | feat(M006/S03-P01): ajouter VideoRepository.list_by_creator au Protocol + adapter SQLite |
| `c44d32c` | feat(M006/S03-P01): GetCreatorUseCase + GetCreatorResult + 6 tests |
| `4800c89` | feat(M006/S03-P01): ListCreatorsUseCase + ListCreatorsResult + 8 tests |
| `9a4d489` | feat(M006/S03-P01): ListCreatorVideosUseCase + ListCreatorVideosResult + 6 tests |
| `830f3de` | feat(M006/S03-P01): exporter GetCreatorUseCase, ListCreatorsUseCase, ListCreatorVideosUseCase dans vidscope.application |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `Creator.__slots__` incompatible avec `__dict__`**
- **Trouvé pendant :** Task 2
- **Problème :** Le code du plan utilisait `Creator(**{**creator.__dict__, ...})` mais `Creator` utilise `__slots__` donc `__dict__` n'est pas disponible
- **Fix :** Remplacé par `dataclasses.replace(creator, follower_count=42000)`
- **Fichiers modifiés :** `tests/unit/application/test_get_creator.py`
- **Commit :** `c44d32c`

**2. [Rule 1 - Bug] `object.__setattr__` ne lève pas d'exception sur frozen dataclass**
- **Trouvé pendant :** Task 2
- **Problème :** `object.__setattr__` contourne le mécanisme `frozen=True` des dataclasses Python (CPython quirk). Le test ne levait jamais d'exception
- **Fix :** Remplacé par une assignation directe `result.found = True` qui lève `dataclasses.FrozenInstanceError` correctement
- **Fichiers modifiés :** `tests/unit/application/test_get_creator.py`, `tests/unit/application/test_list_creators.py`
- **Commit :** `c44d32c`, `4800c89`

**3. [Rule 1 - Bug] Erreur mypy sur `key` de `sorted` avec `datetime | None`**
- **Trouvé pendant :** Task 3
- **Problème :** `lambda c: c.last_seen_at or c.created_at` retourne `datetime | None` qui n'est pas compatible avec `SupportsDunderLT` attendu par mypy
- **Fix :** Ajout d'une constante sentinelle `_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)` utilisée comme fallback : `c.last_seen_at or c.created_at or _EPOCH`
- **Fichiers modifiés :** `src/vidscope/application/list_creators.py`
- **Commit :** `4800c89`

## Handoff pour S03-P02 (CLI) et S03-P03 (MCP)

Les 3 use cases sont importables depuis `vidscope.application` :

```python
from vidscope.application import (
    GetCreatorUseCase,       # GetCreatorResult(found, creator)
    ListCreatorsUseCase,     # ListCreatorsResult(creators: tuple, total: int)
    ListCreatorVideosUseCase,  # ListCreatorVideosResult(found, creator, videos: tuple, total: int)
)
```

Signatures `execute` :
- `GetCreatorUseCase.execute(platform: Platform, handle: str) -> GetCreatorResult`
- `ListCreatorsUseCase.execute(*, platform=None, min_followers=None, limit=20) -> ListCreatorsResult`
- `ListCreatorVideosUseCase.execute(platform: Platform, handle: str, *, limit=20) -> ListCreatorVideosResult`

## Self-Check: PASSED

Fichiers créés :
- `src/vidscope/application/get_creator.py` — FOUND
- `src/vidscope/application/list_creators.py` — FOUND
- `src/vidscope/application/list_creator_videos.py` — FOUND
- `tests/unit/application/test_get_creator.py` — FOUND
- `tests/unit/application/test_list_creators.py` — FOUND
- `tests/unit/application/test_list_creator_videos.py` — FOUND

Commits vérifiés :
- `2047fed` — FOUND
- `c44d32c` — FOUND
- `4800c89` — FOUND
- `9a4d489` — FOUND
- `830f3de` — FOUND
