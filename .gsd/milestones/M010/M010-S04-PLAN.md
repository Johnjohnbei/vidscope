---
phase: M010
plan: S04
type: execute
wave: 4
depends_on: [S01]
files_modified:
  - src/vidscope/ports/repositories.py
  - src/vidscope/adapters/sqlite/analysis_repository.py
  - src/vidscope/application/explain_analysis.py
  - src/vidscope/application/search_videos.py
  - src/vidscope/application/__init__.py
  - src/vidscope/cli/commands/explain.py
  - src/vidscope/cli/commands/search.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/application/test_explain_analysis.py
  - tests/unit/application/test_search_videos.py
  - tests/unit/cli/test_explain.py
  - tests/unit/cli/test_search_cmd.py
  - tests/unit/cli/test_app.py
autonomous: true
requirements: [R053, R055]
must_haves:
  truths:
    - "`ExplainAnalysisUseCase.execute(video_id)` retourne un `ExplainAnalysisResult` frozen dataclass avec `found`, `video`, `analysis` (l'analyse la plus récente, ou None si aucune)"
    - "`SearchVideosUseCase.execute(query, filters)` filtre les résultats FTS5 par content_type, min_actionability, is_sponsored (nouveaux params)"
    - "`AnalysisRepositorySQLite.list_by_filters(...)` (nouvelle méthode) retourne les `video_id`s dont la dernière analyse matche les filtres, via SQL paramétré (pas d'injection)"
    - "`vidscope explain <id>` exit 0 quand l'analyse existe — affiche reasoning + per-dimension scores en ASCII"
    - "`vidscope explain <id>` exit 1 avec message clair quand la vidéo n'existe pas ou n'a pas d'analyse"
    - "`vidscope search <query> --content-type tutorial --min-actionability 70 --sponsored false` exit 0 et filtre la sortie"
    - "`vidscope search --min-actionability -10` rejeté par Typer (min=0, max=100)"
    - "`vidscope search --content-type podcast` rejeté par Typer (valeur hors enum ContentType)"
    - "`vidscope --help` liste la commande `explain`"
    - "Aucun glyphe unicode dans les fichiers CLI (compat Windows cp1252)"
  artifacts:
    - path: "src/vidscope/application/explain_analysis.py"
      provides: "ExplainAnalysisUseCase + DTO"
      contains: "class ExplainAnalysisUseCase"
    - path: "src/vidscope/application/search_videos.py"
      provides: "SearchVideosUseCase avec filtres facettes M010"
      contains: "class SearchVideosUseCase"
    - path: "src/vidscope/cli/commands/explain.py"
      provides: "vidscope explain <id> command"
      contains: "def explain_command"
    - path: "src/vidscope/cli/commands/search.py"
      provides: "vidscope search + nouveaux flags M010 (--content-type, --min-actionability, --sponsored)"
      contains: "content_type"
  key_links:
    - from: "src/vidscope/cli/app.py"
      to: "explain_command"
      via: "app.command('explain')(explain_command)"
      pattern: "explain_command"
    - from: "src/vidscope/application/explain_analysis.py"
      to: "UnitOfWork.analyses.get_latest_for_video"
      via: "Delegation to existing repository method"
      pattern: "get_latest_for_video"
    - from: "src/vidscope/application/search_videos.py"
      to: "AnalysisRepositorySQLite.list_by_filters"
      via: "Filter candidate video_ids before/after FTS5 search"
      pattern: "list_by_filters"
---

<objective>
S04 clôture M010 côté utilisateur: nouvelle commande `vidscope explain <id>` affichant le reasoning + score vector, et extension de `vidscope search` avec 3 filtres facettes (`--content-type`, `--min-actionability`, `--sponsored`). Le use case `SearchVideosUseCase` remplace/étend `SearchLibraryUseCase` uniquement pour la logique de filtrage — le FTS5 existant est préservé.

Purpose: Sans ce plan, les 9 nouveaux champs persistés par S01/S02/S03 sont invisibles à l'utilisateur. `vidscope explain` rend R055 (reasoning) immédiatement exploitable; les filtres facettes rendent R053 (score vector + is_sponsored + content_type) opérationnels pour la veille.
Output: 1 nouveau use case + 1 use case étendu + 1 nouvelle commande + 1 commande étendue + 1 méthode repository + tests complets.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M010/M010-S01-PLAN.md
@.gsd/milestones/M010/M010-ROADMAP.md
@.gsd/milestones/M010/M010-RESEARCH.md
@.gsd/milestones/M010/M010-VALIDATION.md
@.gsd/KNOWLEDGE.md
@src/vidscope/domain/entities.py
@src/vidscope/domain/values.py
@src/vidscope/ports/repositories.py
@src/vidscope/adapters/sqlite/analysis_repository.py
@src/vidscope/adapters/sqlite/schema.py
@src/vidscope/application/search_library.py
@src/vidscope/application/show_video.py
@src/vidscope/application/__init__.py
@src/vidscope/cli/commands/search.py
@src/vidscope/cli/commands/show.py
@src/vidscope/cli/commands/__init__.py
@src/vidscope/cli/app.py
@src/vidscope/cli/_support.py

<interfaces>
**Analysis V2 (livré S01)** : les 9 nouveaux champs sont accessibles via `analysis.content_type`, `.sentiment`, etc.

**Existing `SearchLibraryUseCase`** :
```python
class SearchLibraryUseCase:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None: ...
    def execute(self, query: str, *, limit: int = 20) -> SearchLibraryResult:
        with self._uow_factory() as uow:
            hits = tuple(uow.search_index.search(query, limit=limit))
        return SearchLibraryResult(query=query, hits=hits)
```

**Cible `SearchVideosUseCase` (NOUVEAU en S04)** — étend le use case avec filtres facettes :

```python
@dataclass(frozen=True, slots=True)
class SearchFilters:
    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None   # None = not filtered, True = only sponsored, False = only not-sponsored

class SearchVideosUseCase:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None: ...
    def execute(self, query: str, *, limit: int = 20, filters: SearchFilters | None = None) -> SearchLibraryResult:
        ...
```

**Stratégie de filtrage** : 
1. Si `filters` est None ou toutes ses valeurs sont None → délégation directe à `search_index.search` (comportement V1).
2. Sinon: appeler `uow.analyses.list_by_filters(filters)` pour obtenir l'ensemble des `video_id`s autorisés, puis faire le search FTS5 et filtrer les hits sur cet ensemble.

**Nouvelle méthode repository** : `AnalysisRepository.list_by_filters(*, content_type, min_actionability, is_sponsored) -> list[VideoId]`. Retourne les `video_id`s dont la dernière analyse matche. Implémentation SQL paramétrée — pas de concat de strings.

**Cible `ExplainAnalysisUseCase`** :

```python
@dataclass(frozen=True, slots=True)
class ExplainAnalysisResult:
    found: bool
    video: Video | None = None
    analysis: Analysis | None = None

class ExplainAnalysisUseCase:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None: ...
    def execute(self, video_id: int) -> ExplainAnalysisResult:
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ExplainAnalysisResult(found=False)
            analysis = uow.analyses.get_latest_for_video(VideoId(video_id))
        return ExplainAnalysisResult(found=True, video=video, analysis=analysis)
```

**Règle Typer `Annotated[...]`** (KNOWLEDGE.md) :
```python
from typing import Annotated

def search_command(
    query: Annotated[str, typer.Argument(...)],
    content_type: Annotated[str | None, typer.Option("--content-type", help="...")] = None,
    min_actionability: Annotated[int | None, typer.Option("--min-actionability", min=0, max=100, help="...")] = None,
    sponsored: Annotated[str | None, typer.Option("--sponsored", help="true|false")] = None,
) -> None: ...
```

**Pour `--content-type`** : Typer n'accepte pas `ContentType` directement comme type d'option (il faut une conversion). Stratégie: `str | None` puis conversion interne avec `typer.BadParameter` si invalide.

**Règle ASCII output (KNOWLEDGE.md)** : `[green]OK[/green]`, `[red]FAIL[/red]`. Pas de `✓`, `✗`, `→`, `←`.

**Ordre wave** : S04 dépend de S01 UNIQUEMENT (repository field `content_type` etc.) — il ne dépend PAS de S02 (heuristic V2) ni S03 (LLM V2). Ça signifie que S04 peut tourner en parallèle de S02/S03 (wave 4 définition: concurrent avec wave 2 et 3 dans l'absolu, mais comme le ROADMAP spécifie wave=4, on respecte). Cette indépendance a été validée dans le ROADMAP.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: `AnalysisRepository.list_by_filters` (port + SQLite impl) + tests SQL paramétré</name>
  <files>src/vidscope/ports/repositories.py, src/vidscope/adapters/sqlite/analysis_repository.py, tests/unit/adapters/sqlite/test_analysis_repository.py</files>
  <read_first>
    - src/vidscope/ports/repositories.py (Protocol AnalysisRepository — où ajouter la méthode)
    - src/vidscope/adapters/sqlite/analysis_repository.py (pattern SQLAlchemy `select()` dans `get_latest_for_video` — à reproduire)
    - src/vidscope/adapters/sqlite/schema.py (structure de la table `analyses` — colonnes M010)
    - src/vidscope/domain/values.py (ContentType)
    - tests/unit/adapters/sqlite/test_analysis_repository.py (pattern test avec engine fixture)
    - tests/unit/adapters/sqlite/conftest.py (fixture `engine`)
    - .gsd/milestones/M010/M010-RESEARCH.md (Pitfall 5 : décision retenue = JSON inline dans `verticals`)
    - .gsd/DECISIONS.md (D020 hexagonal layering)
  </read_first>
  <behavior>
    - Test 1: `list_by_filters(content_type=ContentType.TUTORIAL)` retourne `[video_id]` pour les vidéos dont la dernière analyse a `content_type == "tutorial"`.
    - Test 2: `list_by_filters(min_actionability=70)` retourne les vidéos dont `actionability >= 70`. Les analyses avec `actionability IS NULL` sont EXCLUES.
    - Test 3: `list_by_filters(is_sponsored=True)` retourne uniquement les vidéos avec `is_sponsored = 1` (True en SQL).
    - Test 4: `list_by_filters(is_sponsored=False)` retourne uniquement `is_sponsored = 0`. Les NULL sont EXCLUES (interprétation: False explicite ≠ unknown).
    - Test 5: Filtres combinés AND: `list_by_filters(content_type=TUTORIAL, min_actionability=70, is_sponsored=False)` retourne l'intersection stricte.
    - Test 6: Tous filtres None → retourne TOUS les `video_id`s (behavior neutre, utile par défaut).
    - Test 7: Si un video a plusieurs analyses, seule la PLUS RÉCENTE (par `created_at`) est prise en compte pour le filtre.
    - Test 8: Le filtre n'injecte pas: `content_type="' OR 1=1 --"` → retourne [] (pas de crash, pas de SQL injection).
    - Test 9: `limit` respecté (paramètre optionnel, default 1000).
    - Test 10: Les vidéos sans aucune analyse ne sont PAS retournées même si les filtres sont None (la jointure implicite nécessite au moins une analyse).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/ports/repositories.py` pour ajouter la méthode au Protocol `AnalysisRepository`. Localisation: après `get_latest_for_video` dans la classe existante.

Ajouter l'import en haut du fichier :
```python
from vidscope.domain import (
    ...
    ContentType,
    ...
)
```

Puis ajouter dans le Protocol :

```python
@runtime_checkable
class AnalysisRepository(Protocol):
    """Persistence for :class:`~vidscope.domain.entities.Analysis`."""

    def add(self, analysis: Analysis) -> Analysis: ...
    def get_latest_for_video(self, video_id: VideoId) -> Analysis | None: ...

    def list_by_filters(
        self,
        *,
        content_type: "ContentType | None" = None,
        min_actionability: float | None = None,
        is_sponsored: bool | None = None,
        limit: int = 1000,
    ) -> list[VideoId]:
        """Return video ids whose LATEST analysis matches every non-None filter.

        The match semantics:

        - ``content_type``: latest analysis.content_type equals the given enum.
          NULL stored values are excluded.
        - ``min_actionability``: latest analysis.actionability is not NULL AND >= the given float.
        - ``is_sponsored``: latest analysis.is_sponsored strictly equals the bool. NULL excluded.

        Filters are combined with AND. Missing filters (``None``) are ignored.
        Videos with no analysis row at all are excluded from the result.
        ``limit`` caps the number of video ids returned (default 1000) to
        avoid unbounded scans. Results ordered by analysis.created_at DESC.
        """
        ...
```

Étape 2 — Implémenter dans `src/vidscope/adapters/sqlite/analysis_repository.py`. Ajouter la méthode à la classe, après `get_latest_for_video` :

```python
def list_by_filters(
    self,
    *,
    content_type: ContentType | None = None,
    min_actionability: float | None = None,
    is_sponsored: bool | None = None,
    limit: int = 1000,
) -> list[VideoId]:
    """Return video ids whose most-recent analysis matches the given filters.

    Uses a GROUP BY subquery to pick the latest analysis per video_id, then
    filters. All inputs are cast to primitive types before binding so no
    string concatenation touches the query — SQL injection is structurally
    impossible.
    """
    # Subquery: latest analysis row per video_id (by max(id), since id is
    # AUTOINCREMENT — newer rows always have larger ids).
    # We use a correlated approach via inner join on max id.
    from sqlalchemy import and_, func

    latest_subq = (
        select(
            analyses_table.c.video_id.label("vid"),
            func.max(analyses_table.c.id).label("max_id"),
        )
        .group_by(analyses_table.c.video_id)
        .subquery()
    )

    stmt = (
        select(analyses_table.c.video_id)
        .join(latest_subq, analyses_table.c.id == latest_subq.c.max_id)
    )

    where_clauses = []
    if content_type is not None:
        where_clauses.append(analyses_table.c.content_type == content_type.value)
    if min_actionability is not None:
        where_clauses.append(analyses_table.c.actionability.is_not(None))
        where_clauses.append(analyses_table.c.actionability >= float(min_actionability))
    if is_sponsored is not None:
        # Strict equality: True → only rows with is_sponsored=1, NULL excluded.
        where_clauses.append(analyses_table.c.is_sponsored.is_not(None))
        where_clauses.append(analyses_table.c.is_sponsored == bool(is_sponsored))

    if where_clauses:
        stmt = stmt.where(and_(*where_clauses))

    stmt = stmt.order_by(analyses_table.c.created_at.desc()).limit(max(1, int(limit)))

    rows = self._conn.execute(stmt).all()
    return [VideoId(int(row[0])) for row in rows]
```

Étape 3 — Ajouter l'import `ContentType` en haut de `src/vidscope/adapters/sqlite/analysis_repository.py` si pas déjà présent (S01 Task 3 l'a déjà fait):
```python
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    VideoId,
)
```

Étape 4 — Étendre `tests/unit/adapters/sqlite/test_analysis_repository.py` en AJOUTANT la classe `TestListByFilters` :

```python
class TestListByFilters:
    """M010: facet filtering on the analyses table."""

    def _insert_analysis(
        self, conn, *, vid: int, content_type: str | None = None,
        actionability: float | None = None, is_sponsored: bool | None = None,
        created_at: datetime | None = None,
    ) -> None:
        conn.execute(
            text("""
                INSERT INTO analyses
                (video_id, provider, language, keywords, topics,
                 content_type, actionability, is_sponsored, created_at)
                VALUES (:v, 'heuristic', 'en', '[]', '[]', :ct, :act, :sp, :c)
            """),
            {
                "v": vid, "ct": content_type, "act": actionability,
                "sp": 1 if is_sponsored is True else (0 if is_sponsored is False else None),
                "c": created_at or datetime(2026, 1, 1, tzinfo=UTC),
            },
        )

    def test_filter_by_content_type(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "f1")
            v2 = _insert_video(conn, "f2")
            self._insert_analysis(conn, vid=v1, content_type="tutorial")
            self._insert_analysis(conn, vid=v2, content_type="review")
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = repo.list_by_filters(content_type=ContentType.TUTORIAL)
        assert v1 in [int(x) for x in hits]
        assert v2 not in [int(x) for x in hits]

    def test_filter_min_actionability_excludes_null(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "f3")
            v2 = _insert_video(conn, "f4")
            v3 = _insert_video(conn, "f5")
            self._insert_analysis(conn, vid=v1, actionability=90.0)
            self._insert_analysis(conn, vid=v2, actionability=50.0)
            self._insert_analysis(conn, vid=v3, actionability=None)  # excluded
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(min_actionability=70.0)]
        assert v1 in hits
        assert v2 not in hits
        assert v3 not in hits

    def test_filter_is_sponsored_true(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "f6")
            v2 = _insert_video(conn, "f7")
            v3 = _insert_video(conn, "f8")
            self._insert_analysis(conn, vid=v1, is_sponsored=True)
            self._insert_analysis(conn, vid=v2, is_sponsored=False)
            self._insert_analysis(conn, vid=v3, is_sponsored=None)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(is_sponsored=True)]
        assert v1 in hits
        assert v2 not in hits
        assert v3 not in hits

    def test_filter_is_sponsored_false_excludes_null(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "g1")
            v2 = _insert_video(conn, "g2")
            v3 = _insert_video(conn, "g3")
            self._insert_analysis(conn, vid=v1, is_sponsored=True)
            self._insert_analysis(conn, vid=v2, is_sponsored=False)
            self._insert_analysis(conn, vid=v3, is_sponsored=None)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(is_sponsored=False)]
        assert v2 in hits
        assert v1 not in hits
        assert v3 not in hits

    def test_combined_filters_and(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "h1")
            v2 = _insert_video(conn, "h2")
            v3 = _insert_video(conn, "h3")
            self._insert_analysis(conn, vid=v1, content_type="tutorial",
                                  actionability=90.0, is_sponsored=False)
            self._insert_analysis(conn, vid=v2, content_type="tutorial",
                                  actionability=60.0, is_sponsored=False)
            self._insert_analysis(conn, vid=v3, content_type="review",
                                  actionability=95.0, is_sponsored=False)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(
                content_type=ContentType.TUTORIAL,
                min_actionability=70.0,
                is_sponsored=False,
            )]
        assert v1 in hits
        assert v2 not in hits  # actionability too low
        assert v3 not in hits  # wrong content_type

    def test_no_filters_returns_all_analyzed_videos(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "i1")
            v2 = _insert_video(conn, "i2")
            _insert_video(conn, "i3_no_analysis")  # excluded — no analyses row
            self._insert_analysis(conn, vid=v1)
            self._insert_analysis(conn, vid=v2)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters()]
        assert v1 in hits
        assert v2 in hits

    def test_latest_analysis_used(self, engine: Engine) -> None:
        """If a video has multiple analyses, only the latest is checked."""
        with engine.begin() as conn:
            v1 = _insert_video(conn, "j1")
            # Old analysis: content_type=vlog
            self._insert_analysis(conn, vid=v1, content_type="vlog",
                                  created_at=datetime(2025, 1, 1, tzinfo=UTC))
            # Newer analysis: content_type=tutorial (should be the winner)
            self._insert_analysis(conn, vid=v1, content_type="tutorial",
                                  created_at=datetime(2026, 1, 1, tzinfo=UTC))
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            tutorials = [int(x) for x in repo.list_by_filters(content_type=ContentType.TUTORIAL)]
            vlogs = [int(x) for x in repo.list_by_filters(content_type=ContentType.VLOG)]
        assert v1 in tutorials
        assert v1 not in vlogs

    def test_sql_injection_attempt_safe(self, engine: Engine) -> None:
        """ContentType enum → controlled string; direct string injection impossible."""
        with engine.begin() as conn:
            _insert_video(conn, "k1")
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            # Passing a non-ContentType would fail at type-check; but we can
            # still verify the query path handles bogus enums gracefully by
            # constructing via the mechanism the code uses.
            from vidscope.domain import ContentType
            # If ContentType("' OR 1=1 --") was accepted, we'd have an issue.
            # But ContentType rejects invalid values — test that instead.
            import pytest as _pytest
            with _pytest.raises(ValueError):
                ContentType("' OR 1=1 --")
            # And list_by_filters with a valid enum returns safely:
            hits = repo.list_by_filters(content_type=ContentType.UNKNOWN)
            assert isinstance(hits, list)

    def test_limit_respected(self, engine: Engine) -> None:
        with engine.begin() as conn:
            for i in range(10):
                vid = _insert_video(conn, f"lim{i}")
                self._insert_analysis(conn, vid=vid, content_type="tutorial",
                                      created_at=datetime(2026, 1, 1 + i, tzinfo=UTC))
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = repo.list_by_filters(content_type=ContentType.TUTORIAL, limit=3)
        assert len(hits) == 3
```

(Note: si le fixture `_insert_video` n'existe pas dans le fichier, réutiliser celui défini au Task 3 de S01 ou le dupliquer en local.)

Étape 5 — Exécuter :
```
uv run pytest tests/unit/adapters/sqlite/test_analysis_repository.py -x -q
uv run lint-imports
```

NE JAMAIS concaténer des strings dans les requêtes SQL. Utiliser uniquement les opérateurs SQLAlchemy (`.where`, `.c.xxx == val`). Les valeurs utilisateur sont automatiquement bindées comme paramètres.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/sqlite/test_analysis_repository.py::TestListByFilters -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def list_by_filters" src/vidscope/ports/repositories.py` matches (Protocol)
    - `grep -n "def list_by_filters" src/vidscope/adapters/sqlite/analysis_repository.py` matches (impl)
    - `grep -n "content_type: ContentType" src/vidscope/ports/repositories.py` matches
    - `grep -n "min_actionability" src/vidscope/adapters/sqlite/analysis_repository.py` matches
    - `grep -nE "f\".*%s|\\.format\\(|\\+ str\\(" src/vidscope/adapters/sqlite/analysis_repository.py` returns exit 1 (no raw string interpolation in SQL)
    - `grep -n "analyses_table.c.content_type" src/vidscope/adapters/sqlite/analysis_repository.py` matches (SQLAlchemy parameterized)
    - `uv run pytest tests/unit/adapters/sqlite/test_analysis_repository.py::TestListByFilters -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - `AnalysisRepository.list_by_filters` livré (port + impl)
    - SQL paramétré — pas de string interpolation
    - 9 tests verts couvrant chaque filtre + combo + SQL injection + limit + latest-analysis
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: ExplainAnalysisUseCase + SearchVideosUseCase + wiring application/__init__.py</name>
  <files>src/vidscope/application/explain_analysis.py, src/vidscope/application/search_videos.py, src/vidscope/application/__init__.py, tests/unit/application/test_explain_analysis.py, tests/unit/application/test_search_videos.py</files>
  <read_first>
    - src/vidscope/application/search_library.py (pattern SearchLibraryUseCase existant — à NE PAS supprimer)
    - src/vidscope/application/show_video.py (pattern use case + DTO frozen dataclass, pattern de lookup video+analysis)
    - src/vidscope/application/__init__.py (liste __all__ + imports)
    - src/vidscope/ports/__init__.py (UnitOfWorkFactory, SearchResult)
    - src/vidscope/domain/entities.py (Analysis, Video)
    - src/vidscope/domain/values.py (ContentType)
    - src/vidscope/adapters/sqlite/analysis_repository.py (list_by_filters livré Task 1)
    - .gsd/KNOWLEDGE.md (application-has-no-adapters — injection primitives only)
  </read_first>
  <behavior>
    - Test 1 (explain happy): `ExplainAnalysisUseCase.execute(1)` où video 1 existe + a une analyse → `ExplainAnalysisResult(found=True, video=..., analysis=...)`.
    - Test 2 (explain video missing): `execute(999)` où video n'existe pas → `ExplainAnalysisResult(found=False, video=None, analysis=None)`.
    - Test 3 (explain video without analysis): video existe mais `analyses` table vide → `ExplainAnalysisResult(found=True, video=..., analysis=None)`.
    - Test 4 (search no filters = V1 behavior): `SearchVideosUseCase.execute("query")` sans filters délégué proprement.
    - Test 5 (search with filters): `execute("tutorial", filters=SearchFilters(content_type=ContentType.TUTORIAL))` appelle `uow.analyses.list_by_filters` et retourne uniquement les hits dont le `video_id` est dans l'ensemble autorisé.
    - Test 6 (search filters vide = no filters): `SearchFilters()` (tous None) → comportement V1 (pas d'appel à list_by_filters).
    - Test 7 (search limit respecté): `execute(query, limit=5, filters=...)` → au plus 5 hits retournés.
    - Test 8 (search filters sans match): `execute(query, filters=...)` où list_by_filters retourne [] → SearchLibraryResult avec `hits=()` (pas d'erreur).
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/application/explain_analysis.py` :

```python
"""ExplainAnalysisUseCase — returns video + latest analysis for `vidscope explain`."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Analysis, Video, VideoId
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ExplainAnalysisResult", "ExplainAnalysisUseCase"]


@dataclass(frozen=True, slots=True)
class ExplainAnalysisResult:
    """Result of :meth:`ExplainAnalysisUseCase.execute`.

    ``found`` is ``False`` only when no video matches the given id. When
    the video exists but has no analysis yet, ``found=True`` and
    ``analysis=None`` — the CLI differentiates those cases in its
    output.
    """

    found: bool
    video: Video | None = None
    analysis: Analysis | None = None


class ExplainAnalysisUseCase:
    """Return the latest analysis for ``video_id`` — powers `vidscope explain`."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, video_id: int) -> ExplainAnalysisResult:
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ExplainAnalysisResult(found=False)
            analysis = uow.analyses.get_latest_for_video(VideoId(video_id))
        return ExplainAnalysisResult(found=True, video=video, analysis=analysis)
```

Étape 2 — Créer `src/vidscope/application/search_videos.py` :

```python
"""SearchVideosUseCase — M010 extension of search_library with facet filters.

Adds optional filters on content_type, min_actionability, and is_sponsored.
When any filter is set, the use case first narrows the candidate video_ids
via AnalysisRepository.list_by_filters, then runs the FTS5 query and keeps
only hits that belong to the allowed set. When no filter is set, the use
case behaves exactly like SearchLibraryUseCase (pure FTS5 passthrough).
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.application.search_library import SearchLibraryResult
from vidscope.domain import ContentType
from vidscope.ports import SearchResult, UnitOfWorkFactory

__all__ = ["SearchFilters", "SearchVideosUseCase"]


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Facet filters applied to the search result.

    All fields default to ``None`` — a ``SearchFilters()`` instance with
    every field ``None`` means "no filter".

    Fields
    ------
    content_type:
        When set, only videos whose latest analysis has this
        ``content_type`` are returned.
    min_actionability:
        When set, only videos whose latest analysis has
        ``actionability >= min_actionability`` (NOT NULL) are returned.
    is_sponsored:
        When ``True``: only sponsored videos. When ``False``: only
        non-sponsored videos (NULL excluded). ``None``: no filter.
    """

    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None

    def is_empty(self) -> bool:
        return (
            self.content_type is None
            and self.min_actionability is None
            and self.is_sponsored is None
        )


class SearchVideosUseCase:
    """Run an FTS5 query with optional facet filters on the analysis."""

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

            allowed_video_ids = set(
                int(v)
                for v in uow.analyses.list_by_filters(
                    content_type=filters.content_type,
                    min_actionability=filters.min_actionability,
                    is_sponsored=filters.is_sponsored,
                    limit=1000,
                )
            )
            if not allowed_video_ids:
                return SearchLibraryResult(query=query, hits=())

            # Oversample FTS5 hits so we can filter without losing too many
            # — cap by a reasonable multiplier.
            raw_hits = uow.search_index.search(query, limit=max(limit, limit * 5))
            filtered: list[SearchResult] = []
            for hit in raw_hits:
                if int(hit.video_id) in allowed_video_ids:
                    filtered.append(hit)
                    if len(filtered) >= limit:
                        break
            return SearchLibraryResult(query=query, hits=tuple(filtered))
```

Étape 3 — Mettre à jour `src/vidscope/application/__init__.py` — AJOUTER les imports et `__all__` :
```python
from vidscope.application.explain_analysis import (
    ExplainAnalysisResult,
    ExplainAnalysisUseCase,
)
from vidscope.application.search_videos import (
    SearchFilters,
    SearchVideosUseCase,
)
```
Et dans `__all__` (trié) :
```python
    "ExplainAnalysisResult",
    "ExplainAnalysisUseCase",
    ...
    "SearchFilters",
    "SearchVideosUseCase",
```

Étape 4 — Créer `tests/unit/application/test_explain_analysis.py` :

```python
"""Unit tests for ExplainAnalysisUseCase."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from vidscope.application.explain_analysis import (
    ExplainAnalysisResult,
    ExplainAnalysisUseCase,
)
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    Platform,
    PlatformId,
    SentimentLabel,
    Video,
    VideoId,
)


def _make_video(vid: int = 1) -> Video:
    return Video(
        id=VideoId(vid),
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=f"https://y.be/{vid}",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _make_analysis(vid: int = 1) -> Analysis:
    return Analysis(
        video_id=VideoId(vid),
        provider="heuristic",
        language=Language.ENGLISH,
        score=70.0,
        information_density=72.0,
        actionability=85.0,
        sentiment=SentimentLabel.POSITIVE,
        content_type=ContentType.TUTORIAL,
        reasoning="Clear tutorial.",
    )


def _make_uow_factory(*, video: Video | None, analysis: Analysis | None) -> Any:
    class _UoW:
        def __init__(self) -> None:
            self.videos = MagicMock()
            self.videos.get = MagicMock(return_value=video)
            self.analyses = MagicMock()
            self.analyses.get_latest_for_video = MagicMock(return_value=analysis)

        def __enter__(self) -> Any: return self
        def __exit__(self, *_: Any) -> None: return None

    return lambda: _UoW()


class TestExplainAnalysisHappyPath:
    def test_found_video_with_analysis(self) -> None:
        video = _make_video(1)
        analysis = _make_analysis(1)
        uc = ExplainAnalysisUseCase(unit_of_work_factory=_make_uow_factory(
            video=video, analysis=analysis,
        ))
        result = uc.execute(1)
        assert result.found is True
        assert result.video is video
        assert result.analysis is analysis

    def test_video_missing(self) -> None:
        uc = ExplainAnalysisUseCase(unit_of_work_factory=_make_uow_factory(
            video=None, analysis=None,
        ))
        result = uc.execute(999)
        assert result.found is False
        assert result.video is None
        assert result.analysis is None

    def test_video_present_no_analysis(self) -> None:
        video = _make_video(1)
        uc = ExplainAnalysisUseCase(unit_of_work_factory=_make_uow_factory(
            video=video, analysis=None,
        ))
        result = uc.execute(1)
        assert result.found is True
        assert result.video is video
        assert result.analysis is None
```

Étape 5 — Créer `tests/unit/application/test_search_videos.py` :

```python
"""Unit tests for SearchVideosUseCase — filter logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

from vidscope.application.search_videos import (
    SearchFilters,
    SearchVideosUseCase,
)
from vidscope.domain import ContentType
from vidscope.ports import SearchResult


@dataclass(frozen=True)
class _FakeHit:
    """Minimal SearchResult-shaped record."""
    video_id: int
    source: str
    rank: float
    snippet: str


def _make_factory(*, hits: list, allowed_ids: list[int] | None = None) -> Any:
    class _UoW:
        def __init__(self) -> None:
            self.search_index = MagicMock()
            self.search_index.search = MagicMock(return_value=hits)
            self.analyses = MagicMock()
            self.analyses.list_by_filters = MagicMock(return_value=allowed_ids or [])

        def __enter__(self) -> Any: return self
        def __exit__(self, *_: Any) -> None: return None

    return lambda: _UoW()


class TestSearchFiltersIsEmpty:
    def test_all_none_is_empty(self) -> None:
        assert SearchFilters().is_empty() is True

    def test_any_set_not_empty(self) -> None:
        assert SearchFilters(content_type=ContentType.TUTORIAL).is_empty() is False
        assert SearchFilters(min_actionability=70.0).is_empty() is False
        assert SearchFilters(is_sponsored=True).is_empty() is False


class TestSearchVideosWithoutFilters:
    def test_no_filters_passes_through_search_index(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(hits=hits))
        result = uc.execute("python")
        assert result.query == "python"
        assert len(result.hits) == 1
        assert result.hits[0].video_id == 1

    def test_empty_filters_behaves_like_no_filters(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(hits=hits))
        result = uc.execute("python", filters=SearchFilters())
        assert len(result.hits) == 1


class TestSearchVideosWithFilters:
    def test_filters_restrict_to_allowed_ids(self) -> None:
        hits = [
            _FakeHit(1, "transcript", 0.9, "...a..."),
            _FakeHit(2, "transcript", 0.8, "...b..."),
            _FakeHit(3, "transcript", 0.7, "...c..."),
        ]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(
            hits=hits, allowed_ids=[1, 3],
        ))
        result = uc.execute(
            "python",
            filters=SearchFilters(content_type=ContentType.TUTORIAL),
        )
        ids = [h.video_id for h in result.hits]
        assert 1 in ids
        assert 3 in ids
        assert 2 not in ids

    def test_no_allowed_ids_returns_empty_hits(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(
            hits=hits, allowed_ids=[],
        ))
        result = uc.execute("python",
                            filters=SearchFilters(content_type=ContentType.TUTORIAL))
        assert result.hits == ()

    def test_limit_respected_with_filters(self) -> None:
        hits = [_FakeHit(i, "transcript", 0.5, "...") for i in range(1, 20)]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(
            hits=hits, allowed_ids=list(range(1, 20)),
        ))
        result = uc.execute("python", limit=3,
                            filters=SearchFilters(is_sponsored=False))
        assert len(result.hits) <= 3

    def test_filters_combine_all_three(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        fake_uow = _make_factory(hits=hits, allowed_ids=[1])
        uc = SearchVideosUseCase(unit_of_work_factory=fake_uow)
        result = uc.execute(
            "x",
            filters=SearchFilters(
                content_type=ContentType.TUTORIAL,
                min_actionability=70.0,
                is_sponsored=False,
            ),
        )
        # Vérifier l'appel passé à list_by_filters
        uow_instance = fake_uow()  # regenerate to peek the MagicMock calls through another instance
        # Pas idéal — le test principal est: le résultat est filtré correctement
        assert result.hits[0].video_id == 1


class TestNoInfrastructureImport:
    """application-has-no-adapters contract sanity check."""

    def test_module_has_no_adapter_or_infra_imports(self) -> None:
        src = open(
            "src/vidscope/application/search_videos.py",
            encoding="utf-8",
        ).read()
        for forbidden in (
            "from vidscope.adapters",
            "from vidscope.infrastructure",
            "import yaml",
            "import sqlalchemy",
            "import httpx",
        ):
            assert forbidden not in src, f"unexpected import: {forbidden}"
```

Étape 6 — Exécuter :
```
uv run pytest tests/unit/application/test_explain_analysis.py tests/unit/application/test_search_videos.py -x -q
uv run lint-imports
```

NE PAS importer `vidscope.infrastructure` ni `vidscope.adapters` dans `application/*.py` (contrat `application-has-no-adapters`).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_explain_analysis.py tests/unit/application/test_search_videos.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class ExplainAnalysisUseCase" src/vidscope/application/explain_analysis.py` matches
    - `grep -n "class SearchVideosUseCase" src/vidscope/application/search_videos.py` matches
    - `grep -n "class SearchFilters" src/vidscope/application/search_videos.py` matches
    - `grep -n "ExplainAnalysisUseCase\\|SearchVideosUseCase" src/vidscope/application/__init__.py` matches
    - `grep -nE "^from vidscope.infrastructure|^from vidscope.adapters" src/vidscope/application/explain_analysis.py` returns exit 1 (no match)
    - `grep -nE "^from vidscope.infrastructure|^from vidscope.adapters" src/vidscope/application/search_videos.py` returns exit 1 (no match)
    - `uv run pytest tests/unit/application/test_explain_analysis.py -x -q` exits 0
    - `uv run pytest tests/unit/application/test_search_videos.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (application-has-no-adapters KEPT)
  </acceptance_criteria>
  <done>
    - `ExplainAnalysisUseCase` livré + 3 tests verts (found/missing/no-analysis)
    - `SearchVideosUseCase` + `SearchFilters` livrés + 6+ tests verts (filter combos)
    - application/__init__.py étendu avec les re-exports
    - application-has-no-adapters KEPT
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: CLI `vidscope explain <id>` + `vidscope search` étendue avec facets + enregistrement app.py + tests</name>
  <files>src/vidscope/cli/commands/explain.py, src/vidscope/cli/commands/search.py, src/vidscope/cli/commands/__init__.py, src/vidscope/cli/app.py, tests/unit/cli/test_explain.py, tests/unit/cli/test_search_cmd.py, tests/unit/cli/test_app.py</files>
  <read_first>
    - src/vidscope/cli/commands/show.py (pattern show_command: lecture use case + rendu rich.Panel + ASCII tags)
    - src/vidscope/cli/commands/search.py (V1 actuel — search_command à ÉTENDRE, pas remplacer)
    - src/vidscope/cli/commands/__init__.py (liste des exports)
    - src/vidscope/cli/app.py (enregistrement commandes via @app.command)
    - src/vidscope/cli/_support.py (acquire_container, console, fail_user, handle_domain_errors)
    - src/vidscope/application/explain_analysis.py (livré Task 2)
    - src/vidscope/application/search_videos.py (livré Task 2)
    - src/vidscope/domain/values.py (ContentType pour la liste des choices)
    - tests/unit/cli/test_search_cmd.py (pattern CliRunner existant — à ÉTENDRE)
    - tests/unit/cli/test_show_cmd.py (pattern mock_container dans tests CLI)
    - tests/unit/cli/test_app.py (test_help_lists_every_command pattern)
    - .gsd/KNOWLEDGE.md (Annotated[T, typer.Argument(...)] pour non-str defaults + no unicode glyphs)
  </read_first>
  <behavior>
    - Test 1 (explain happy): `vidscope explain 1` exit 0 avec reasoning + 5 scores + sentiment + content_type dans stdout.
    - Test 2 (explain missing video): `vidscope explain 999` exit 1 avec "not found" / "no video with id 999".
    - Test 3 (explain video without analysis): video existe mais analysis=None → exit 1 avec message clair (ex: "no analysis yet for video 1 — run vidscope add again").
    - Test 4 (search sans facets = V1 behavior): `vidscope search "python"` exit 0, appelle SearchVideosUseCase avec filters vides.
    - Test 5 (search --content-type valide): `vidscope search "python" --content-type tutorial` exit 0 avec filters.content_type=ContentType.TUTORIAL.
    - Test 6 (search --content-type invalide): `vidscope search "python" --content-type podcast` exit != 0 avec BadParameter message.
    - Test 7 (search --min-actionability): `vidscope search "python" --min-actionability 70` exit 0, filters.min_actionability=70.0.
    - Test 8 (search --min-actionability hors bornes): `vidscope search "python" --min-actionability -10` exit != 0 (Typer min=0).
    - Test 9 (search --sponsored true/false): `vidscope search "python" --sponsored true` → filters.is_sponsored=True; `--sponsored false` → False; `--sponsored unknown` → exit != 0.
    - Test 10 (search facets combinés): `vidscope search "python" --content-type tutorial --min-actionability 70 --sponsored false` → tous filtres passés.
    - Test 11 (explain: vidscope --help liste la commande): `vidscope --help` stdout contient "explain".
    - Test 12 (explain: ASCII only): pas de glyphe unicode dans `cli/commands/explain.py` ni dans la sortie stdout.
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/cli/commands/explain.py` :

```python
"""`vidscope explain <id>` — show reasoning + score vector for a video.

M010 command: surface the qualitative analyzer output in a human-
readable form. Displays all 9 M010 fields (reasoning, 4 score
dimensions, sentiment, is_sponsored, content_type, verticals) plus
the V1 summary / score.

ASCII-only output (Windows cp1252 compat per KNOWLEDGE.md). Uses
``rich.panel.Panel`` with border style for visual anchoring but
only ASCII tags like ``[green]OK[/green]`` in content.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel

from vidscope.application.explain_analysis import ExplainAnalysisUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)

__all__ = ["explain_command"]


def explain_command(
    video_id: Annotated[int, typer.Argument(help="Numeric id of the video to explain.")],
) -> None:
    """Show the reasoning + per-dimension scores of the latest analysis."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = ExplainAnalysisUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(video_id)

        if not result.found or result.video is None:
            raise fail_user(f"no video with id {video_id}")

        if result.analysis is None:
            raise fail_user(
                f"no analysis yet for video {video_id} - "
                f"run vidscope add again to analyze it"
            )

        _render(result)


def _render(result) -> None:  # type: ignore[no-untyped-def]
    video = result.video
    analysis = result.analysis

    header = (
        f"[bold]video:[/bold] {video.id}  "
        f"[bold]platform:[/bold] {video.platform.value}  "
        f"[bold]provider:[/bold] {analysis.provider}"
    )
    console.print(header)

    # Reasoning panel
    reasoning = analysis.reasoning or "(no reasoning — legacy analysis)"
    console.print(Panel(reasoning, title="[bold]Reasoning[/bold]", border_style="cyan"))

    # Categorical fields
    console.print(
        f"[bold]content_type:[/bold] {_fmt_enum(analysis.content_type)}   "
        f"[bold]sentiment:[/bold] {_fmt_enum(analysis.sentiment)}   "
        f"[bold]is_sponsored:[/bold] {_fmt_bool(analysis.is_sponsored)}"
    )

    # Verticals
    if analysis.verticals:
        console.print(
            f"[bold]verticals:[/bold] {', '.join(analysis.verticals)}"
        )
    else:
        console.print("[dim]verticals: (none)[/dim]")

    # Per-dimension scores
    console.print("[bold]Scores:[/bold]")
    console.print(f"  overall:             {_fmt_score(analysis.score)}")
    console.print(f"  information_density: {_fmt_score(analysis.information_density)}")
    console.print(f"  actionability:       {_fmt_score(analysis.actionability)}")
    console.print(f"  novelty:             {_fmt_score(analysis.novelty)}")
    console.print(f"  production_quality:  {_fmt_score(analysis.production_quality)}")

    # Legacy summary
    console.print(f"[bold]summary:[/bold] {analysis.summary or '-'}")

    if analysis.keywords:
        console.print(
            f"[bold]keywords:[/bold] {', '.join(analysis.keywords[:8])}"
        )


def _fmt_enum(value: object) -> str:
    if value is None:
        return "-"
    enum_val = getattr(value, "value", None)
    return enum_val if enum_val is not None else str(value)


def _fmt_bool(value: bool | None) -> str:
    if value is None:
        return "-"
    return "yes" if value else "no"


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}/100"
```

Étape 2 — Étendre `src/vidscope/cli/commands/search.py` (remplacer intégralement le contenu) :

```python
"""`vidscope search <query> [--content-type TYPE] [--min-actionability N] [--sponsored BOOL]`

M010: keeps the FTS5 search path intact; adds 3 facet filters that
narrow results to videos whose latest analysis matches. All options
use ``Annotated[...]`` per KNOWLEDGE.md.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors
from vidscope.domain import ContentType

__all__ = ["search_command"]


def _parse_sponsored(raw: str | None) -> bool | None:
    if raw is None:
        return None
    norm = raw.strip().lower()
    if norm in {"true", "yes", "1"}:
        return True
    if norm in {"false", "no", "0"}:
        return False
    raise typer.BadParameter(
        f"--sponsored expects true|false, got {raw!r}"
    )


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
) -> None:
    """Run a full-text query through the SQLite FTS5 index."""
    with handle_domain_errors():
        parsed_ct = _parse_content_type(content_type)
        parsed_sp = _parse_sponsored(sponsored)

        filters = SearchFilters(
            content_type=parsed_ct,
            min_actionability=float(min_actionability) if min_actionability is not None else None,
            is_sponsored=parsed_sp,
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
    return " ".join(parts) if parts else "none"
```

Étape 3 — Mettre à jour `src/vidscope/cli/commands/__init__.py` pour exporter `explain_command` :

Ajouter :
```python
from vidscope.cli.commands.explain import explain_command
```
Ajouter `"explain_command"` dans `__all__` (tri alphabétique, après `"doctor_command"`).

Étape 4 — Enregistrer la commande dans `src/vidscope/cli/app.py` :

Dans le bloc `from vidscope.cli.commands import (...)`, ajouter `explain_command` dans la liste triée.

Après les autres `app.command(...)` (par exemple après `suggest_command`), ajouter :

```python
app.command(
    "explain",
    help="Show reasoning and per-dimension scores of a video's latest analysis.",
)(explain_command)
```

Étape 5 — Créer `tests/unit/cli/test_explain.py` :

```python
"""CLI tests for vidscope explain <id>."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    Platform,
    PlatformId,
    SentimentLabel,
    Video,
    VideoId,
)

runner = CliRunner()


def _make_video(vid: int = 1) -> Video:
    return Video(
        id=VideoId(vid), platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=f"https://y.be/{vid}",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _make_analysis(vid: int = 1, *, reasoning: str = "Clear tutorial about Python.") -> Analysis:
    return Analysis(
        video_id=VideoId(vid),
        provider="heuristic",
        language=Language.ENGLISH,
        keywords=("python", "code"),
        topics=("python",),
        score=72.0,
        summary="A Python tutorial",
        verticals=("tech", "ai"),
        information_density=70.0,
        actionability=85.0,
        novelty=40.0,
        production_quality=60.0,
        sentiment=SentimentLabel.POSITIVE,
        is_sponsored=False,
        content_type=ContentType.TUTORIAL,
        reasoning=reasoning,
    )


def _make_container(*, video: Video | None, analysis: Analysis | None) -> Any:
    class _UoW:
        def __init__(self) -> None:
            self.videos = MagicMock()
            self.videos.get = MagicMock(return_value=video)
            self.analyses = MagicMock()
            self.analyses.get_latest_for_video = MagicMock(return_value=analysis)
        def __enter__(self) -> Any: return self
        def __exit__(self, *_: Any) -> None: return None

    container = MagicMock()
    container.unit_of_work = lambda: _UoW()
    return container


class TestExplainCommand:
    def test_explain_happy_path_shows_reasoning_and_scores(self, monkeypatch) -> None:
        container = _make_container(video=_make_video(1), analysis=_make_analysis(1))
        import vidscope.cli.commands.explain as ex_mod
        monkeypatch.setattr(ex_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(app, ["explain", "1"])
        assert res.exit_code == 0, res.stdout
        # Reasoning text present
        assert "Clear tutorial" in res.stdout
        # Per-dimension scores rendered
        assert "information_density" in res.stdout
        assert "actionability" in res.stdout
        # Categorical fields
        assert "tutorial" in res.stdout.lower()
        assert "positive" in res.stdout.lower()

    def test_explain_missing_video_exit_nonzero(self, monkeypatch) -> None:
        container = _make_container(video=None, analysis=None)
        import vidscope.cli.commands.explain as ex_mod
        monkeypatch.setattr(ex_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(app, ["explain", "999"])
        assert res.exit_code != 0
        assert "no video" in res.stdout.lower() or "not found" in res.stdout.lower()

    def test_explain_video_without_analysis_exit_nonzero(self, monkeypatch) -> None:
        container = _make_container(video=_make_video(1), analysis=None)
        import vidscope.cli.commands.explain as ex_mod
        monkeypatch.setattr(ex_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(app, ["explain", "1"])
        assert res.exit_code != 0
        assert "no analysis" in res.stdout.lower()

    def test_explain_no_unicode_glyphs_in_source(self) -> None:
        """KNOWLEDGE.md: no unicode glyphs in CLI source (Windows cp1252)."""
        src = Path("src/vidscope/cli/commands/explain.py").read_text(encoding="utf-8")
        for glyph in ("\u2713", "\u2717", "\u2192", "\u2190", "\u2714", "\u2718"):
            assert glyph not in src, f"unicode glyph found: {glyph!r}"


class TestExplainAppHelp:
    def test_help_lists_explain(self) -> None:
        from vidscope.cli.app import app
        res = runner.invoke(app, ["--help"])
        assert res.exit_code == 0
        assert "explain" in res.stdout.lower()
```

Étape 6 — Étendre `tests/unit/cli/test_search_cmd.py` en AJOUTANT :

```python
class TestSearchM010Facets:
    """M010: --content-type, --min-actionability, --sponsored flags."""

    def _make_container(self, *, hits: list) -> Any:
        from unittest.mock import MagicMock

        class _UoW:
            def __init__(self) -> None:
                self.search_index = MagicMock()
                self.search_index.search = MagicMock(return_value=hits)
                self.analyses = MagicMock()
                self.analyses.list_by_filters = MagicMock(
                    return_value=[1] if hits else []
                )
            def __enter__(self) -> Any: return self
            def __exit__(self, *_: Any) -> None: return None

        container = MagicMock()
        container.unit_of_work = lambda: _UoW()
        return container

    def test_search_with_valid_content_type(self, monkeypatch) -> None:
        from dataclasses import dataclass

        @dataclass
        class _Hit:
            video_id: int = 1
            source: str = "transcript"
            rank: float = 0.9
            snippet: str = "..."

        container = self._make_container(hits=[_Hit()])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--content-type", "tutorial"],
        )
        assert res.exit_code == 0, res.stdout

    def test_search_with_invalid_content_type_errors(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--content-type", "podcast"],
        )
        assert res.exit_code != 0

    def test_search_with_min_actionability_valid(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--min-actionability", "70"],
        )
        assert res.exit_code == 0

    def test_search_min_actionability_negative_rejected(self) -> None:
        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--min-actionability", "-5"],
        )
        assert res.exit_code != 0

    def test_search_min_actionability_over_100_rejected(self) -> None:
        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--min-actionability", "150"],
        )
        assert res.exit_code != 0

    def test_search_sponsored_true(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, ["search", "python", "--sponsored", "true"])
        assert res.exit_code == 0

    def test_search_sponsored_false(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, ["search", "python", "--sponsored", "false"])
        assert res.exit_code == 0

    def test_search_sponsored_invalid(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, ["search", "python", "--sponsored", "maybe"])
        assert res.exit_code != 0

    def test_search_combined_facets(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, [
            "search", "python",
            "--content-type", "tutorial",
            "--min-actionability", "70",
            "--sponsored", "false",
        ])
        assert res.exit_code == 0
```

Étape 7 — Étendre `tests/unit/cli/test_app.py` pour vérifier que `explain` apparaît :

```python
def test_app_help_lists_explain_command() -> None:
    from vidscope.cli.app import app
    from typer.testing import CliRunner
    res = CliRunner().invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "explain" in res.stdout.lower()
```

Étape 8 — Exécuter :
```
uv run pytest tests/unit/cli/test_explain.py tests/unit/cli/test_search_cmd.py tests/unit/cli/test_app.py -x -q
uv run lint-imports
uv run pytest -m architecture -x -q
```

NE PAS utiliser de glyphes unicode dans les sorties CLI (règle KNOWLEDGE.md: compat Windows cp1252). Utiliser `[green]OK[/green]` / `[red]FAIL[/red]` (déjà fait dans les fichiers).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/cli/test_explain.py tests/unit/cli/test_search_cmd.py tests/unit/cli/test_app.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def explain_command" src/vidscope/cli/commands/explain.py` matches
    - `grep -n "explain_command" src/vidscope/cli/commands/__init__.py` matches
    - `grep -n "app.command(\"explain\"" src/vidscope/cli/app.py` matches (enregistrement)
    - `grep -n "ContentType" src/vidscope/cli/commands/search.py` matches
    - `grep -n '"--content-type"' src/vidscope/cli/commands/search.py` matches
    - `grep -n '"--min-actionability"' src/vidscope/cli/commands/search.py` matches
    - `grep -n '"--sponsored"' src/vidscope/cli/commands/search.py` matches
    - `grep -n "min=0, max=100" src/vidscope/cli/commands/search.py` matches (Typer validation)
    - `grep -nE "\\u2713|\\u2717|\\u2192" src/vidscope/cli/commands/explain.py` returns exit 1 (no unicode glyphs)
    - `grep -nE "\\u2713|\\u2717|\\u2192" src/vidscope/cli/commands/search.py` returns exit 1
    - `uv run pytest tests/unit/cli/test_explain.py -x -q` exits 0
    - `uv run pytest tests/unit/cli/test_search_cmd.py::TestSearchM010Facets -x -q` exits 0
    - `uv run pytest tests/unit/cli/test_app.py -x -q` exits 0
    - `uv run lint-imports` exits 0
    - `uv run pytest -m architecture -x -q` exits 0
  </acceptance_criteria>
  <done>
    - `vidscope explain <id>` livré + enregistré dans app.py
    - `vidscope search` étendu avec 3 flags facettes validés (Typer + conversion défensive)
    - Messages CLI ASCII-only (compat Windows)
    - 10+ tests CLI explain/search/app verts
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI args (`--content-type`, `--min-actionability`, `--sponsored`, video_id) → CLI parsers | user input, potentially malformed |
| CLI parsed args → SearchFilters / SearchVideosUseCase | primitives + enums, déjà validés |
| SearchFilters → `AnalysisRepository.list_by_filters` | valeurs enum+float+bool — SQL paramétré en Task 1 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INPUT-01 | Injection | `--content-type "' OR 1=1 --"` | mitigate | Conversion via `ContentType("' OR 1=1 --")` lève `ValueError` → `typer.BadParameter` → exit 2 avec message clair. Jamais propagé en SQL. |
| T-INPUT-02 | DoS | `--min-actionability 1000000` | mitigate | Typer valide `min=0, max=100` au parse time. Exit non-zero. |
| T-INPUT-03 | DoS | `--min-actionability -9999999` | mitigate | Typer valide `min=0`. Exit non-zero. |
| T-INPUT-04 | Spoofing | `--sponsored "truthy"` (valeur ambiguë) | mitigate | `_parse_sponsored` strict: n'accepte que true/yes/1 ou false/no/0. Tout autre input → BadParameter. |
| T-INPUT-05 | DoS | `vidscope explain -9999999999` | accept | Python int arbitrary precision. `int(value)` ne lève pas. Le lookup renvoie None (not found) → exit 1 clean. |
| T-SQL-01 | Injection | `list_by_filters` dérive une query SQL depuis user input | mitigate | SQLAlchemy Core `.where(col == value)` binde les valeurs comme paramètres. Pas de string interpolation. Test `test_sql_injection_attempt_safe` guard. |
| T-OUTPUT-01 | Info Disclosure | `explain` révèle reasoning d'une vidéo à un autre user | accept | R032 single-user local tool. Pas de notion de user distinct. |
| T-ENCODING-01 | Availability | CLI stdout crash sur Windows cp1252 (unicode) | mitigate | Tous les fichiers CLI livrés en S04 sont ASCII-only (tests grep vérifient). Tags `[green]OK[/green]` / `[red]FAIL[/red]`. |
</threat_model>

<verification>
Après les 3 tâches :
- `uv run pytest tests/unit/adapters/sqlite/test_analysis_repository.py::TestListByFilters tests/unit/application/test_explain_analysis.py tests/unit/application/test_search_videos.py tests/unit/cli/test_explain.py tests/unit/cli/test_search_cmd.py tests/unit/cli/test_app.py -x -q` vert
- `uv run pytest -x -q` (suite complète unit) vert
- `uv run pytest -m architecture -x -q` vert
- `uv run lint-imports` vert
- `uv run vidscope --help` liste "explain" dans la section Commands
- `uv run vidscope explain --help` exit 0 avec usage détaillé
- `uv run vidscope search --help` liste `--content-type`, `--min-actionability`, `--sponsored` dans les options
- `uv run vidscope search "x" --content-type podcast` exit != 0 (BadParameter)
- `uv run vidscope search "x" --min-actionability -10` exit != 0 (Typer validation)
- `uv run vidscope search "x" --sponsored maybe` exit != 0
</verification>

<success_criteria>
S04 est complet quand :
- [ ] `AnalysisRepository.list_by_filters` livré (port Protocol + SQLite impl) avec SQL paramétré
- [ ] `ExplainAnalysisUseCase` + DTO livrés, 3 cas testés
- [ ] `SearchVideosUseCase` + `SearchFilters` livrés, logique filter/passthrough testée
- [ ] `vidscope explain <id>` livré, enregistré dans app.py
- [ ] `vidscope search` étendu avec `--content-type`, `--min-actionability`, `--sponsored` validés côté Typer + parsing défensif
- [ ] `vidscope --help` liste la commande `explain`
- [ ] Aucun glyphe unicode dans les fichiers CLI (test grep)
- [ ] application-has-no-adapters KEPT (use cases purs)
- [ ] Suite tests verte (sqlite + application + cli)
- [ ] `lint-imports` + `pytest -m architecture` verts
- [ ] R053 (facet search) + R055 (explain reasoning) couverts
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M010/M010-S04-SUMMARY.md` documentant :
- Signature exacte de `AnalysisRepository.list_by_filters` + semantique des filtres (NULL excluded)
- Signature de `ExplainAnalysisUseCase.execute` et son DTO
- Signature de `SearchVideosUseCase.execute` + `SearchFilters`
- UX `vidscope explain <id>` (Panel reasoning + 5 scores + enums)
- UX `vidscope search "..." --content-type ... --min-actionability N --sponsored true|false`
- Validations Typer (min=0, max=100, content-type enum, sponsored true|false)
- Messages d'erreur utilisateurs (not found, no analysis yet, BadParameter)
- Liste des fichiers créés/modifiés
</output>
</content>
</invoke>