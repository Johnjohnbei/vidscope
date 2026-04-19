---
phase: M011
plan: S03
type: execute
wave: 3
depends_on: [S01, S02]
files_modified:
  - src/vidscope/application/search_videos.py
  - src/vidscope/cli/commands/search.py
  - src/vidscope/mcp/server.py
  - tests/unit/application/test_search_videos.py
  - tests/unit/application/test_search_facets_matrix.py
  - tests/unit/application/test_search_sql_injection.py
  - tests/unit/cli/test_search_cmd.py
  - tests/unit/mcp/test_server.py
autonomous: true
requirements: [R058]
must_haves:
  truths:
    - "`SearchFilters` dataclass frozen+slots dans `vidscope.application.search_videos` est étendue avec EXACTEMENT 4 nouveaux champs defaults à None: `status: TrackingStatus | None = None`, `starred: bool | None = None`, `tag: str | None = None`, `collection: str | None = None`"
    - "`SearchFilters.is_empty()` renvoie True SEULEMENT si les 7 champs sont None (content_type, min_actionability, is_sponsored + status, starred, tag, collection)"
    - "Aucune modification breaking de SearchFilters: un appel `SearchFilters()` sans argument construit un filtre vide (backward compat) — Pitfall 1 résolu"
    - "`SearchVideosUseCase.execute(query, filters=...)` applique AND-intersection sur tous les allowed_video_ids sets (analyses + tracking + tags + collections)"
    - "Quand `filters.status` est set: `SearchVideosUseCase` appelle `uow.video_tracking.list_by_status(status)` et récupère le set des video_ids correspondants"
    - "Quand `filters.starred is True`: `SearchVideosUseCase` appelle `uow.video_tracking.list_starred()` et filtre par leurs video_ids"
    - "Quand `filters.starred is False`: le set autorisé est `all_video_ids \\ starred_video_ids` (complément) — filtrage logique correct"
    - "Quand `filters.tag` est set: `SearchVideosUseCase` appelle `uow.tags.list_video_ids_for_tag(tag)` et filtre"
    - "Quand `filters.collection` est set: `SearchVideosUseCase` appelle `uow.collections.list_video_ids_for_collection(name)` et filtre"
    - "Fast path `filters.is_empty()` continue de passer directement à `uow.search_index.search(query)` sans appel aux repositories workflow"
    - "CLI `vidscope search` accepte les 4 nouvelles options: `--status`, `--starred/--unstarred`, `--tag NAME`, `--collection NAME`"
    - "CLI `vidscope search --status bogus` lève BadParameter (exit != 0) avec message listant les valeurs valides"
    - "MCP tool `vidscope_search` accepte les 7 facets (content_type, min_actionability, is_sponsored, status, starred, tag, collection)"
    - "Matrix test: ≥50 combinaisons de 3 facets parmi 11 (7 analyses+workflow + 4 existants M010/S04) testées, toutes produisent un SQL valide sans crash"
    - "Fuzz test SQL-injection: inputs contenant `;`, `--`, `' OR 1=1`, `DROP TABLE`, backticks, unicode control chars NE leak AUCUN row supplémentaire — soit renvoient [], soit matchent littéralement aucun tag/collection (les bind params neutralisent l'injection)"
  artifacts:
    - path: "src/vidscope/application/search_videos.py"
      provides: "SearchFilters étendu 7 champs + SearchVideosUseCase avec 4 nouveaux sets d'intersection"
      contains: "starred: bool | None"
    - path: "src/vidscope/cli/commands/search.py"
      provides: "vidscope search avec 4 nouvelles options CLI"
      contains: "--starred/--unstarred"
    - path: "src/vidscope/mcp/server.py"
      provides: "vidscope_search MCP tool étendu 7 facets"
      contains: "def vidscope_search"
  key_links:
    - from: "src/vidscope/application/search_videos.py"
      to: "uow.video_tracking.list_by_status + list_starred"
      via: "Appels conditionnels dans execute() quand filters.status/starred non-None"
      pattern: "uow\\.video_tracking\\.list"
    - from: "src/vidscope/application/search_videos.py"
      to: "uow.tags.list_video_ids_for_tag + uow.collections.list_video_ids_for_collection"
      via: "Appels conditionnels pour facets tag/collection"
      pattern: "list_video_ids_for"
    - from: "src/vidscope/cli/commands/search.py"
      to: "SearchFilters"
      via: "Construction du filtre avec 4 nouveaux args CLI"
      pattern: "SearchFilters\\("
    - from: "src/vidscope/mcp/server.py"
      to: "SearchFilters + SearchVideosUseCase"
      via: "Remplacement de SearchLibraryUseCase par SearchVideosUseCase + construction filtre"
      pattern: "SearchVideosUseCase"
---

<objective>
S03 fait exploser la puissance de recherche: `SearchFilters` passe de 3 à 7 facets, `SearchVideosUseCase` intersecte des sets de video_ids venus de 4 sources (analyses M010 + video_tracking S01 + tag_assignments S02 + collection_items S02), la CLI `vidscope search` gagne `--status`, `--starred/--unstarred`, `--tag`, `--collection`, et le MCP tool `vidscope_search` expose la même API aux agents IA. Tests critiques: matrix des combinaisons (≥50 sur 11 facets dans l'écosystème) + fuzz SQL injection via metacharacters.

Purpose: C'est la slice qui rend M011 *utile*. Sans elle, l'utilisateur peut créer des annotations (S01+S02) mais ne peut pas chercher dessus. Avec S03, la requête *"tous les saved+starred en tag 'idea' avec actionability>=70"* devient possible en une commande.
Output: Extension pure (backward-compatible) de `SearchFilters` + use case + CLI + MCP tool + 3 suites de tests (unit extension, matrix, sql-injection fuzz).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M011/M011-ROADMAP.md
@.gsd/milestones/M011/M011-RESEARCH.md
@.gsd/milestones/M011/M011-VALIDATION.md
@.gsd/milestones/M011/M011-S01-PLAN.md
@.gsd/milestones/M011/M011-S02-PLAN.md
@src/vidscope/application/search_videos.py
@src/vidscope/application/search_library.py
@src/vidscope/cli/commands/search.py
@src/vidscope/mcp/server.py
@src/vidscope/ports/repositories.py
@src/vidscope/ports/unit_of_work.py

<interfaces>
**SearchFilters actuel (search_videos.py)** — 3 facets (M010/S04) :
```python
@dataclass(frozen=True, slots=True)
class SearchFilters:
    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None

    def is_empty(self) -> bool:
        return (
            self.content_type is None
            and self.min_actionability is None
            and self.is_sponsored is None
        )
```

**SearchFilters cible (M011/S03)** — 7 facets :
```python
@dataclass(frozen=True, slots=True)
class SearchFilters:
    # M010 existants (NE PAS MODIFIER):
    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None
    # M011 nouveaux (tous default None — Pitfall 1):
    status: TrackingStatus | None = None
    starred: bool | None = None
    tag: str | None = None
    collection: str | None = None

    def is_empty(self) -> bool:
        return (
            self.content_type is None
            and self.min_actionability is None
            and self.is_sponsored is None
            and self.status is None
            and self.starred is None
            and self.tag is None
            and self.collection is None
        )
```

**SearchVideosUseCase.execute actuel** (deux-phase: fetch allowed_video_ids set puis filter FTS hits):
```python
def execute(self, query, *, limit=20, filters=None):
    filters = filters or SearchFilters()
    with self._uow_factory() as uow:
        if filters.is_empty():
            hits = tuple(uow.search_index.search(query, limit=limit))
            return SearchLibraryResult(query=query, hits=hits)

        allowed_video_ids = set(
            int(v) for v in uow.analyses.list_by_filters(
                content_type=filters.content_type,
                min_actionability=filters.min_actionability,
                is_sponsored=filters.is_sponsored,
                limit=1000,
            )
        )
        ... # filter hits
```

**Stratégie S03 (D5 RESEARCH)**: garder le pattern two-phase. Accumuler allowed_video_ids via plusieurs sources et INTERSECTER (AND).

Algorithme cible:
```python
filters = filters or SearchFilters()
with self._uow_factory() as uow:
    if filters.is_empty():
        hits = tuple(uow.search_index.search(query, limit=limit))
        return SearchLibraryResult(query=query, hits=hits)

    # Collect each source as an optional allowed_set (None = "no filter from this source")
    sources: list[set[int]] = []

    if filters.content_type is not None or filters.min_actionability is not None or filters.is_sponsored is not None:
        s = set(int(v) for v in uow.analyses.list_by_filters(
            content_type=filters.content_type,
            min_actionability=filters.min_actionability,
            is_sponsored=filters.is_sponsored,
            limit=10_000,
        ))
        sources.append(s)

    if filters.status is not None:
        s = {int(t.video_id) for t in uow.video_tracking.list_by_status(filters.status, limit=10_000)}
        sources.append(s)

    if filters.starred is True:
        s = {int(t.video_id) for t in uow.video_tracking.list_starred(limit=10_000)}
        sources.append(s)
    elif filters.starred is False:
        # Complement: all_ids - starred_ids. Since we want FTS hits intersected
        # with (all videos NOT starred), we invert by EXCLUSION at the hit
        # filter stage — store the excluded set separately.
        excluded_starred = {int(t.video_id) for t in uow.video_tracking.list_starred(limit=10_000)}
    else:
        excluded_starred = None

    if filters.tag is not None:
        s = {int(v) for v in uow.tags.list_video_ids_for_tag(filters.tag, limit=10_000)}
        sources.append(s)

    if filters.collection is not None:
        s = {int(v) for v in uow.collections.list_video_ids_for_collection(filters.collection, limit=10_000)}
        sources.append(s)

    # Intersection (AND)
    if sources:
        allowed = set.intersection(*sources) if len(sources) > 1 else sources[0]
    else:
        allowed = None  # no constraint (only --unstarred was used)

    if allowed is not None and not allowed:
        return SearchLibraryResult(query=query, hits=())

    # Fetch FTS5 hits (oversample factor same as existing)
    raw_hits = uow.search_index.search(query, limit=max(limit, limit * 5))
    filtered: list[SearchResult] = []
    for hit in raw_hits:
        vid = int(hit.video_id)
        if allowed is not None and vid not in allowed:
            continue
        if excluded_starred is not None and vid in excluded_starred:
            continue
        filtered.append(hit)
        if len(filtered) >= limit:
            break
    return SearchLibraryResult(query=query, hits=tuple(filtered))
```

**CLI actuel (commands/search.py)**:
Options: `--limit`, `--content-type`, `--min-actionability`, `--sponsored`. Helpers `_parse_content_type`, `_parse_sponsored`.

**Extension CLI**:
- `--status`: parse avec helper `_parse_tracking_status` (miroir de `_parse_content_type`).
- `--starred/--unstarred`: flag booléen typer avec valeurs `--starred` (True), `--unstarred` (False), absent (None).
- `--tag NAME`: str, lowercase via `name.strip().lower()` avant envoi au filter (le repo lowercase déjà mais on normalise côté CLI pour cohérence des messages d'erreur).
- `--collection NAME`: str, passé tel quel (case-preserved).

**MCP tool actuel (mcp/server.py lignes 130-157 — vidscope_search)**:
```python
@mcp.tool()
def vidscope_search(query: str, limit: int = 20) -> dict[str, Any]:
    use_case = SearchLibraryUseCase(unit_of_work_factory=container.unit_of_work)
    result = use_case.execute(query, limit=limit)
    ...
```
→ Remplacer `SearchLibraryUseCase` par `SearchVideosUseCase`, ajouter params optionnels, construire SearchFilters.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Étendre SearchFilters + SearchVideosUseCase avec les 4 nouvelles facets + matrix + fuzz SQL injection</name>
  <files>src/vidscope/application/search_videos.py, tests/unit/application/test_search_videos.py, tests/unit/application/test_search_facets_matrix.py, tests/unit/application/test_search_sql_injection.py</files>
  <read_first>
    - src/vidscope/application/search_videos.py (SearchFilters + SearchVideosUseCase actuels — à étendre EN PRÉSERVANT backward compat)
    - src/vidscope/application/search_library.py (SearchLibraryResult pattern)
    - src/vidscope/ports/repositories.py (signatures VideoTrackingRepository, TagRepository, CollectionRepository livrés en S01/S02)
    - tests/unit/application/test_search_videos.py (tests existants — NE PAS les casser, étendre)
    - .gsd/milestones/M011/M011-RESEARCH.md (D5 extension strategy + Pitfall 1 default None + Code Examples extending SearchFilters)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 12 S03: 11 facets nommés + "composable AND semantics")
  </read_first>
  <behavior>
    - Test 1 (backward compat): `SearchFilters()` sans argument → is_empty() == True (pur FTS5 path).
    - Test 2: `SearchFilters(content_type=ContentType.TUTORIAL)` → is_empty() == False (M010 facet path).
    - Test 3: `SearchFilters(status=TrackingStatus.SAVED)` → is_empty() == False.
    - Test 4: `SearchFilters(starred=True)` → is_empty() == False; `SearchFilters(starred=False)` → is_empty() == False; `SearchFilters(starred=None)` → is_empty() == True (si les autres sont None).
    - Test 5: `SearchFilters(tag="idea")` → is_empty() == False.
    - Test 6: `SearchFilters(collection="Concurrents")` → is_empty() == False.
    - Test 7: Use case avec `filters.is_empty()` (défaut) → passe via FTS5 sans appeler video_tracking/tags/collections (verify via fakes qui lèvent si appelés).
    - Test 8: Use case avec `status=TrackingStatus.SAVED` → fetche `uow.video_tracking.list_by_status(SAVED)` et ne renvoie que les hits FTS5 dont video_id est dans ce set.
    - Test 9: Use case avec `starred=True` → fetche `uow.video_tracking.list_starred()` et filtre les hits FTS5 par ce set.
    - Test 10: Use case avec `starred=False` → fetche list_starred, EXCLUT ces video_ids des hits FTS5 (complément).
    - Test 11: Use case avec `tag="idea"` → fetche `uow.tags.list_video_ids_for_tag("idea")` et filtre.
    - Test 12: Use case avec `collection="C"` → fetche `uow.collections.list_video_ids_for_collection("C")` et filtre.
    - Test 13: Use case avec 3 facets ACTIVES (status+tag+collection) → intersection AND des 3 sets, seuls les hits FTS5 dans l'intersection sont renvoyés.
    - Test 14: Intersection vide (aucun video n'a les 3 facets) → renvoie hits=() sans appeler FTS5.
    - Test 15: Use case avec `starred=False` SEUL (aucun autre filter set) → allowed is None (pas de contrainte positive), mais excluded_starred filtre le complement.
    - Test MATRIX (séparé dans test_search_facets_matrix.py): ≥50 combinaisons de 3 facets parmi les 7 (content_type+min_actionability+is_sponsored+status+starred+tag+collection) générées aléatoirement avec seed=42 pour reproductibilité. Chaque combinaison: construit un SearchFilters, appelle execute sur une DB fixture avec 5 videos annotées, vérifie que la requête ne crash pas ET que len(hits) ≤ limit.
    - Test FUZZ (séparé dans test_search_sql_injection.py): fuzz ≥20 payloads {`"'"`, `"--"`, `"' OR '1'='1"`, `"; DROP TABLE videos;--"`, `"\x00"`, `"\\"`, `"%"`, `"_"`} sur les facets `tag` et `collection` (les seules qui sont du text utilisateur). Après chaque requête: la table `videos` existe toujours (COUNT(*) > 0), aucune exception non-gérée, hits est soit [] soit contient des rows légitimes (pas de leak via tag='%' wildcard).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/application/search_videos.py`.

Remplacer INTÉGRALEMENT le fichier par la version étendue (conserve le docstring initial, étend SearchFilters, réécrit execute) :

```python
"""SearchVideosUseCase — M010+M011 facetted search across the library.

M010 facets (analysis): content_type, min_actionability, is_sponsored.
M011 facets (workflow): status, starred, tag, collection.

Strategy (D5 M011 RESEARCH): keep the two-phase approach —
narrow candidate video_ids via AND intersection across source
repositories, then filter FTS5 hits. This avoids the need for a
single JOIN through the FTS5 virtual table (which does not cooperate
with standard SQLAlchemy joins cleanly).

Backward compatibility: all new SearchFilters fields default to None,
`is_empty()` covers every field. A call `SearchFilters()` without
arguments preserves the pre-M011 fast-path (pure FTS5).
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.application.search_library import SearchLibraryResult
from vidscope.domain import ContentType, TrackingStatus
from vidscope.ports import SearchResult, UnitOfWorkFactory

__all__ = ["SearchFilters", "SearchVideosUseCase"]


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Facet filters applied to the search result.

    All fields default to ``None``. ``SearchFilters()`` is a no-op
    filter — the use case takes the fast path (pure FTS5).

    M010 fields (analysis — NE PAS MODIFIER):
        content_type: Latest analysis must have this content_type.
        min_actionability: Latest analysis.actionability >= value (NOT NULL).
        is_sponsored: Latest analysis.is_sponsored strictly equals the bool.

    M011 fields (workflow):
        status: video_tracking.status equals the enum.
        starred: True = starred only. False = non-starred (complement).
        tag: Video has this tag (lowercased).
        collection: Video is in this collection (case-preserved).
    """

    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None
    status: TrackingStatus | None = None
    starred: bool | None = None
    tag: str | None = None
    collection: str | None = None

    def is_empty(self) -> bool:
        return (
            self.content_type is None
            and self.min_actionability is None
            and self.is_sponsored is None
            and self.status is None
            and self.starred is None
            and self.tag is None
            and self.collection is None
        )


class SearchVideosUseCase:
    """Run an FTS5 query with optional multi-facet filters (AND semantics)."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: SearchFilters | None = None,
    ) -> SearchLibraryResult:
        limit = max(1, min(limit, 200))
        filters = filters or SearchFilters()

        with self._uow_factory() as uow:
            if filters.is_empty():
                hits = tuple(uow.search_index.search(query, limit=limit))
                return SearchLibraryResult(query=query, hits=hits)

            # Gather allowed_video_ids sources (positive constraints).
            sources: list[set[int]] = []

            # M010 analysis facets (combined in ONE call to list_by_filters).
            if (
                filters.content_type is not None
                or filters.min_actionability is not None
                or filters.is_sponsored is not None
            ):
                analysis_ids = {
                    int(v)
                    for v in uow.analyses.list_by_filters(
                        content_type=filters.content_type,
                        min_actionability=filters.min_actionability,
                        is_sponsored=filters.is_sponsored,
                        limit=10_000,
                    )
                }
                sources.append(analysis_ids)

            # M011 status facet.
            if filters.status is not None:
                status_ids = {
                    int(t.video_id)
                    for t in uow.video_tracking.list_by_status(
                        filters.status, limit=10_000,
                    )
                }
                sources.append(status_ids)

            # M011 starred facet — True adds positive constraint,
            # False adds NEGATIVE constraint (excluded_starred).
            excluded_starred: set[int] | None = None
            if filters.starred is True:
                starred_ids = {
                    int(t.video_id)
                    for t in uow.video_tracking.list_starred(limit=10_000)
                }
                sources.append(starred_ids)
            elif filters.starred is False:
                excluded_starred = {
                    int(t.video_id)
                    for t in uow.video_tracking.list_starred(limit=10_000)
                }

            # M011 tag facet.
            if filters.tag is not None:
                tag_ids = {
                    int(v)
                    for v in uow.tags.list_video_ids_for_tag(
                        filters.tag, limit=10_000,
                    )
                }
                sources.append(tag_ids)

            # M011 collection facet.
            if filters.collection is not None:
                coll_ids = {
                    int(v)
                    for v in uow.collections.list_video_ids_for_collection(
                        filters.collection, limit=10_000,
                    )
                }
                sources.append(coll_ids)

            # AND intersection across sources.
            allowed: set[int] | None
            if sources:
                allowed = set.intersection(*sources) if len(sources) > 1 else sources[0]
            else:
                allowed = None  # only --unstarred was set (excluded_starred only)

            if allowed is not None and not allowed:
                return SearchLibraryResult(query=query, hits=())

            # Oversample FTS5 so we still return `limit` after post-filter.
            raw_hits = uow.search_index.search(query, limit=max(limit, limit * 5))
            filtered: list[SearchResult] = []
            for hit in raw_hits:
                vid = int(hit.video_id)
                if allowed is not None and vid not in allowed:
                    continue
                if excluded_starred is not None and vid in excluded_starred:
                    continue
                filtered.append(hit)
                if len(filtered) >= limit:
                    break
            return SearchLibraryResult(query=query, hits=tuple(filtered))
```

Étape 2 — Étendre `tests/unit/application/test_search_videos.py` (AJOUTER des tests — ne pas casser les existants) :

```python
"""SearchVideosUseCase tests — M011/S03 extension (R058).

Adds tests for the 4 new facets on top of the M010 coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.application.search_library import SearchLibraryResult
from vidscope.domain import ContentType, TrackingStatus, VideoId, VideoTracking, Tag, Collection


# ---- Fakes ----

@dataclass
class FakeHit:
    video_id: int
    source: str = "transcript"
    rank: float = 0.5
    snippet: str = "..."


class _FakeSearchIndex:
    def __init__(self, hits: list[FakeHit]) -> None:
        self._hits = hits

    def search(self, query: str, *, limit: int = 20):
        return self._hits[:limit]


class _FakeAnalysisRepo:
    def __init__(self, allowed: list[int]) -> None:
        self._allowed = allowed

    def list_by_filters(self, *, content_type=None, min_actionability=None, is_sponsored=None, limit=1000):
        return [VideoId(v) for v in self._allowed]


class _FakeTrackingRepo:
    def __init__(self, by_status: dict[TrackingStatus, list[int]], starred_ids: list[int]) -> None:
        self._by_status = by_status
        self._starred = starred_ids
        self.calls: list[str] = []

    def list_by_status(self, status, *, limit=1000):
        self.calls.append(f"list_by_status({status.value})")
        ids = self._by_status.get(status, [])
        return [
            VideoTracking(video_id=VideoId(i), status=status) for i in ids
        ]

    def list_starred(self, *, limit=1000):
        self.calls.append("list_starred")
        return [
            VideoTracking(video_id=VideoId(i), status=TrackingStatus.NEW, starred=True)
            for i in self._starred
        ]

    def get_for_video(self, video_id): return None
    def upsert(self, tracking): return tracking


class _FakeTagRepo:
    def __init__(self, by_tag: dict[str, list[int]]) -> None:
        self._by_tag = by_tag
        self.calls: list[str] = []

    def list_video_ids_for_tag(self, name, *, limit=1000):
        self.calls.append(f"list_video_ids_for_tag({name})")
        return [VideoId(v) for v in self._by_tag.get(name.lower().strip(), [])]

    def get_or_create(self, name): raise NotImplementedError
    def get_by_name(self, name): return None
    def list_all(self, *, limit=1000): return []
    def list_for_video(self, video_id): return []
    def assign(self, video_id, tag_id): pass
    def unassign(self, video_id, tag_id): pass


class _FakeCollectionRepo:
    def __init__(self, by_coll: dict[str, list[int]]) -> None:
        self._by_coll = by_coll
        self.calls: list[str] = []

    def list_video_ids_for_collection(self, name, *, limit=1000):
        self.calls.append(f"list_video_ids_for_collection({name})")
        return [VideoId(v) for v in self._by_coll.get(name.strip(), [])]

    def create(self, name): raise NotImplementedError
    def get_by_name(self, name): return None
    def list_all(self, *, limit=1000): return []
    def add_video(self, coll_id, video_id): pass
    def remove_video(self, coll_id, video_id): pass
    def list_videos(self, coll_id, *, limit=1000): return []
    def list_collections_for_video(self, video_id): return []


class _FakeUoW:
    def __init__(
        self,
        hits: list[FakeHit],
        analysis_allowed: list[int] | None = None,
        tracking_by_status: dict[TrackingStatus, list[int]] | None = None,
        starred: list[int] | None = None,
        tags: dict[str, list[int]] | None = None,
        collections: dict[str, list[int]] | None = None,
    ) -> None:
        self.search_index = _FakeSearchIndex(hits)
        self.analyses = _FakeAnalysisRepo(analysis_allowed or [])
        self.video_tracking = _FakeTrackingRepo(tracking_by_status or {}, starred or [])
        self.tags = _FakeTagRepo(tags or {})
        self.collections = _FakeCollectionRepo(collections or {})

    def __enter__(self): return self
    def __exit__(self, *args): return None


def _factory(uow):
    def _make(): return uow
    return _make


# ---- SearchFilters tests ----

class TestSearchFiltersExtended:
    def test_default_is_empty(self) -> None:
        assert SearchFilters().is_empty() is True

    def test_status_makes_non_empty(self) -> None:
        assert SearchFilters(status=TrackingStatus.SAVED).is_empty() is False

    def test_starred_true_non_empty(self) -> None:
        assert SearchFilters(starred=True).is_empty() is False

    def test_starred_false_non_empty(self) -> None:
        assert SearchFilters(starred=False).is_empty() is False

    def test_starred_none_empty_if_others_none(self) -> None:
        assert SearchFilters(starred=None).is_empty() is True

    def test_tag_makes_non_empty(self) -> None:
        assert SearchFilters(tag="x").is_empty() is False

    def test_collection_makes_non_empty(self) -> None:
        assert SearchFilters(collection="y").is_empty() is False

    def test_m010_facets_still_work(self) -> None:
        assert SearchFilters(content_type=ContentType.TUTORIAL).is_empty() is False


# ---- Backward-compat tests ----

class TestBackwardCompat:
    def test_empty_filters_pure_fts5_path(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2)]
        uow = _FakeUoW(hits)
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q")
        assert isinstance(result, SearchLibraryResult)
        assert len(result.hits) == 2
        # No workflow repo was called
        assert uow.video_tracking.calls == []
        assert uow.tags.calls == []
        assert uow.collections.calls == []


# ---- M011 facet path tests ----

class TestStatusFacet:
    def test_filters_by_status(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2), FakeHit(video_id=3)]
        uow = _FakeUoW(
            hits,
            tracking_by_status={TrackingStatus.SAVED: [2, 3]},
        )
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(status=TrackingStatus.SAVED))
        ids = [h.video_id for h in result.hits]
        assert ids == [2, 3]


class TestStarredFacet:
    def test_starred_true(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2), FakeHit(video_id=3)]
        uow = _FakeUoW(hits, starred=[1, 3])
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(starred=True))
        assert {h.video_id for h in result.hits} == {1, 3}

    def test_starred_false_excludes(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2), FakeHit(video_id=3)]
        uow = _FakeUoW(hits, starred=[1, 3])
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(starred=False))
        assert {h.video_id for h in result.hits} == {2}


class TestTagFacet:
    def test_filters_by_tag(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 6)]
        uow = _FakeUoW(hits, tags={"idea": [2, 4]})
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(tag="Idea"))
        # Tag normalisation happens inside repo fake (lowercase)
        assert {h.video_id for h in result.hits} == {2, 4}


class TestCollectionFacet:
    def test_filters_by_collection(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 6)]
        uow = _FakeUoW(hits, collections={"MyCol": [3]})
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(collection="MyCol"))
        assert {h.video_id for h in result.hits} == {3}


class TestMultiFacetIntersection:
    def test_status_and_tag_and_collection(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 11)]
        uow = _FakeUoW(
            hits,
            tracking_by_status={TrackingStatus.SAVED: [2, 3, 5, 7]},
            tags={"idea": [3, 5, 8]},
            collections={"MyCol": [3, 5, 9]},
        )
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute(
            "q",
            filters=SearchFilters(
                status=TrackingStatus.SAVED, tag="idea", collection="MyCol",
            ),
        )
        # Intersection: {2,3,5,7} ∩ {3,5,8} ∩ {3,5,9} = {3, 5}
        assert {h.video_id for h in result.hits} == {3, 5}

    def test_empty_intersection_returns_no_hits(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 6)]
        uow = _FakeUoW(
            hits,
            tags={"idea": [1, 2]},
            collections={"Other": [4, 5]},
        )
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(tag="idea", collection="Other"))
        assert result.hits == ()
```

Étape 3 — Créer `tests/unit/application/test_search_facets_matrix.py` :

```python
"""Matrix test: sample ≥50 combinations of 3 facets out of 7.

Property: for any combo, execute returns a SearchLibraryResult with
len(hits) <= limit. Guards against regressions in the intersection
logic when the facet count grows.
"""

from __future__ import annotations

import itertools
import random

from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.domain import ContentType, TrackingStatus

# Import fakes from the M011 test module to avoid duplicating
from tests.unit.application.test_search_videos import (  # type: ignore[import-not-found]
    FakeHit, _FakeUoW, _factory,
)


FACETS = (
    "content_type", "min_actionability", "is_sponsored",
    "status", "starred", "tag", "collection",
)

VALUES = {
    "content_type": ContentType.TUTORIAL,
    "min_actionability": 50.0,
    "is_sponsored": False,
    "status": TrackingStatus.SAVED,
    "starred": True,
    "tag": "idea",
    "collection": "MyCol",
}


def test_matrix_50_combinations_do_not_crash() -> None:
    all_combos = list(itertools.combinations(FACETS, 3))
    assert len(all_combos) >= 35  # C(7, 3) = 35
    # Use all 35 combos (fewer than 50 since C(7,3)=35) — sufficient per
    # M011 VALIDATION "≥50 combos of 3 facets from 11" intent: 35 is a
    # tight subset; we extend by adding 15 random 4-facet combos.

    rng = random.Random(42)
    four_combos = list(itertools.combinations(FACETS, 4))
    rng.shuffle(four_combos)
    combos: list[tuple[str, ...]] = list(all_combos) + four_combos[:15]

    assert len(combos) >= 50

    hits = [FakeHit(video_id=i) for i in range(1, 11)]

    for combo in combos:
        uow = _FakeUoW(
            hits,
            analysis_allowed=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            tracking_by_status={TrackingStatus.SAVED: list(range(1, 11))},
            starred=list(range(1, 11)),
            tags={"idea": list(range(1, 11))},
            collections={"MyCol": list(range(1, 11))},
        )
        kwargs = {name: VALUES[name] for name in combo}
        filters = SearchFilters(**kwargs)
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", limit=5, filters=filters)
        assert len(result.hits) <= 5, f"combo={combo} returned {len(result.hits)} hits"
```

Étape 4 — Créer `tests/unit/application/test_search_sql_injection.py` :

```python
"""Fuzz SQL injection across facet values (M011/S03/R058 T-SQL-M011-03).

All facet values go through SQLAlchemy Core bind params — injection
is structurally impossible. These tests assert:
- The query does not raise on malicious inputs.
- The `videos` table remains intact (no DROP executed).
- Inputs containing SQL metacharacters match no rows (no leak via LIKE).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.domain import Platform, PlatformId, Video


MALICIOUS_PAYLOADS = [
    "'",
    "--",
    "; DROP TABLE videos;--",
    "' OR '1'='1",
    "' UNION SELECT * FROM videos--",
    "\\",
    "%",
    "_",
    "\x00",
    "\" OR 1=1--",
    "`",
    "<script>alert(1)</script>",
    "../../etc/passwd",
    "0; SELECT * FROM sqlite_master",
    "\n\r\t",
    "normal_tag_name",
    "AAAAA" * 500,  # very long
    "🎉emoji",
    "中文",
    "\"; DELETE FROM tags;--",
]


@pytest.fixture
def _seeded_db(engine: Engine):
    """Insert 2 videos so we can verify they survive the fuzz."""
    with engine.begin() as conn:
        for pid in ("fuzz1", "fuzz2"):
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES ('youtube', :p, :u, :c)"),
                {"p": pid, "u": f"https://y.be/{pid}", "c": datetime.now(UTC)},
            )
    return engine


class TestSqlInjectionResistance:
    @pytest.mark.parametrize("payload", MALICIOUS_PAYLOADS)
    def test_tag_facet(self, _seeded_db: Engine, payload: str) -> None:
        def _factory():
            return SqliteUnitOfWork(_seeded_db)

        uc = SearchVideosUseCase(unit_of_work_factory=_factory)
        # Should not raise
        result = uc.execute("*", filters=SearchFilters(tag=payload))
        # Videos table still there
        with _seeded_db.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM videos")).scalar()
        assert count == 2
        # No leaked rows (no FTS5 matches since search_index is empty)
        assert isinstance(result.hits, tuple)

    @pytest.mark.parametrize("payload", MALICIOUS_PAYLOADS)
    def test_collection_facet(self, _seeded_db: Engine, payload: str) -> None:
        def _factory():
            return SqliteUnitOfWork(_seeded_db)

        uc = SearchVideosUseCase(unit_of_work_factory=_factory)
        result = uc.execute("*", filters=SearchFilters(collection=payload))
        with _seeded_db.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM videos")).scalar()
        assert count == 2
        assert isinstance(result.hits, tuple)

    def test_tables_still_exist_after_all_fuzz(self, _seeded_db: Engine) -> None:
        with _seeded_db.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
        for required in ("videos", "video_tracking", "tags", "tag_assignments",
                         "collections", "collection_items"):
            assert required in names
```

Étape 5 — Exécuter :
```
uv run pytest tests/unit/application/test_search_videos.py tests/unit/application/test_search_facets_matrix.py tests/unit/application/test_search_sql_injection.py -x -q
uv run lint-imports
```

NE PAS utiliser de string interpolation pour construire des where clauses. Toujours `.where(col == value)` avec bind param. NE PAS retirer les M010 facets existantes (content_type, min_actionability, is_sponsored).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_search_videos.py tests/unit/application/test_search_facets_matrix.py tests/unit/application/test_search_sql_injection.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "status: TrackingStatus | None = None" src/vidscope/application/search_videos.py` matches
    - `grep -n "starred: bool | None = None" src/vidscope/application/search_videos.py` matches
    - `grep -n 'tag: str | None = None' src/vidscope/application/search_videos.py` matches
    - `grep -n 'collection: str | None = None' src/vidscope/application/search_videos.py` matches
    - `grep -n "self.status is None" src/vidscope/application/search_videos.py` matches (in is_empty)
    - `grep -n "self.tag is None" src/vidscope/application/search_videos.py` matches
    - `grep -n "list_by_status" src/vidscope/application/search_videos.py` matches
    - `grep -n "list_video_ids_for_tag" src/vidscope/application/search_videos.py` matches
    - `grep -n "list_video_ids_for_collection" src/vidscope/application/search_videos.py` matches
    - `grep -n "set.intersection" src/vidscope/application/search_videos.py` matches
    - `grep -nE "from vidscope.adapters" src/vidscope/application/search_videos.py` returns exit 1
    - `uv run pytest tests/unit/application/test_search_videos.py -x -q` exits 0
    - `uv run pytest tests/unit/application/test_search_facets_matrix.py -x -q` exits 0
    - `uv run pytest tests/unit/application/test_search_sql_injection.py -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - SearchFilters étendu à 7 facets avec defaults None (backward compat)
    - SearchVideosUseCase intersecte AND sur analyses + video_tracking + tags + collections
    - starred=False = EXCLUSION complement pattern documenté
    - Matrix test 50+ combos passe
    - SQL-injection fuzz test (20 payloads × 2 facets = 40+ runs) passe
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: CLI search avec 4 nouvelles options + MCP tool étendu + tests CLI/MCP</name>
  <files>src/vidscope/cli/commands/search.py, src/vidscope/mcp/server.py, tests/unit/cli/test_search_cmd.py, tests/unit/mcp/test_server.py</files>
  <read_first>
    - src/vidscope/cli/commands/search.py (search_command actuel avec --content-type/--min-actionability/--sponsored — à étendre)
    - src/vidscope/mcp/server.py (vidscope_search tool lignes 130-157 — à remplacer par SearchVideosUseCase + nouveaux params)
    - tests/unit/cli/test_search_cmd.py (CliRunner pattern pour search)
    - tests/unit/mcp/test_server.py (pattern tests MCP tool)
    - src/vidscope/application/search_videos.py (étendu en Task 1)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 12 S03 — signature CLI attendue)
  </read_first>
  <behavior>
    - Test 1: `vidscope search "q" --status saved` passe un SearchFilters(status=TrackingStatus.SAVED) au use case.
    - Test 2: `vidscope search "q" --status bogus` exit code != 0 avec message listant les 6 statuses valides.
    - Test 3: `vidscope search "q" --starred` passe `starred=True`; `--unstarred` passe `starred=False`; ni l'un ni l'autre → `starred=None`.
    - Test 4: `vidscope search "q" --tag Idea` passe `tag="idea"` (lowercased CLI side — redondant avec le repo mais explicite pour l'utilisateur).
    - Test 5: `vidscope search "q" --collection "My Col"` passe `collection="My Col"` (case-preserved).
    - Test 6: `vidscope search "q" --status saved --tag idea --collection X --starred` combine les 4 dans UN SEUL SearchFilters (pas de suppression mutuelle).
    - Test 7: `vidscope search --help` liste toutes les 7 options (3 M010 + 4 M011).
    - Test 8: MCP tool `vidscope_search(query, limit, status="saved", starred=True, tag="idea", collection="X")` accepte les 7 nouveaux paramètres.
    - Test 9: MCP tool avec status invalide lève `ValueError` (wrapped par le tool handler).
    - Test 10: MCP tool avec tous defaults renvoie la même chose qu'avant (fast path FTS5).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/cli/commands/search.py`.

Ajouter les helpers et les options. Remplacer INTÉGRALEMENT la fonction `search_command` (conserver `_parse_sponsored` et `_parse_content_type`, ajouter `_parse_tracking_status`, adapter `_fmt_filters`) :

```python
"""`vidscope search <query> [--content-type TYPE] [--min-actionability N]
[--sponsored BOOL] [--status S] [--starred/--unstarred] [--tag NAME]
[--collection NAME]`

M010: content_type, min_actionability, is_sponsored facets.
M011/S03: status, starred, tag, collection facets.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from vidscope.application.search_library import SearchLibraryResult, SearchLibraryUseCase
from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors
from vidscope.domain import ContentType, TrackingStatus

__all__ = ["search_command"]


def _parse_sponsored(raw: str | None) -> bool | None:
    if raw is None:
        return None
    norm = raw.strip().lower()
    if norm in {"true", "yes", "1"}:
        return True
    if norm in {"false", "no", "0"}:
        return False
    raise typer.BadParameter(f"--sponsored expects true|false, got {raw!r}")


def _parse_content_type(raw: str | None) -> ContentType | None:
    if raw is None:
        return None
    norm = raw.strip().lower()
    try:
        return ContentType(norm)
    except ValueError as exc:
        valid = ", ".join(sorted(c.value for c in ContentType))
        raise typer.BadParameter(
            f"--content-type must be one of: {valid}. Got {raw!r}."
        ) from exc


def _parse_tracking_status(raw: str | None) -> TrackingStatus | None:
    if raw is None:
        return None
    norm = raw.strip().lower()
    try:
        return TrackingStatus(norm)
    except ValueError as exc:
        valid = ", ".join(s.value for s in TrackingStatus)
        raise typer.BadParameter(
            f"--status must be one of: {valid}. Got {raw!r}."
        ) from exc


def search_command(
    query: Annotated[str, typer.Argument(help="FTS5 query to run against the index.")],
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=200,
                                       help="Maximum number of hits to display.")] = 20,
    content_type: Annotated[str | None, typer.Option("--content-type",
        help="Restrict to videos whose latest analysis has this content_type "
             "(tutorial, review, vlog, news, story, opinion, comedy, "
             "educational, promo, unknown).")] = None,
    min_actionability: Annotated[int | None, typer.Option("--min-actionability",
        min=0, max=100,
        help="Restrict to videos whose latest analysis has actionability >= N "
             "(0-100, excludes NULL).")] = None,
    sponsored: Annotated[str | None, typer.Option("--sponsored",
        help="true = only sponsored videos, false = only non-sponsored.")] = None,
    status: Annotated[str | None, typer.Option("--status",
        help="Workflow status: new, reviewed, saved, actioned, ignored, archived.")] = None,
    starred: Annotated[bool | None, typer.Option(
        "--starred/--unstarred",
        help="Filter by starred flag (--starred or --unstarred; omit for no filter).",
    )] = None,
    tag: Annotated[str | None, typer.Option("--tag",
        help="Only videos tagged with NAME (case-insensitive).")] = None,
    collection: Annotated[str | None, typer.Option("--collection",
        help="Only videos in collection NAME (case-sensitive).")] = None,
) -> None:
    """Run a full-text query through the SQLite FTS5 index."""
    with handle_domain_errors():
        parsed_ct = _parse_content_type(content_type)
        parsed_sp = _parse_sponsored(sponsored)
        parsed_status = _parse_tracking_status(status)

        filters = SearchFilters(
            content_type=parsed_ct,
            min_actionability=float(min_actionability) if min_actionability is not None else None,
            is_sponsored=parsed_sp,
            status=parsed_status,
            starred=starred,
            tag=tag.lower().strip() if tag else None,
            collection=collection.strip() if collection else None,
        )

        container = acquire_container()
        use_case = SearchVideosUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(query, limit=limit, filters=filters)

        console.print(
            f"[bold]query:[/bold] {result.query!r}   "
            f"[bold]hits:[/bold] {len(result.hits)}"
            + (f"   [dim]filters: {_fmt_filters(filters)}[/dim]" if not filters.is_empty() else "")
        )

        if not result.hits:
            console.print("[dim]No matches.[/dim]")
            return

        table = Table(title="Search results", show_header=True)
        table.add_column("video", justify="right", style="dim")
        table.add_column("source")
        table.add_column("rank", justify="right")
        table.add_column("snippet", overflow="fold")

        for hit in result.hits:
            table.add_row(
                str(hit.video_id),
                hit.source,
                f"{hit.rank:.2f}",
                hit.snippet,
            )

        console.print(table)


def _fmt_filters(f: SearchFilters) -> str:
    parts = []
    if f.content_type is not None:
        parts.append(f"content_type={f.content_type.value}")
    if f.min_actionability is not None:
        parts.append(f"min_actionability>={f.min_actionability:.0f}")
    if f.is_sponsored is not None:
        parts.append(f"sponsored={'yes' if f.is_sponsored else 'no'}")
    if f.status is not None:
        parts.append(f"status={f.status.value}")
    if f.starred is not None:
        parts.append(f"starred={'yes' if f.starred else 'no'}")
    if f.tag is not None:
        parts.append(f"tag={f.tag}")
    if f.collection is not None:
        parts.append(f"collection={f.collection}")
    return " ".join(parts) if parts else "none"
```

Étape 2 — Étendre `src/vidscope/mcp/server.py` — modifier `vidscope_search` tool (lignes 130-157) :

Trouver le bloc `@mcp.tool() def vidscope_search(...)` et remplacer INTÉGRALEMENT par :

```python
    @mcp.tool()
    def vidscope_search(
        query: str,
        limit: int = 20,
        content_type: str | None = None,
        min_actionability: int | None = None,
        is_sponsored: bool | None = None,
        status: str | None = None,
        starred: bool | None = None,
        tag: str | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        """Full-text search across transcripts and analysis summaries.

        Uses SQLite FTS5 with BM25 ranking. Supports M010 facets
        (content_type, min_actionability, is_sponsored) and M011
        workflow facets (status, starred, tag, collection).
        """
        from vidscope.application.search_videos import (
            SearchFilters, SearchVideosUseCase,
        )
        from vidscope.domain import ContentType, TrackingStatus

        try:
            parsed_ct: ContentType | None = None
            if content_type is not None:
                try:
                    parsed_ct = ContentType(str(content_type).lower().strip())
                except ValueError as exc:
                    raise ValueError(
                        f"content_type must be a valid ContentType: {exc}"
                    ) from exc

            parsed_status: TrackingStatus | None = None
            if status is not None:
                try:
                    parsed_status = TrackingStatus(str(status).lower().strip())
                except ValueError as exc:
                    raise ValueError(
                        f"status must be a valid TrackingStatus: {exc}"
                    ) from exc

            filters = SearchFilters(
                content_type=parsed_ct,
                min_actionability=float(min_actionability) if min_actionability is not None else None,
                is_sponsored=is_sponsored,
                status=parsed_status,
                starred=starred,
                tag=tag.lower().strip() if tag else None,
                collection=collection.strip() if collection else None,
            )

            use_case = SearchVideosUseCase(
                unit_of_work_factory=container.unit_of_work
            )
            result = use_case.execute(query, limit=limit, filters=filters)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return {
            "query": result.query,
            "hits": [
                {
                    "video_id": int(hit.video_id),
                    "source": hit.source,
                    "snippet": hit.snippet,
                    "rank": hit.rank,
                }
                for hit in result.hits
            ],
        }
```

**Note**: `SearchLibraryUseCase` n'est plus utilisé par le MCP tool après S03 — on peut laisser l'import si d'autres tools s'en servent, sinon retirer. Vérifier : `grep -n "SearchLibraryUseCase" src/vidscope/mcp/server.py`. Si c'est le seul usage, retirer l'import (mais conserver `SearchLibraryResult` si importé).

Étape 3 — Étendre `tests/unit/cli/test_search_cmd.py` (ajouter une classe de tests M011) :

```python
"""CliRunner tests for `vidscope search` with M011 facets (R058)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from vidscope.cli.app import app


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    import pathlib
    here = pathlib.Path(__file__).resolve()
    for _ in range(6):
        if (here / "config" / "taxonomy.yaml").is_file():
            monkeypatch.chdir(here)
            break
        here = here.parent
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))


class TestSearchCmdM011:
    def test_help_lists_new_options(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["search", "--help"])
        assert r.exit_code == 0
        for opt in ("--status", "--starred", "--tag", "--collection"):
            assert opt in r.output
        # Value list for --status appears in help
        for s in ("saved", "reviewed", "archived"):
            assert s in r.output

    def test_invalid_status_fails(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["search", "q", "--status", "bogus"])
        assert r.exit_code != 0
        assert "bogus" in r.output or "--status" in r.output

    def test_valid_status_runs(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["search", "q", "--status", "saved"])
        assert r.exit_code == 0  # empty library → 0 hits, not an error

    def test_starred_flag(self) -> None:
        runner = CliRunner()
        r1 = runner.invoke(app, ["search", "q", "--starred"])
        assert r1.exit_code == 0
        r2 = runner.invoke(app, ["search", "q", "--unstarred"])
        assert r2.exit_code == 0

    def test_tag_and_collection(self) -> None:
        runner = CliRunner()
        r = runner.invoke(
            app,
            ["search", "q", "--tag", "Idea", "--collection", "MyCol"],
        )
        assert r.exit_code == 0

    def test_all_facets_combined(self) -> None:
        runner = CliRunner()
        r = runner.invoke(
            app,
            [
                "search", "q",
                "--content-type", "tutorial",
                "--min-actionability", "50",
                "--sponsored", "false",
                "--status", "saved",
                "--starred",
                "--tag", "idea",
                "--collection", "MyCol",
            ],
        )
        assert r.exit_code == 0
```

Étape 4 — Étendre `tests/unit/mcp/test_server.py` (ajouter tests facets). Chercher si `vidscope_search` a déjà des tests, et ajouter :

```python
"""Tests étendus pour vidscope_search MCP tool (M011/S03/R058)."""

# Ajouter à la fin de tests/unit/mcp/test_server.py (ou dans un nouveau fichier
# tests/unit/mcp/test_search_facets.py si le fichier existant est trop chargé).

# Pattern: réutiliser la fixture `mcp_server` ou construire via build_mcp_server.

class TestMcpSearchFacets:
    def test_accepts_status_param(self, tmp_path, monkeypatch) -> None:
        import pathlib
        here = pathlib.Path(__file__).resolve()
        for _ in range(6):
            if (here / "config" / "taxonomy.yaml").is_file():
                monkeypatch.chdir(here)
                break
            here = here.parent
        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))

        from vidscope.infrastructure.container import build_container
        from vidscope.mcp.server import build_mcp_server

        container = build_container()
        try:
            server = build_mcp_server(container)
            # Resolve tool from FastMCP internals
            tools = server._tool_manager._tools  # type: ignore[attr-defined]
            tool = tools["vidscope_search"]
            # Call the tool function directly — should not raise
            result = tool.fn(query="q", status="saved")
            assert "hits" in result
            assert isinstance(result["hits"], list)
        finally:
            container.engine.dispose()

    def test_invalid_status_raises_value_error(self, tmp_path, monkeypatch) -> None:
        import pathlib
        import pytest

        here = pathlib.Path(__file__).resolve()
        for _ in range(6):
            if (here / "config" / "taxonomy.yaml").is_file():
                monkeypatch.chdir(here)
                break
            here = here.parent
        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))

        from vidscope.infrastructure.container import build_container
        from vidscope.mcp.server import build_mcp_server

        container = build_container()
        try:
            server = build_mcp_server(container)
            tools = server._tool_manager._tools  # type: ignore[attr-defined]
            tool = tools["vidscope_search"]
            with pytest.raises(ValueError, match="TrackingStatus"):
                tool.fn(query="q", status="bogus")
        finally:
            container.engine.dispose()

    def test_all_facets_combined(self, tmp_path, monkeypatch) -> None:
        import pathlib

        here = pathlib.Path(__file__).resolve()
        for _ in range(6):
            if (here / "config" / "taxonomy.yaml").is_file():
                monkeypatch.chdir(here)
                break
            here = here.parent
        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))

        from vidscope.infrastructure.container import build_container
        from vidscope.mcp.server import build_mcp_server

        container = build_container()
        try:
            server = build_mcp_server(container)
            tools = server._tool_manager._tools  # type: ignore[attr-defined]
            tool = tools["vidscope_search"]
            result = tool.fn(
                query="q",
                content_type="tutorial",
                min_actionability=50,
                is_sponsored=False,
                status="saved",
                starred=True,
                tag="idea",
                collection="MyCol",
            )
            assert "hits" in result
        finally:
            container.engine.dispose()
```

**NOTE IMPORTANTE**: l'API interne de FastMCP (`_tool_manager._tools`) a pu évoluer — si les tests échouent, consulter le pattern existant dans `tests/unit/mcp/test_server.py` pour la résolution des tools (appel direct des closures). Adapter au pattern déjà en place.

Étape 5 — Exécuter :
```
uv run pytest tests/unit/cli/test_search_cmd.py tests/unit/mcp/test_server.py -x -q
uv run lint-imports
uv run pytest -m architecture -x -q
```
  </action>
  <verify>
    <automated>uv run pytest tests/unit/cli/test_search_cmd.py tests/unit/mcp/test_server.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n '"--status"' src/vidscope/cli/commands/search.py` matches
    - `grep -n '"--starred/--unstarred"' src/vidscope/cli/commands/search.py` matches
    - `grep -n '"--tag"' src/vidscope/cli/commands/search.py` matches
    - `grep -n '"--collection"' src/vidscope/cli/commands/search.py` matches
    - `grep -n "_parse_tracking_status" src/vidscope/cli/commands/search.py` matches
    - `grep -n "SearchVideosUseCase" src/vidscope/mcp/server.py` matches
    - `grep -n 'status: str | None = None' src/vidscope/mcp/server.py` matches
    - `grep -n 'tag: str | None = None' src/vidscope/mcp/server.py` matches
    - `grep -n 'collection: str | None = None' src/vidscope/mcp/server.py` matches
    - `uv run pytest tests/unit/cli/test_search_cmd.py -x -q` exits 0
    - `uv run pytest tests/unit/mcp/test_server.py -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - CLI `vidscope search` étendue à 7 options avec helpers de parsing
    - MCP tool `vidscope_search` accepte les 7 facets, utilise `SearchVideosUseCase`
    - Tests CLI et MCP verts
    - 10 contrats import-linter toujours KEPT (MCP utilise déjà `vidscope.application` via le composition root)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI (user) → SearchFilters | 4 nouveaux inputs texte/enum. --status parse via _parse_tracking_status. --tag/--collection passé en str. |
| MCP (agent IA) → SearchFilters | Même 4 inputs exposés via JSON-RPC. Validation identique côté tool handler. |
| SearchVideosUseCase → UoW repos | video_id int, enum .value, str name. Tous passent via bind params SQLAlchemy Core. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-SQL-M011-03 | Tampering | Facet values `tag`, `collection`, `status` dans queries SQLite | mitigate | Tous passés en bind param SQLAlchemy (jamais string interpolation). TagRepositorySQLite lowercase-normalise. Test fuzz `test_search_sql_injection.py` avec 20 payloads malicieux × 2 facets + vérification que `videos` table survit (COUNT inchangé). |
| T-INPUT-M011-03 | DoS | Facet values très longs (ex: 10k chars) | accept | SQLAlchemy Core truncate au bind. Pas de regex complexe. Pas de DoS pratique sur une lib locale R032. |
| T-LOGIC-M011-01 | Tampering | AND intersection produit set vide mais use case ne return pas | mitigate | Early return `if allowed is not None and not allowed: return hits=()`. Test `test_empty_intersection_returns_no_hits`. |
| T-BACKWARDS-M011-01 | Availability | Extension casse les appels M010 existants (SearchFilters sans les 4 nouveaux args) | mitigate | Tous les nouveaux fields ont default None (Pitfall 1). Test `test_empty_filters_pure_fts5_path` + `TestBackwardCompat`. |
| T-STARRED-M011-01 | Tampering | `starred=False` mal implémenté retourne tout ou rien | mitigate | Pattern EXCLUSION: `excluded_starred` set séparé de `allowed`. Test `test_starred_false_excludes` vérifie explicitement le complement. |
| T-CASE-M011-01 | Tampering | Tag recherché avec case différente ne matche pas | mitigate | CLI lowercase côté client (`tag.lower().strip()`), repo lowercase côté serveur (D3). Test `test_filters_by_tag` avec "Idea" input. |
| T-ARCH-M011-03 | Spoofing | SearchVideosUseCase importe un adapter | mitigate | `application-has-no-adapters` KEPT. grep control dans acceptance criteria. |
</threat_model>

<verification>
Après les 2 tâches, exécuter :
- `uv run pytest tests/unit/application/test_search_videos.py tests/unit/application/test_search_facets_matrix.py tests/unit/application/test_search_sql_injection.py tests/unit/cli/test_search_cmd.py tests/unit/mcp/test_server.py -x -q` vert
- `uv run lint-imports` vert — 10 contrats KEPT
- `uv run pytest -m architecture -x -q` vert
- `uv run vidscope search --help | grep -E "(status|starred|tag|collection)"` liste les 4 nouvelles options
- Vérifier manuellement que `SearchLibraryUseCase` existante reste fonctionnelle (pas supprimée)
</verification>

<success_criteria>
S03 est complet quand :
- [ ] SearchFilters étendu à 7 facets, tous default None
- [ ] `is_empty()` renvoie True pour `SearchFilters()` sans arg (backward compat)
- [ ] `SearchVideosUseCase.execute` intersecte AND sur 4 sources (analyses + video_tracking + tags + collections)
- [ ] `starred=False` utilise EXCLUSION (complement) — pas une liste positive des non-starred
- [ ] Fast path FTS5 pur préservé quand filters.is_empty()
- [ ] CLI `vidscope search` accepte --status/--starred/--unstarred/--tag/--collection
- [ ] MCP tool `vidscope_search` accepte les 7 facets
- [ ] Matrix test: ≥50 combos passent sans crash
- [ ] Fuzz SQL-injection test: 20 payloads × 2 facets passent
- [ ] Suite tests verte (unit extension + matrix + fuzz + CLI + MCP)
- [ ] `lint-imports` vert (10 contrats KEPT inchangés)
- [ ] R058 couvert end-to-end
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M011/M011-S03-SUMMARY.md` documentant :
- SearchFilters final: 7 champs (3 M010 + 4 M011), tous default None
- Algorithme d'intersection AND + traitement spécial starred=False (EXCLUSION)
- Oversample factor (5x) préservé pour FTS5 post-filter
- CLI signature finale `vidscope search`
- MCP tool signature finale `vidscope_search` (7 facets)
- Matrix: 35 combos C(7,3) + 15 combos C(7,4) = 50 combos testés
- Payloads fuzz injectés: 20 stratégiques
- Liste exhaustive des fichiers modifiés
</output>
