---
phase: M009
verified: 2026-04-18T12:00:00Z
status: passed
score: 28/28 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 26/28
  gaps_closed:
    - "Hypothesis property-based gate bloque le merge si une propriété échoue (test_metrics_property.py)"
    - "Requirements R050, R051, R052 documentés dans REQUIREMENTS.md avec statut 'validated'"
  gaps_remaining: []
  regressions: []
---

# Phase M009 : Verification Report — Engagement Signals + Velocity Tracking

**Phase Goal :** Table `video_stats` time-series, `vidscope refresh-stats`, `vidscope watch refresh` étendu, `vidscope trending --since`, MCP tool `vidscope_trending`.
**Verified :** 2026-04-18
**Status :** passed
**Re-verification :** Oui — après fermeture des 2 gaps identifiés en vérification initiale

---

## Re-verification Summary

Les 2 gaps bloquants ont été résolus :

**Gap 1 — Hypothesis installé (CLOSED)**
`hypothesis>=6.0,<7` ajouté dans les dev dependencies de `pyproject.toml` (ligne 185) et `uv sync` exécuté. La commande `uv run pytest tests/unit/domain/test_metrics_property.py` collecte et passe 13/13 tests (hypothesis-6.152.1 actif).

**Gap 2 — Requirements R050, R051, R052 documentés (CLOSED)**
R050, R051, R052 ajoutés dans `.gsd/REQUIREMENTS.md` avec statut `validated`, preuve de validation M009, et entrées dans le tableau Traceability et le Coverage Summary (Validated: 7 dont R050, R051, R052).

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                        | Status        | Evidence                                                                                    |
|----|--------------------------------------------------------------------------------------------------------------|---------------|---------------------------------------------------------------------------------------------|
| 1  | `VideoStats` frozen dataclass slots=True avec 5 compteurs `int\|None`                                       | VERIFIED      | `entities.py:212-236` — `@dataclass(frozen=True, slots=True)`, 5 champs int\|None          |
| 2  | Table `video_stats` avec `UNIQUE(video_id, captured_at)` dans schema.py                                     | VERIFIED      | `schema.py:201-218` — UniqueConstraint nommée + migration idempotente                       |
| 3  | `metrics.views_velocity_24h` et `metrics.engagement_rate` calculent correctement                             | VERIFIED      | `metrics.py:30-100` — 2 fonctions pure-Python ; tests `test_video_stats_repository.py` verts|
| 4  | `YtdlpStatsProbe.probe_stats(url)` utilise `extract_info(download=False)`                                   | VERIFIED      | `ytdlp_stats_probe.py:110` — `ydl.extract_info(url, download=False)` confirmé              |
| 5  | `VideoStatsRepositorySQLite.append` est append-only (`INSERT ON CONFLICT DO NOTHING`)                       | VERIFIED      | `video_stats_repository.py:42-46` — pattern confirmé                                        |
| 6  | `UnitOfWork.video_stats` disponible                                                                          | VERIFIED      | `unit_of_work.py:69` — `video_stats: VideoStatsRepository`                                  |
| 7  | `Container.stats_probe` existe                                                                               | VERIFIED      | `container.py:133` — champ `stats_probe: StatsProbe`                                        |
| 8  | `StatsStage.is_satisfied()` retourne toujours False                                                          | VERIFIED      | `stats_stage.py:48-56` — `return False` ; 7/7 tests passent                                 |
| 9  | `StatsStage` N'EST PAS dans le graphe `add` par défaut                                                       | VERIFIED      | `container.py:227-237` — `stages=[ingest, transcribe, frames, analyze, index]` seulement   |
| 10 | `RefreshStatsUseCase.execute_one(video_id)` fonctionne                                                       | VERIFIED      | `refresh_stats.py:73` ; 21/21 tests `test_refresh_stats.py` passent                         |
| 11 | `RefreshStatsUseCase.execute_all(since, limit)` avec validation `limit >= 1`                                 | VERIFIED      | `refresh_stats.py:130,156-157` — `if limit < 1: raise ValueError`                           |
| 12 | `vidscope refresh-stats <id>` fonctionne                                                                     | VERIFIED      | `cli/commands/stats.py:64` ; `app.py:101-103` ; 12 tests CLI verts                          |
| 13 | `vidscope refresh-stats --all [--since 7d]` fonctionne                                                       | VERIFIED      | `stats.py:84` — `--all` flag avec `_parse_since` strict                                     |
| 14 | `vidscope refresh-stats --all --limit 0` est refusé (T-INPUT-01)                                             | VERIFIED      | `stats.py:84` — `min=1` Typer + double validation use case                                  |
| 15 | `vidscope watch refresh` rapporte BOTH nouvelles vidéos ET stats rafraîchies                                 | VERIFIED      | `watch.py:237,245` — format `new_videos=N` + `refreshed=M`                                  |
| 16 | Isolation par créateur ET par vidéo dans `RefreshStatsForWatchlistUseCase`                                   | VERIFIED      | `refresh_stats.py:209-310` — try/except par compte + par vidéo                              |
| 17 | `RefreshWatchlistUseCase` (M003) RESTE INCHANGÉ                                                              | VERIFIED      | `watchlist.py` — classe M003 intacte ; 23/23 tests `test_watchlist.py` verts                |
| 18 | `vidscope trending --since 7d` ranke par `velocity_24h` descendant                                          | VERIFIED      | `list_trending.py:143` — `entries.sort(key=lambda e: e.views_velocity_24h, reverse=True)`  |
| 19 | `vidscope trending` REFUSE l'absence de `--since`                                                            | VERIFIED      | `trending.py:82` — `--since` sans défaut ; CLI exit != 0 si absent (confirmé live)          |
| 20 | MCP tool `vidscope_trending` exposé sur FastMCP                                                              | VERIFIED      | `server.py:292` — `def vidscope_trending` ; 10/10 tests `test_trending_tool.py` verts       |
| 21 | `vidscope show <id>` affiche section stats (D-05)                                                            | VERIFIED      | `show.py:81-112` — `_render_stats()` ; 9/9 tests `test_show_stats.py` verts                 |
| 22 | `ListTrendingUseCase` utilise SQL LIMIT poussé en base (D-04)                                                | VERIFIED      | `video_stats_repository.py:132+` — `rank_candidates_by_delta` avec GROUP BY + LIMIT SQL    |
| 23 | Hypothesis property-based gate sur `metrics.py`                                                              | VERIFIED      | hypothesis-6.152.1 installé ; `uv run pytest test_metrics_property.py` = 13/13 PASSED      |
| 24 | 9/9 contrats import-linter verts                                                                             | VERIFIED      | `uv run lint-imports` — "Contracts: 9 kept, 0 broken"                                       |
| 25 | ASCII-only stdout (pas de glyphes Unicode Windows cp1252)                                                    | VERIFIED      | Tests `test_watch.py`, `test_trending.py`, `test_stats.py` — scan glyphes vert              |
| 26 | Requirements R050, R051, R052 documentés dans REQUIREMENTS.md                                               | VERIFIED      | R050, R051, R052 présents dans `.gsd/REQUIREMENTS.md` statut `validated`, Traceability + Coverage Summary mis à jour |
| 27 | `vidscope refresh-stats --all --limit 0` exit != 0 (Typer min=1)                                            | VERIFIED      | Confirmé par test CLI `test_refresh_stats_limit_zero_rejected_by_typer`                     |
| 28 | MCP `vidscope_trending` retourne JSON-serializable                                                           | VERIFIED      | `test_trending_tool.py::test_result_is_json_serializable` vert                              |

**Score :** 28/28 truths verified

---

### Required Artifacts

| Artifact                                                               | Attendu                                      | Status     | Détails                                                          |
|------------------------------------------------------------------------|----------------------------------------------|------------|------------------------------------------------------------------|
| `src/vidscope/domain/entities.py`                                      | VideoStats frozen, slots, 5 compteurs        | VERIFIED   | Ligne 212-236 — conforme                                         |
| `src/vidscope/domain/metrics.py`                                       | views_velocity_24h + engagement_rate         | VERIFIED   | Lignes 27-100 — 2 fonctions pure-Python exportées                |
| `src/vidscope/adapters/sqlite/schema.py`                               | video_stats table + UNIQUE + migration       | VERIFIED   | Lignes 201-299 — table + constraint + idempotente                |
| `src/vidscope/adapters/sqlite/video_stats_repository.py`               | Append-only + rank_candidates_by_delta       | VERIFIED   | `append` ON CONFLICT DO NOTHING ; `rank_candidates_by_delta` L132|
| `src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py`                    | extract_info(download=False)                 | VERIFIED   | Ligne 110 confirmée                                              |
| `src/vidscope/pipeline/stages/stats_stage.py`                          | StatsStage standalone, is_satisfied=False    | VERIFIED   | Classe conforme ; 7 tests verts                                  |
| `src/vidscope/application/refresh_stats.py`                            | RefreshStatsUseCase + ForWatchlist           | VERIFIED   | execute_one, execute_all, ForWatchlistUseCase, 21 tests verts    |
| `src/vidscope/application/list_trending.py`                            | ListTrendingUseCase + TrendingEntry          | VERIFIED   | Classe + DTO conforme ; 10 tests verts                           |
| `src/vidscope/application/show_video.py`                               | latest_stats + views_velocity_24h champs     | VERIFIED   | Lignes 39-40 + lignes 70-81 — D-05 conforme                      |
| `src/vidscope/cli/commands/stats.py`                                   | vidscope refresh-stats command               | VERIFIED   | `refresh_stats_command` enregistré dans app.py                   |
| `src/vidscope/cli/commands/trending.py`                                | vidscope trending, --since obligatoire       | VERIFIED   | `trending_command` ; `--since` [required] confirmé live          |
| `src/vidscope/cli/commands/watch.py`                                   | Orchestration combinée + résumé              | VERIFIED   | RefreshStatsForWatchlistUseCase appelé ; résumé combiné          |
| `src/vidscope/mcp/server.py`                                           | vidscope_trending tool                       | VERIFIED   | `def vidscope_trending` à la ligne 292 ; 10 tests MCP verts      |
| `tests/unit/domain/test_metrics_property.py`                           | Gate Hypothesis (13 tests de propriétés)     | VERIFIED   | 13/13 PASSED — hypothesis-6.152.1 installé et fonctionnel        |
| `pyproject.toml`                                                       | hypothesis dans dev deps                     | VERIFIED   | Ligne 185 : `"hypothesis>=6.0,<7"` — uv.lock régénéré           |
| `.gsd/REQUIREMENTS.md`                                                 | R050, R051, R052 documentés                  | VERIFIED   | 3 IDs présents, statut validated, Traceability + Coverage Summary à jour |

---

### Key Link Verification

| From                              | To                           | Via                                      | Status  | Détails                                                     |
|-----------------------------------|------------------------------|------------------------------------------|---------|-------------------------------------------------------------|
| `cli/app.py`                      | `refresh_stats_command`      | `app.command("refresh-stats")`           | WIRED   | Ligne 101-103 confirmée                                     |
| `application/refresh_stats.py`    | `StatsStage`                 | Import direct + execute                  | WIRED   | `from vidscope.pipeline.stages.stats_stage import StatsStage`|
| `infrastructure/container.py`     | `StatsStage` (standalone)    | `Container.stats_stage` hors `stages=[]` | WIRED   | Lignes 134, 187 ; exclusion confirmée lignes 227-237        |
| `cli/commands/watch.py`           | `RefreshStatsForWatchlistUseCase` | Appel séquentiel après M003           | WIRED   | `watch.py:20,204`                                           |
| `cli/commands/trending.py`        | `ListTrendingUseCase`        | `trending_command -> uc.execute()`       | WIRED   | Import + instanciation + appel dans `trending_command`      |
| `mcp/server.py`                   | `vidscope_trending`          | `@mcp.tool()` + `ListTrendingUseCase`    | WIRED   | Ligne 292 ; test `test_total_tools_is_seven` vert           |
| `application/show_video.py`       | `VideoStatsRepository`       | `uow.video_stats.latest_for_video()`     | WIRED   | Ligne 70 confirmée                                          |
| `ports/repositories.py`           | `rank_candidates_by_delta`   | Protocol + impl SQLite                   | WIRED   | Ligne 336 Protocol ; ligne 132 impl SQLite                  |

---

### Data-Flow Trace (Level 4)

| Artifact                    | Variable                | Source                                   | Données réelles | Status    |
|-----------------------------|-------------------------|------------------------------------------|-----------------|-----------|
| `list_trending.py`          | `entries`               | `uow.video_stats.rank_candidates_by_delta` + `metrics.py` | Requête SQL GROUP BY réelle | FLOWING |
| `show_video.py`             | `latest_stats`          | `uow.video_stats.latest_for_video(vid_id)` | Requête SQLite réelle | FLOWING |
| `refresh_stats.py`          | `per_video`             | `execute_one` → `StatsStage` → `YtdlpStatsProbe` | Vrai probe yt-dlp | FLOWING |
| `test_metrics_property.py`  | Hypothesis strategies   | `hypothesis` module (6.152.1)            | OUI — 13/13 tests passent | FLOWING |

---

### Behavioral Spot-Checks

| Comportement                          | Commande                              | Résultat                                  | Status   |
|---------------------------------------|---------------------------------------|-------------------------------------------|----------|
| `vidscope trending --since` obligatoire | `uv run vidscope trending`            | exit != 0, "Missing option '--since'"     | PASS     |
| `--since 7d` parsed + format correct   | `uv run vidscope trending --help`     | `[required]` + `RANGE [x>=1]` affichés   | PASS     |
| `vidscope refresh-stats --help`        | `uv run vidscope refresh-stats --help` | Affichage `[VIDEO_ID]` + flags correct   | PASS     |
| Hypothesis gate (re-vérification)      | `uv run pytest tests/unit/domain/test_metrics_property.py` | 13/13 PASSED (1.08s) | PASS |

---

### Requirements Coverage

| Requirement | Plan source | Description                                             | Status       | Evidence                                                                  |
|-------------|-------------|----------------------------------------------------------|--------------|---------------------------------------------------------------------------|
| R050        | S01, S02, S03, S04 | Time-series `video_stats` table                  | SATISFIED    | Documenté dans REQUIREMENTS.md, statut validated, preuve M009             |
| R051        | S02, S03    | `vidscope refresh-stats` + watchlist extension           | SATISFIED    | Documenté dans REQUIREMENTS.md, statut validated, preuve M009             |
| R052        | S04         | `vidscope trending` + MCP tool                           | SATISFIED    | Documenté dans REQUIREMENTS.md, statut validated, preuve M009             |

---

### Anti-Patterns Found

Aucun anti-pattern bloquant. Les fichiers modifiés lors de la correction des gaps (pyproject.toml, .gsd/REQUIREMENTS.md) sont propres.

---

### Human Verification Required

Aucun — tous les comportements critiques ont pu être vérifiés programmatiquement.

---

### Gaps Summary

Aucun gap restant. Les 2 gaps identifiés lors de la vérification initiale (2026-04-18) ont été fermés :

1. **Hypothesis installé** — `hypothesis>=6.0,<7` ajouté en dev deps, `uv sync` exécuté, 13/13 tests propriétés verts.
2. **R050, R051, R052 documentés** — 3 requirements ajoutés dans `.gsd/REQUIREMENTS.md` avec statut `validated`, Traceability et Coverage Summary mis à jour.

**Score final : 28/28 — Objectif M009 atteint.**

---

_Verified: 2026-04-18 (re-verification)_
_Verifier: Claude (gsd-verifier)_
