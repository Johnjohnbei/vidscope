---
phase: M011
plan: S03
subsystem: application+cli+mcp
tags: [facetted-search, SearchFilters, AND-intersection, SQL-injection, CLI, MCP]
requirements: [R058]

dependency_graph:
  requires: [M011-S01, M011-S02]
  provides: [SearchFilters_7_facets, SearchVideosUseCase_AND_intersection, vidscope_search_CLI_M011, vidscope_search_MCP_M011]
  affects: [M011-S04]

tech_stack:
  added: []
  patterns:
    - SearchFilters frozen+slots étendu à 7 champs (3 M010 + 4 M011) tous default None (backward compat)
    - Pattern AND intersection via set.intersection(*sources) sur list de sets optionnels
    - starred=False → EXCLUSION pattern (excluded_starred set séparé), pas de liste positive des non-starred
    - Fast path FTS5 pur préservé quand filters.is_empty() == True
    - Oversample factor 5x en FTS5 pour garantir limit après post-filter
    - MCP inline import (SearchVideosUseCase dans closure) pour respecter mcp-has-no-adapters contract
    - _parse_tracking_status helper miroir de _parse_content_type avec BadParameter Typer

key_files:
  modified:
    - src/vidscope/application/search_videos.py (SearchFilters 7 champs + SearchVideosUseCase AND intersection)
    - src/vidscope/cli/commands/search.py (4 nouvelles options CLI + _parse_tracking_status)
    - src/vidscope/mcp/server.py (vidscope_search étendu 7 facets + SearchVideosUseCase)
  created:
    - tests/unit/application/test_search_videos_m011.py (17 tests unitaires SearchFilters + SearchVideosUseCase)
    - tests/unit/application/test_search_facets_matrix.py (1 test matrix 50 combos)
    - tests/unit/application/test_search_sql_injection.py (41 tests fuzz SQL injection)
    - tests/unit/cli/test_search_cmd_m011.py (7 tests CLI M011)
    - tests/unit/mcp/test_search_facets.py (9 tests MCP facets)

decisions:
  - "D5 extension strategy: two-phase approach conservé (FTS5 + Python set intersection). JOIN FTS5 virtuelle rejeté."
  - "starred=False = EXCLUSION pattern: excluded_starred set séparé de sources[], allowed=None quand seul starred=False est set"
  - "MCP inline import SearchVideosUseCase dans closure pour respecter contract mcp-has-no-adapters (10 contrats KEPT)"
  - "tag lowercase côté CLI et côté repo (redondant mais explicite pour messages d'erreur utilisateur)"
  - "Matrix test: C(7,3)=35 combos + 15 combos C(7,4) = 50 combos avec seed=42 pour reproductibilité"

metrics:
  duration: ~45min
  tasks_completed: 2
  files_created: 5
  files_modified: 3
  tests_added: 75
---

# Phase M011 Plan S03: Facetted Search Summary

**One-liner:** SearchFilters étendu à 7 facets (AND semantics) avec intersection set multi-sources, CLI vidscope search 4 nouvelles options, MCP vidscope_search 7 facets, matrix 50 combos + fuzz SQL injection 20 payloads.

## What Was Built

S03 livre la slice qui rend M011 *utile*. La requête *"tous les saved+starred en tag 'idea'"* est maintenant possible en une commande.

### SearchFilters final — 7 champs (backward compatible)

```python
@dataclass(frozen=True, slots=True)
class SearchFilters:
    # M010 (inchangés):
    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None
    # M011/S03 nouveaux:
    status: TrackingStatus | None = None
    starred: bool | None = None          # None=no filter, True=starred only, False=EXCLUSION
    tag: str | None = None               # single tag (normalized)
    collection: str | None = None        # single collection (case-preserved)

    def is_empty(self) -> bool:
        return (
            self.content_type is None and self.min_actionability is None
            and self.is_sponsored is None and self.status is None
            and self.starred is None and self.tag is None and self.collection is None
        )
```

`SearchFilters()` sans argument → is_empty() == True → fast path FTS5 pur (backward compat Pitfall 1).

### Algorithme d'intersection AND

```
sources: list[set[int]] = []  # positive constraints
excluded_starred: set[int] | None = None  # negative constraint (starred=False only)

# Chaque facet active ajoute un set dans sources
# M010: analyses.list_by_filters → sources.append(analysis_ids)
# M011: video_tracking.list_by_status → sources.append(status_ids)
# M011: video_tracking.list_starred → sources.append(starred_ids) [si starred=True]
#      OU → excluded_starred = starred_ids [si starred=False]
# M011: tags.list_video_ids_for_tag → sources.append(tag_ids)
# M011: collections.list_video_ids_for_collection → sources.append(coll_ids)

# AND intersection:
allowed = set.intersection(*sources) if len(sources) > 1 else sources[0]
# Si sources est vide (seul starred=False): allowed = None
```

**Traitement spécial starred=False (EXCLUSION):**
- `starred=True` → positive constraint via `sources.append(starred_ids)`
- `starred=False` → negative constraint via `excluded_starred` (complément)
- Le filtre final excluant les starred_ids est appliqué dans la boucle post-FTS5

**Early return:** Si `allowed is not None and not allowed` → hits=() sans appeler FTS5.

### Oversample factor 5x préservé

```python
raw_hits = uow.search_index.search(query, limit=max(limit, limit * 5))
```

Nécessaire pour garantir de retourner `limit` hits après post-filtrage. Hérité de M010/S04.

### CLI signature finale `vidscope search`

```
vidscope search <query>
  [--limit N]
  [--content-type TYPE]            # M010 — tutorial|review|vlog|...
  [--min-actionability N]          # M010 — 0-100
  [--sponsored true|false]         # M010
  [--status new|reviewed|saved|actioned|ignored|archived]  # M011
  [--starred | --unstarred]        # M011 — bool flag
  [--tag NAME]                     # M011 — case-insensitive (lowercased CLI-side)
  [--collection NAME]              # M011 — case-preserved
```

- `--status bogus` → `typer.BadParameter` exit code 2 avec liste des 6 valeurs valides
- `--tag Idea` → normalisé en `"idea"` côté CLI avant SearchFilters

### MCP tool signature finale `vidscope_search` (7 facets)

```python
def vidscope_search(
    query: str,
    limit: int = 20,
    content_type: str | None = None,        # M010
    min_actionability: int | None = None,   # M010
    is_sponsored: bool | None = None,       # M010
    status: str | None = None,              # M011
    starred: bool | None = None,            # M011
    tag: str | None = None,                 # M011
    collection: str | None = None,          # M011
) -> dict[str, Any]:
```

- `status="bogus"` → lève `ValueError("status must be a valid TrackingStatus: ...")`
- `content_type="podcast"` → lève `ValueError("content_type must be a valid ContentType: ...")`
- Import inline de `SearchVideosUseCase` dans la closure pour respecter `mcp-has-no-adapters` contract

### Matrix test

```
C(7,3) = 35 combos de 3 facets
+ 15 combos de 4 facets (seed=42, reproductible)
= 50 combos total
```

Chaque combo: construit un `SearchFilters`, execute sur une fixture de 10 videos (toutes dans toutes les facets), vérifie `len(hits) <= limit`. Aucun crash sur 50 combos.

### Payloads fuzz SQL injection

20 payloads stratégiques testés sur les facets `tag` et `collection` (les seules string utilisateur) :
- `"'"`, `"--"`, `"; DROP TABLE videos;--"`, `"' OR '1'='1"`, `"' UNION SELECT * FROM videos--"`
- `"\\"`, `"%"`, `"_"`, `"\x00"`, `"\" OR 1=1--"`, `` "`" ``
- `"<script>alert(1)</script>"`, `"../../etc/passwd"`, `"0; SELECT * FROM sqlite_master"`
- `"\n\r\t"`, `"normal_tag_name"`, `"AAAAA" * 500`, emoji, zhongwen, DELETE FROM tags
- Résultat: 2 videos insérées avant fuzz, COUNT=2 après fuzz (table intact)
- Les bind params SQLAlchemy Core neutralisent structurellement l'injection

## Deviations from Plan

Aucune déviation. Plan exécuté exactement tel qu'écrit.

**Note sur tests pré-existants hors scope:** Certains tests dans `tests/unit/adapters/sqlite/test_creator_repository.py` et `tests/integration/pipeline/test_visual_intelligence_stage.py` échouent à l'import (Creator, VisualIntelligenceStage) — ces tests sont hors scope de S03, ils référencent des entités M009+ absentes de ce worktree. Enregistrés dans deferred-items.

## Known Stubs

Aucun stub. Toutes les fonctionnalités S03 sont wired end-to-end:
- SearchFilters → SearchVideosUseCase → VideoTrackingRepository + TagRepository + CollectionRepository → SQLite adapters
- CLI → SearchFilters → SearchVideosUseCase
- MCP tool → SearchFilters → SearchVideosUseCase

## Threat Flags

Aucune nouvelle surface de sécurité hors plan. Les mitigations du threat model sont toutes couvertes:
- T-SQL-M011-03: fuzz test 40 runs (20 payloads × 2 facets) — COVERED
- T-LOGIC-M011-01: early return `allowed is not None and not allowed` — COVERED
- T-BACKWARDS-M011-01: `SearchFilters()` → is_empty() True → fast path — COVERED
- T-STARRED-M011-01: excluded_starred set séparé — COVERED
- T-CASE-M011-01: CLI lowercase + test avec "Idea" input — COVERED
- T-ARCH-M011-03: `grep -nE "from vidscope.adapters" src/vidscope/application/search_videos.py` → exit 1 — COVERED

## Self-Check: PASSED

Fichiers modifiés:
- src/vidscope/application/search_videos.py — `status: TrackingStatus | None = None` présent: YES
- src/vidscope/cli/commands/search.py — `"--status"` présent: YES
- src/vidscope/mcp/server.py — `SearchVideosUseCase` présent: YES

Fichiers créés:
- tests/unit/application/test_search_videos_m011.py — TestSearchFiltersExtended: YES
- tests/unit/application/test_search_facets_matrix.py — test_matrix_50_combinations_do_not_crash: YES
- tests/unit/application/test_search_sql_injection.py — TestSqlInjectionResistance: YES
- tests/unit/cli/test_search_cmd_m011.py — TestSearchCmdM011: YES
- tests/unit/mcp/test_search_facets.py — TestMcpSearchFacets: YES

Commits:
- f74f347: feat(M011-S03): Task 1 — VERIFIED
- 2282ef8: feat(M011-S03): Task 2 — VERIFIED

Tests: 112 passed, 0 failed
lint-imports: 10 contracts KEPT, 0 broken
vidscope search --help: --status, --starred, --tag, --collection tous présents
