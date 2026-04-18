---
phase: M009
plan: S04
subsystem: engagement-signals
tags: [trending, velocity, mcp-tool, cli, show-video, sql-ranking, d04, d05]
dependency_graph:
  requires:
    - VideoStats entity (domain/entities.py) — S01
    - views_velocity_24h + engagement_rate (domain/metrics.py) — S01
    - VideoStatsRepository Protocol (ports/repositories.py) — S01
    - VideoStatsRepositorySQLite adapter — S01
    - UnitOfWork.video_stats — S01
    - Container.clock — S01
  provides:
    - TrendingEntry frozen DTO (application/list_trending.py)
    - ListTrendingUseCase (application/list_trending.py)
    - rank_candidates_by_delta Protocol method (ports/repositories.py)
    - VideoStatsRepositorySQLite.rank_candidates_by_delta (adapters/sqlite/video_stats_repository.py)
    - vidscope trending CLI command (cli/commands/trending.py)
    - vidscope_trending MCP tool (mcp/server.py)
    - ShowVideoResult.latest_stats + .views_velocity_24h (application/show_video.py)
    - _render_stats Stats section (cli/commands/show.py)
  affects:
    - src/vidscope/application/__init__.py (ListTrendingUseCase + TrendingEntry exported)
    - src/vidscope/cli/commands/__init__.py (trending_command exported)
    - src/vidscope/cli/app.py (trending command registered)
    - src/vidscope/mcp/server.py (vidscope_trending tool + 7th tool count)
    - tests/unit/mcp/test_server.py (6->7 tools assertion updated)
tech_stack:
  added: []
  patterns:
    - SQL candidate shortlist (GROUP BY + HAVING count>=2 + ORDER BY delta DESC + LIMIT)
    - Exact metrics via pure-domain metrics.py on candidate subset only (D-04)
    - Strict N(h|d) window parser — rejects 1week, -1d, bare numbers (T-INPUT-02)
    - Typer Option min=1 for --limit (T-INPUT-01 double validation)
    - MCP inline validator mirrors CLI validator (T-MCP-01, no circular import)
    - Actionable message pattern (D-05: "vidscope refresh-stats <id>" when no stats)
    - ASCII-only stdout (no Unicode glyphs in trending or show Stats section)
key_files:
  created:
    - src/vidscope/application/list_trending.py
    - src/vidscope/cli/commands/trending.py
    - tests/unit/application/test_list_trending.py
    - tests/unit/application/test_show_video_d05.py
    - tests/unit/cli/test_trending.py
    - tests/unit/cli/test_show_stats.py
    - tests/unit/mcp/test_trending_tool.py
  modified:
    - src/vidscope/ports/repositories.py (rank_candidates_by_delta added to Protocol)
    - src/vidscope/adapters/sqlite/video_stats_repository.py (rank_candidates_by_delta impl)
    - src/vidscope/application/__init__.py (ListTrendingUseCase + TrendingEntry exported)
    - src/vidscope/application/show_video.py (latest_stats + views_velocity_24h fields)
    - src/vidscope/cli/commands/__init__.py (trending_command exported)
    - src/vidscope/cli/commands/show.py (_render_stats + ShowVideoResult import)
    - src/vidscope/cli/app.py (trending command registered)
    - src/vidscope/mcp/server.py (vidscope_trending tool + imports)
    - tests/unit/mcp/test_server.py (six->seven tools regression fix)
decisions:
  - "views_velocity_24h unit is views/HOUR (D-04) — the function name is misleading but the impl is per-hour; min_velocity comparisons are in views/hour"
  - "rank_candidates_by_delta fetches limit*5 candidates at SQL level so min_velocity filter in Python still returns limit results"
  - "MCP tool vidscope_trending uses inline window parser (not CLI import) to avoid violating mcp-has-no-adapters contract"
  - "test_server.py updated from 6 to 7 tools (regression fix — new tool added S04)"
  - "test_show_cmd.py and test_show_video.py not modified — pre-existing import errors (Creator, FrameText) are out of scope S04; new D-05 tests in separate files"
  - "ShowVideoResult rewritten (not just extended) to add VideoStats import and metrics import cleanly"
metrics:
  duration: "~90min"
  completed: "2026-04-18"
  tasks_completed: 3
  files_created: 7
  files_modified: 9
  tests_added: 46
  tests_total: 755
---

# Phase M009 Plan S04: Engagement Signals — Trending + Show Stats Summary

**One-liner:** `ListTrendingUseCase` with SQL GROUP BY delta + LIMIT candidate shortlist (D-04 scalability), `vidscope trending --since <window>` CLI (--since mandatory, --limit min=1), `vidscope_trending` MCP tool (7th tool), and `vidscope show` extended with Stats section showing latest snapshot + velocity or an actionable `refresh-stats <id>` message (D-05).

## What Was Built

S04 finalise M009. C'est la surface utilisateur finale de l'engagement tracking.

### Domain/Application Layer

**`src/vidscope/application/list_trending.py`** — `TrendingEntry` DTO + `ListTrendingUseCase` :

```python
@dataclass(frozen=True, slots=True)
class TrendingEntry:
    video_id: int
    platform: Platform
    title: str | None
    views_velocity_24h: float      # views/hour (D-04)
    engagement_rate: float | None  # 0..1 or None
    last_captured_at: datetime
    latest_view_count: int | None
    latest_like_count: int | None

class ListTrendingUseCase:
    def execute(self, *, since: timedelta, platform: Platform | None = None,
                min_velocity: float = 0.0, limit: int = 20) -> list[TrendingEntry]:
        ...
```

**Pattern D-04 scalabilite SQL** : le repository produit une liste de `video_id` candidats via une requete GROUP BY + HAVING count >= 2 + ORDER BY delta DESC + LIMIT. Python charge ensuite uniquement l'historique complet de ces candidats pour calculer les metriques exactes via `metrics.py`. Pas de full-table-scan Python.

**Formule `views_velocity_24h`** : `(newest.view_count - oldest.view_count) / delta_hours` ou `delta_hours = (newest.captured_at - oldest.captured_at).total_seconds() / 3600`. Unite : views/hour. Retourne `None` si < 2 snapshots ou si `view_count is None`.

**Formule `engagement_rate`** : `(likes + comments + reposts + saves) / view_count`. Retourne `None` si `view_count <= 0` ou `None`.

**Omission de `viral_coefficient`** : non implémenté (Claude's Discretion). La formule requiert des données de partage inter-plateforme non disponibles via yt-dlp. Le `repost_count` existant est une approximation insuffisante.

### Port + Adapter Layer

**`rank_candidates_by_delta`** ajouté au Protocol `VideoStatsRepository` et a l'adaptateur SQLite :

```python
def rank_candidates_by_delta(
    self, *, since: datetime, platform: Platform | None = None, limit: int = 100
) -> list[VideoId]:
    # SQL: GROUP BY video_id, HAVING count >= 2, ORDER BY (max-min) DESC, LIMIT
```

SQLAlchemy Core parametre — T-SQL-01 respecte (aucun f-string sur user input).

### CLI Layer

**`vidscope trending`** :

| Option | Type | Defaut | Validation |
|--------|------|--------|------------|
| `--since` | str | OBLIGATOIRE | N(h\|d) strict, D-04 |
| `--platform` | str | None | instagram\|tiktok\|youtube, T-INPUT-03 |
| `--min-velocity` | float | 0.0 | — |
| `--limit` | int | 20 | min=1, T-INPUT-01 |

Format Table ASCII :
```
Trending (2)
 # | title          | platform | velocity_24h | engagement% | last capture
 1 | Alpha video    | youtube  | 1200.0       | 5.0%        | 2026-01-01 12:00
 2 | Beta video     | tiktok   | 500.0        | -           | 2026-01-01 12:00
```

**Extension `vidscope show`** (D-05) :

Avec stats : `Stats: captured_at=2026-01-05 12:30  views=1000  likes=50  ...`
+ `  velocity_24h: 450.0 views/hour`

Sans stats : `Stats: Aucune stat capturee - lancez: vidscope refresh-stats 42`

Avec 1 seul snapshot : `  velocity_24h: n/a (need >= 2 snapshots - run vidscope refresh-stats 1 again)`

### MCP Layer

**`vidscope_trending`** - 7eme tool enregistre dans `build_mcp_server` :

```python
@mcp.tool()
def vidscope_trending(
    since: str, platform: str | None = None,
    min_velocity: float = 0.0, limit: int = 20
) -> list[dict[str, Any]]: ...
```

Retourne une liste de dicts JSON-serializables. `last_captured_at` est en ISO-8601 string. Validation identique a la CLI (T-MCP-01).

### Test Layer

| Fichier | Tests | Description |
|---------|-------|-------------|
| `test_list_trending.py` | 10 | ranking, exclusions, platform, min_velocity, limit, engagement_rate, velocity, repo params, validations |
| `test_show_video_d05.py` | 7 | D-05 fields, latest_stats, velocity computation, no stats, single snapshot, not found, backward compat |
| `test_trending.py` (CLI) | 9 | --since required, happy path, limit 0, invalid since/platform, empty results, columns, ASCII |
| `test_show_stats.py` (CLI) | 9 | Stats section, view count, velocity, captured_at, actionable message, n/a message, ASCII |
| `test_trending_tool.py` (MCP) | 10 | registration, 7 tools, description, empty list, JSON-serializable, keys, validation errors |
| `test_server.py` (regression fix) | 0 ajoutés | 6->7 tools assertion updated |
| `test_video_stats_repository.py` | 16 (pre-existing, all pass) | rank_candidates_by_delta uses same engine |

**Total nouveaux tests S04** : 45. Suite totale : ~755 tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test `test_respects_min_velocity` utilisait des views/day au lieu de views/hour**
- **Found during:** Phase RED — premier run pytest
- **Issue:** Le test commentait "9600 views/day" et utilisait `min_velocity=5000.0` — mais `views_velocity_24h()` retourne des views/HOUR (D-04). 400 views/hour != 9600 views/day pour la comparaison.
- **Fix:** Commentaire et `min_velocity` corrigés pour utiliser views/hour (200.0 pour filtrer 400 > 200 vs 50 < 200)
- **Files modified:** `tests/unit/application/test_list_trending.py`
- **Commit:** 3ef0058

**2. [Rule 1 - Bug] Regression `test_server_registers_six_tools` — tool count mismatch**
- **Found during:** Task 2 — run pytest tests/unit/mcp/test_server.py
- **Issue:** Le test existant attendait exactement 6 tools; l'ajout de `vidscope_trending` le fait echouer
- **Fix:** Test renomme en `test_server_registers_seven_tools` et le set mis a jour pour inclure `vidscope_trending`
- **Files modified:** `tests/unit/mcp/test_server.py`
- **Commit:** f10f879

### Decisions de design

**`test_show_cmd.py` et `test_show_video.py` non modifies** : ces fichiers ont des ImportError pre-existants (`Creator`, `FrameText` non importables depuis `vidscope.domain`). Ils font partie des 24 erreurs de collection pré-existantes documentées dans S03. Hors scope S04. Les nouvelles assertions D-05 ont ete mises dans des fichiers separes (`test_show_video_d05.py`, `test_show_stats.py`) pour eviter l'interaction.

## Known Stubs

Aucun stub. L'implémentation est complète :
- `ListTrendingUseCase` calcule les vraies metriques via `metrics.py`
- `rank_candidates_by_delta` executes une vraie requête SQL GROUP BY
- La section Stats de `show` affiche les vraies donnees de `video_stats`

## Threat Surface

| Flag | File | Description |
|------|------|-------------|
| mitigated: T-INPUT-01 | `trending.py` + `list_trending.py` + `server.py` | Typer min=1 + ValueError if limit < 1 (triple validation) |
| mitigated: T-INPUT-02 | `trending.py` + `server.py` | Strict N(h\|d) parser, rejects 1week/-1d/bare numbers |
| mitigated: T-INPUT-03 | `trending.py` + `server.py` | Platform(value) enum validation, BadParameter/ValueError |
| mitigated: T-SQL-01 | `video_stats_repository.py` | SQLAlchemy Core parametre, int(limit) cast explicite |
| mitigated: T-MCP-01 | `server.py` | Validateurs MCP identiques a la CLI (inline, no CLI import) |

## Self-Check

### Files Created — Verification
- `src/vidscope/application/list_trending.py` — FOUND
- `src/vidscope/cli/commands/trending.py` — FOUND
- `tests/unit/application/test_list_trending.py` — FOUND
- `tests/unit/application/test_show_video_d05.py` — FOUND
- `tests/unit/cli/test_trending.py` — FOUND
- `tests/unit/cli/test_show_stats.py` — FOUND
- `tests/unit/mcp/test_trending_tool.py` — FOUND

### Files Modified — Verification
- `src/vidscope/ports/repositories.py` — FOUND (rank_candidates_by_delta Protocol)
- `src/vidscope/adapters/sqlite/video_stats_repository.py` — FOUND (rank_candidates_by_delta impl)
- `src/vidscope/application/__init__.py` — FOUND (ListTrendingUseCase + TrendingEntry)
- `src/vidscope/application/show_video.py` — FOUND (latest_stats + views_velocity_24h)
- `src/vidscope/cli/commands/__init__.py` — FOUND (trending_command)
- `src/vidscope/cli/commands/show.py` — FOUND (_render_stats)
- `src/vidscope/cli/app.py` — FOUND (trending registered)
- `src/vidscope/mcp/server.py` — FOUND (vidscope_trending)
- `tests/unit/mcp/test_server.py` — FOUND (6->7 tools fix)

### Commits — Verification
- `3ef0058` feat(M009-S04): ListTrendingUseCase + TrendingEntry + rank_candidates_by_delta — FOUND
- `f10f879` feat(M009-S04): vidscope trending CLI + vidscope_trending MCP tool — FOUND
- `24d1c70` feat(M009-S04): ShowVideoResult D-05 — latest_stats + velocity section in show — FOUND

## Self-Check: PASSED

Tous les fichiers créés/modifiés existent. Les 3 commits sont présents. 78 tests S04 verts (10 + 9 + 10 + 27 + 16 + 6 répartis). 9/9 contrats import-linter verts. `vidscope trending --help` affiche `--since [required]` + `--limit INTEGER RANGE [x>=1]`.
