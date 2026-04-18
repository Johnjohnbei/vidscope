---
plan_id: S04-P01
phase: M007/S04
subsystem: application + cli
tags: [search, facets, links, use-case, cli, m007]
completed_at: 2026-04-18T10:53:50Z
duration_minutes: 65

dependency_graph:
  requires: [S03-P02]
  provides: [SearchLibraryUseCase-facets, ListLinksUseCase, vidscope-search-facets, vidscope-links-command]
  affects: [application/__init__.py, cli/app.py, cli/commands/__init__.py]

tech_stack:
  added: []
  patterns:
    - AND-implicit facet intersection via Python set operations
    - synthetic SearchResult for empty-query + facet cases
    - Typer options for boolean flag (--has-link) and optional strings

key_files:
  created:
    - src/vidscope/application/list_links.py
    - src/vidscope/cli/commands/links.py
    - tests/unit/application/test_search_library.py
    - tests/unit/application/test_list_links.py
    - tests/unit/cli/test_search_cmd.py
    - tests/unit/cli/test_links_cmd.py
  modified:
    - src/vidscope/application/search_library.py
    - src/vidscope/application/__init__.py
    - src/vidscope/cli/commands/search.py
    - src/vidscope/cli/commands/__init__.py
    - src/vidscope/cli/app.py

decisions:
  - Synthèse de SearchResult (source="video", rank=1.0, snippet=title) quand query vide + facette active, pour éviter d'appeler FTS5 avec une query vide
  - video non trouvée dans repo lors de synthèse → résultat inclus avec snippet "video #N" (pas de skip silencieux)
  - Import direct dans les tests (pas de lazy-import) pour compatibilité ruff RUF059

metrics:
  tasks_completed: 3
  tasks_total: 3
  tests_added: 37
  tests_total: 915
  files_created: 6
  files_modified: 5
---

# Phase M007 Plan S04-P01: CLI facets + ListLinksUseCase Summary

**One-liner:** FTS5+facets search with AND-implicit intersection and new `vidscope links <id>` command exposing extracted URLs via Rich table.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T01 | Étendre SearchLibraryUseCase avec 4 facettes + tests | 8e7ed8a | search_library.py, test_search_library.py |
| T02 | Créer ListLinksUseCase + tests | 995e420 | list_links.py, __init__.py, test_list_links.py |
| T03 | CLI search + links commands + tests | a224755 | search.py, links.py, app.py, __init__.py (x2), test_*.py |

## What Was Built

### SearchLibraryUseCase — 4 nouvelles facettes

`execute(query, *, limit, hashtag, mention, has_link, music_track)` avec :

- **AND-implicit** : chaque facette active réduit l'ensemble des video_ids candidates via intersection Python `set`
- **hashtag** : canonicalisé par `HashtagRepository.find_video_ids_by_tag` (`#Coding` → `coding`)
- **mention** : canonicalisé par `MentionRepository.find_video_ids_by_handle` (`@Alice` → `alice`)
- **has_link** : booléen via `LinkRepository.find_video_ids_with_any_link`
- **music_track** : exact match filtré en mémoire via `VideoRepository.list_recent(limit=1000)`
- **Synthèse SearchResult** : quand `query=""` + facette active → pas d'appel FTS5, génère un résultat synthétique par vidéo (source="video", rank=1.0, snippet=title)

### ListLinksUseCase

`execute(video_id, *, source=None)` → `ListLinksResult(video_id, found, links)` :

- `found=False` quand la vidéo n'existe pas (pas d'exception)
- `found=True, links=()` quand la vidéo existe sans liens
- filtre optionnel par `source` délégué à `LinkRepository.list_for_video`

### CLI

- `vidscope search <query> [--hashtag] [--mention] [--has-link] [--music-track] [--limit]`
- `vidscope links <id> [--source]` — nouvelle commande affichant les URLs en Rich table (colonnes : id, source, url, position)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Synthèse incluait les vidéos non trouvées en repo**
- **Found during:** T01 RED
- **Issue:** L'implémentation initiale du plan faisait `if video is None: continue` dans la boucle de synthèse — ce qui retournait 0 résultats dans les tests où seul le repo hashtag/link était peuplé mais pas le repo video
- **Fix:** Remplacement par `snippet = (video.title or f"video #{vid}") if video is not None else f"video #{vid}"` — inclure le résultat même si la vidéo n'est pas dans le repo video
- **Files modified:** src/vidscope/application/search_library.py
- **Commit:** 8e7ed8a

**2. [Rule 1 - Bug] Erreur mypy sur opérateur & avec type `set[int] | None`**
- **Found during:** T01 mypy check
- **Issue:** `allowed_ids: set[int] | None = facet_sets[0]; allowed_ids = allowed_ids & s` — mypy rejette l'opérateur & sur un type union avec None
- **Fix:** Introduction d'une variable intermédiaire `result_set: set[int]` pour les intersections
- **Files modified:** src/vidscope/application/search_library.py
- **Commit:** 8e7ed8a

**3. [Rule 2 - Quality] Erreurs ruff RUF059 sur lazy-import pattern dans tests**
- **Found during:** T03 ruff check
- **Issue:** Pattern `ListLinksResult, ListLinksUseCase = _get_use_case_classes()` générait des `RUF059 Unpacked variable is never used` quand seulement l'un des deux était utilisé dans chaque test
- **Fix:** Import direct au top du fichier (le module existe maintenant), suppression du lazy-import pattern
- **Files modified:** tests/unit/application/test_list_links.py
- **Commit:** a224755

## Known Stubs

Aucun stub. Toute la logique est câblée aux repositories réels via UnitOfWork.

## Threat Flags

Aucun nouveau endpoint réseau ou surface d'authentification introduite. Les mitigations du plan (T-S04P01-01 à T-S04P01-05) sont respectées :
- Pas de concaténation SQL — SQLAlchemy Core bindings dans les adapters
- `limit=1000` sur chaque facette (T-S04P01-02)
- Les URLs affichées dans la table Rich sont les URLs publiques déjà en base (T-S04P01-04)

## Self-Check: PASSED

Fichiers créés vérifiés :
- src/vidscope/application/list_links.py : FOUND
- src/vidscope/cli/commands/links.py : FOUND
- tests/unit/application/test_search_library.py : FOUND
- tests/unit/application/test_list_links.py : FOUND
- tests/unit/cli/test_search_cmd.py : FOUND
- tests/unit/cli/test_links_cmd.py : FOUND

Commits vérifiés :
- 8e7ed8a (T01) : FOUND
- 995e420 (T02) : FOUND
- a224755 (T03) : FOUND

Suite complète : 915 passed, 5 deselected
mypy : Success: no issues found in 99 source files
lint-imports : Contracts: 10 kept, 0 broken
ruff : All checks passed
