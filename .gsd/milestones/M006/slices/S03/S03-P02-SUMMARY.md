---
plan_id: S03-P02
phase: M006/S03
plan: 02
subsystem: cli
tags: [cli, typer, creator, rich, video-entity]
dependency_graph:
  requires:
    - M006/S03-P01  # GetCreatorUseCase, ListCreatorsUseCase, ListCreatorVideosUseCase
    - M006/S01-P03  # CreatorRepositorySQLite + UoW wiring
  provides:
    - creator_app   # consommé par vidscope CLI entry point
    - Video.creator_id  # consommé par ShowVideoUseCase, list_command, futur MCP
  affects:
    - src/vidscope/cli/app.py
    - src/vidscope/cli/commands/__init__.py
    - src/vidscope/cli/commands/creators.py
    - src/vidscope/cli/commands/show.py
    - src/vidscope/cli/commands/list.py
    - src/vidscope/domain/entities.py
    - src/vidscope/adapters/sqlite/video_repository.py
    - src/vidscope/application/show_video.py
tech_stack:
  added: []
  patterns:
    - Typer sub-app (creator_app) enregistré via app.add_typer
    - Rich Panel.fit pour profil créateur (creator show)
    - Rich Table pour listing (creator list, creator videos)
    - MagicMock container + patch build_container dans tests CLI
    - Video.creator_id champ optionnel (rétrocompat totale, default None)
key_files:
  created:
    - src/vidscope/cli/commands/creators.py
    - tests/unit/cli/test_creators.py
  modified:
    - src/vidscope/cli/commands/__init__.py
    - src/vidscope/cli/app.py
    - src/vidscope/domain/entities.py
    - src/vidscope/adapters/sqlite/video_repository.py
    - src/vidscope/application/show_video.py
    - src/vidscope/cli/commands/show.py
    - src/vidscope/cli/commands/list.py
decisions:
  - "Video.creator_id ajouté comme champ optionnel (default None) pour rétrocompat totale — aucun test existant cassé"
  - "ShowVideoUseCase charge le créateur via uow.creators.get(video.creator_id) dans la même transaction"
  - "Tests CLI utilisent MagicMock container + patch build_container (pas de vraie infrastructure) avec SQLite réel en tmp_path"
  - "Ruff B904 corrigé : raise ... from None dans _parse_platform; E501 corrigés via reformatage"
metrics:
  duration: "~35 min"
  completed: "2026-04-17"
  tasks: 5
  files_changed: 9
---

# Phase M006 Plan S03-P02 : CLI surfaces — Summary

**One-liner :** `vidscope creator` sub-app (show/list/videos) + Video.creator_id propagé du DB vers l'entity + enrichissement inline de `vidscope show` et `vidscope list`, 9 tests CLI verts.

## Fichiers créés / modifiés

| Fichier | Action | Description |
|---------|--------|-------------|
| `src/vidscope/cli/commands/creators.py` | créé | `creator_app` Typer sub-app : 3 commandes show/list/videos |
| `src/vidscope/cli/commands/__init__.py` | modifié | Import + export `creator_app` |
| `src/vidscope/cli/app.py` | modifié | `app.add_typer(creator_app, name="creator")` |
| `src/vidscope/domain/entities.py` | modifié | `Video.creator_id: CreatorId | None = None` ajouté |
| `src/vidscope/adapters/sqlite/video_repository.py` | modifié | `_row_to_video` lit `creator_id` depuis la colonne DB |
| `src/vidscope/application/show_video.py` | modifié | `ShowVideoResult.creator` + chargement via `uow.creators.get` |
| `src/vidscope/cli/commands/show.py` | modifié | Bloc créateur inline après analyse |
| `src/vidscope/cli/commands/list.py` | modifié | Colonne `creator_id` entre `author` et `duration` |
| `tests/unit/cli/test_creators.py` | créé | 9 tests snapshot pour creator show/list/videos |

## Fonctionnalités livrées

### 1. `vidscope creator show <handle> [--platform]`
Rich Panel avec : id, platform, handle, display_name, followers, verified, profile_url, first_seen, last_seen. Platform par défaut : youtube (D-04). Retourne exit code 1 si créateur absent.

### 2. `vidscope creator list [--platform] [--min-followers N] [--limit N]`
Rich Table avec colonnes : id, platform, handle, display_name, followers, verified, last_seen. Delègue au `ListCreatorsUseCase` (dual-filter platform + min_followers). Limit clampé à [1,200].

### 3. `vidscope creator videos <handle> [--platform] [--limit N]`
Rich Table avec colonnes : id, platform, title, duration, ingested. Affiche créateur + total en en-tête. Retourne exit code 1 si créateur absent.

### 4. `vidscope show <id>` enrichi
`Video.creator_id` peuplé depuis la DB via `_row_to_video`. `ShowVideoUseCase` charge le `Creator` via `uow.creators.get`. `show_command` affiche le bloc créateur inline : handle, platform, followers.

### 5. `vidscope list` enrichi
Colonne `creator_id` ajoutée entre `author` et `duration` — affiche l'int FK si peuplé, sinon `-`.

## Propagation de Video.creator_id

```
DB (videos.creator_id) → _row_to_video → Video.creator_id → ShowVideoUseCase.execute → ShowVideoResult.creator → show_command
                                        ↘ list_command (affiche directement creator_id)
```

## Résultats de vérification

- `python -m uv run pytest -q` : **727 passed, 5 deselected** (9 nouveaux tests, aucune régression)
- `python -m uv run mypy src` : **Success: no issues found in 89 source files**
- `python -m uv run lint-imports` : **9 kept, 0 broken**
- `python -m uv run ruff check src/vidscope/cli tests/unit/cli/test_creators.py` : **All checks passed**

## Commits atomiques

| Hash | Message |
|------|---------|
| `d60dec9` | feat(M006/S03-P02): créer creator_app Typer sub-app avec show, list, videos |
| `524b71e` | feat(M006/S03-P02): enregistrer creator_app dans app.py et commands/__init__.py |
| `0f18847` | feat(M006/S03-P02): enrichir vidscope show avec le bloc créateur inline |
| `137a5bf` | feat(M006/S03-P02): ajouter colonne creator_id dans vidscope list |
| `cf1bc4d` | test(M006/S03-P02): 9 tests CLI snapshot pour creator show/list/videos |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff B904 : raise dans except sans `from`**
- **Trouvé pendant :** Task 5 (vérification ruff finale)
- **Problème :** `_parse_platform` levait `typer.BadParameter` dans un bloc `except ValueError:` sans `from` — ruff B904
- **Fix :** Remplacé `raise typer.BadParameter(...)` par `raise typer.BadParameter(...) from None`
- **Fichiers modifiés :** `src/vidscope/cli/commands/creators.py`
- **Commit :** `cf1bc4d`

**2. [Rule 1 - Bug] Ruff E501 : lignes trop longues dans creators.py et test_creators.py**
- **Trouvé pendant :** Task 5 (vérification ruff finale)
- **Problème :** Plusieurs lignes > 100 chars dans les deux fichiers du plan
- **Fix :** Reformatage des expressions ternaires longues, extraction des f-strings, alias `_PATCH` dans les tests
- **Fichiers modifiés :** `src/vidscope/cli/commands/creators.py`, `tests/unit/cli/test_creators.py`
- **Commit :** `cf1bc4d`

**Note hors scope :** `tests/unit/application/test_list_creators.py` et `test_list_creator_videos.py` (livrés en S03-P01) ont des E501 pré-existants non corrigés — hors périmètre S03-P02.

## Handoff pour S03-P03 (MCP)

Les use cases sont tous câblés et testés :

```python
from vidscope.application import (
    GetCreatorUseCase,       # GetCreatorResult(found, creator)
    ListCreatorsUseCase,     # ListCreatorsResult(creators: tuple, total: int)
    ListCreatorVideosUseCase,  # ListCreatorVideosResult(found, creator, videos, total)
)
```

`Video.creator_id: CreatorId | None` est disponible dans l'entity pour le MCP tool `vidscope_get_creator`.

## Known Stubs

Aucun stub identifié — toutes les commandes s'appuient sur des données réelles via les use cases applicatifs.

## Threat Flags

Aucune nouvelle surface de sécurité non prévue dans le threat model du plan.

## Self-Check: PASSED

Fichiers créés :
- `src/vidscope/cli/commands/creators.py` — FOUND
- `tests/unit/cli/test_creators.py` — FOUND

Commits vérifiés :
- `d60dec9` — FOUND
- `524b71e` — FOUND
- `0f18847` — FOUND
- `137a5bf` — FOUND
- `cf1bc4d` — FOUND
