---
phase: M009
plan: S01
subsystem: engagement-signals
tags: [video-stats, time-series, hypothesis, sqlite, ytdlp, metrics]
dependency_graph:
  requires: []
  provides:
    - VideoStats entity (domain/entities.py)
    - views_velocity_24h + engagement_rate (domain/metrics.py)
    - StatsProbe Protocol (ports/stats_probe.py)
    - VideoStatsRepository Protocol (ports/repositories.py)
    - VideoStatsRepositorySQLite adapter (adapters/sqlite/video_stats_repository.py)
    - YtdlpStatsProbe adapter (adapters/ytdlp/ytdlp_stats_probe.py)
    - video_stats Table + migration (adapters/sqlite/schema.py)
    - Container.stats_probe (infrastructure/container.py)
  affects:
    - ports/unit_of_work.py (UnitOfWork.video_stats added)
    - adapters/sqlite/unit_of_work.py (SqliteUnitOfWork.video_stats wired)
    - domain/values.py (StageName.STATS added)
    - domain/__init__.py (VideoStats exported)
    - ports/__init__.py (StatsProbe, VideoStatsRepository exported)
tech_stack:
  added:
    - hypothesis>=6.0,<7 (property-based testing dev dependency)
  patterns:
    - Append-only repository (ON CONFLICT DO NOTHING, no update method)
    - Protocol + runtime_checkable (StatsProbe, VideoStatsRepository)
    - Idempotent migration (_ensure_video_stats_table + _ensure_video_stats_indexes)
    - Probe-never-raises (T-PROBE-01: all exceptions caught, returns None)
    - _int_or_none safety helper (T-DATA-01: non-int values from platform become None)
key_files:
  created:
    - src/vidscope/domain/metrics.py
    - src/vidscope/ports/stats_probe.py
    - src/vidscope/adapters/sqlite/video_stats_repository.py
    - src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py
    - tests/unit/domain/test_metrics_property.py
    - tests/unit/adapters/sqlite/test_video_stats_repository.py
    - tests/unit/adapters/ytdlp/test_stats_probe.py
  modified:
    - pyproject.toml (hypothesis added to dev deps)
    - src/vidscope/domain/values.py (StageName.STATS)
    - src/vidscope/domain/entities.py (VideoStats dataclass)
    - src/vidscope/domain/__init__.py (VideoStats exported)
    - src/vidscope/ports/repositories.py (VideoStatsRepository Protocol)
    - src/vidscope/ports/unit_of_work.py (video_stats attribute)
    - src/vidscope/ports/__init__.py (StatsProbe, VideoStatsRepository exported)
    - src/vidscope/adapters/sqlite/schema.py (video_stats Table + migration)
    - src/vidscope/adapters/sqlite/unit_of_work.py (video_stats wired)
    - src/vidscope/adapters/ytdlp/__init__.py (YtdlpStatsProbe exported)
    - src/vidscope/infrastructure/container.py (Container.stats_probe + YtdlpStatsProbe)
    - tests/unit/domain/test_entities.py (TestVideoStats class added)
    - tests/unit/domain/test_values.py (StageName.STATS added to order test)
    - tests/unit/adapters/sqlite/test_schema.py (video_stats table tests added)
decisions:
  - "VideoStats.view_count <= 0 → engagement_rate None (not just == 0): Hypothesis caught negative views edge case"
  - "_ensure_video_stats_indexes separate from _ensure_video_stats_table: metadata.create_all creates table but not named indexes"
  - "captured_at truncated to microsecond=0 at probe time (D-01): UNIQUE constraint works at second resolution"
  - "repost_count field name matches yt-dlp info dict key (D-02): NOT share_count"
  - "Container.stats_probe typed as StatsProbe Protocol (not YtdlpStatsProbe): substitutable in tests"
metrics:
  duration: "~45min"
  completed: "2026-04-18"
  tasks_completed: 1
  files_created: 7
  files_modified: 14
  tests_added: 71
  tests_total: 671
---

# Phase M009 Plan S01: Engagement Signals Foundation Summary

**One-liner:** Append-only `video_stats` time-series table, `VideoStats` frozen entity with 5 `int | None` counters, pure-Python `metrics.py` with velocity + engagement-rate formulas, `StatsProbe` Protocol, `YtdlpStatsProbe` adapter with `_int_or_none` safety, and Hypothesis property-based gate — all 9 import-linter contracts kept.

## What Was Built

S01 pose la fondation complète M009. Sans ce plan, S02/S03/S04 ne peuvent pas être bâtis.

### Domain Layer

**`src/vidscope/domain/entities.py`** — `VideoStats` frozen dataclass (`slots=True`) :
- 5 compteurs `int | None` : `view_count`, `like_count`, `repost_count`, `comment_count`, `save_count`
- `captured_at: datetime` UTC-aware, résolution seconde (D-01)
- `id: int | None = None`, `created_at: datetime | None = None` (non-persisté au retour de probe)

**`src/vidscope/domain/metrics.py`** — Deux fonctions pure-Python, zéro import tiers runtime :
- `views_velocity_24h(history)` : vitesse en vues/heure sur fenêtre 24h, `None` si < 2 snapshots
- `engagement_rate(stats)` : `(likes + comments + reposts + saves) / views`, `None` si `view_count <= 0`

**`src/vidscope/domain/values.py`** — `StageName.STATS = "stats"` ajouté.

### Ports Layer

**`src/vidscope/ports/stats_probe.py`** — `StatsProbe` Protocol `runtime_checkable` :
```python
def probe_stats(self, url: str) -> VideoStats | None: ...
```

**`src/vidscope/ports/repositories.py`** — `VideoStatsRepository` Protocol append-only :
- `append`, `list_for_video`, `latest_for_video`, `has_any_for_video`, `list_videos_with_min_snapshots`

**`src/vidscope/ports/unit_of_work.py`** — `video_stats: VideoStatsRepository` ajouté au Protocol `UnitOfWork`.

### Adapter Layer

**`src/vidscope/adapters/sqlite/schema.py`** :
- Table `video_stats` avec `UNIQUE(video_id, captured_at)` nommée `uq_video_stats_video_id_captured_at`
- `_ensure_video_stats_table(conn)` : migration idempotente (no-op si table existe)
- `_ensure_video_stats_indexes(conn)` : `CREATE INDEX IF NOT EXISTS` pour `video_id` et `captured_at`
- `init_db()` appelle les deux migrations automatiquement au démarrage

**`src/vidscope/adapters/sqlite/video_stats_repository.py`** — Adapter append-only :
- `append` : `INSERT ... ON CONFLICT DO NOTHING` (jamais de UPDATE — D031)
- `list_for_video` : tri `captured_at ASC`, limite par défaut 100 (T-INPUT-01)
- `latest_for_video`, `has_any_for_video`, `list_videos_with_min_snapshots`
- Aucune méthode `update()` — structurellement impossible de muter une ligne

**`src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py`** — Adapter probe :
- `_int_or_none(value)` : filtre tout non-int → `None` (T-DATA-01, exclut `bool` malgré `isinstance(bool, int)`)
- `probe_stats(url)` : `extract_info(download=False)`, toute exception → `None` (T-PROBE-01)
- `captured_at = datetime.now(UTC).replace(microsecond=0)` (D-01)
- Champ `repost_count` de yt-dlp, pas `share_count` (D-02)

### Infrastructure Layer

**`src/vidscope/infrastructure/container.py`** :
- Champ `stats_probe: StatsProbe` ajouté au dataclass `Container`
- `YtdlpStatsProbe(cookies_file=resolved_config.cookies_file)` instancié dans `build_container()`

### Test Layer

| Fichier | Tests | Description |
|---------|-------|-------------|
| `test_metrics_property.py` | 13 | Gate Hypothesis (4 propriétés + déterministes) |
| `test_video_stats_repository.py` | 15 | Append-only invariant, None roundtrip, idempotence |
| `test_stats_probe.py` | 18 | _int_or_none, probe-never-raises, D-01/D-02/D-03 |
| `test_entities.py` (ajout) | 5 | TestVideoStats class |
| `test_schema.py` (ajout) | 4 | video_stats table + migration idempotente |
| `test_values.py` (ajout) | 1 | StageName.STATS dans l'ordre |

**Total suite** : 671 tests verts (était 600 avant S01).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `engagement_rate` retournait une valeur pour `view_count < 0`**
- **Found during:** Tests Hypothesis (Property 2 — zero-bug guard)
- **Issue:** Le code original utilisait `view_count == 0` mais Hypothesis a généré `view_count=-1` qui retournait `-0.0` au lieu de `None`
- **Fix:** Changement de `== 0` en `<= 0` dans `metrics.py:111`
- **Files modified:** `src/vidscope/domain/metrics.py`
- **Commit:** 60d7c2f

**2. [Rule 1 - Bug] `_ensure_video_stats_indexes` manquant pour les bases nouvelles**
- **Found during:** Test `test_init_db_is_idempotent_on_video_stats`
- **Issue:** `metadata.create_all()` crée la table `video_stats` mais pas les indexes nommés `idx_video_stats_video_id` / `idx_video_stats_captured_at` (SQLAlchemy génère seulement `sqlite_autoindex_video_stats_1` pour la UNIQUE constraint)
- **Fix:** Ajout de `_ensure_video_stats_indexes(conn)` appelé dans `init_db()` après `_ensure_video_stats_table(conn)`
- **Files modified:** `src/vidscope/adapters/sqlite/schema.py`
- **Commit:** 60d7c2f

**3. [Rule 1 - Bug] Test `test_uses_cookies_file_when_provided` chemin `/tmp` non-portable**
- **Found during:** Exécution tests `test_stats_probe.py` sur Windows
- **Issue:** `Path("/tmp/cookies.txt")` convertit en `\tmp\cookies.txt` sur Windows
- **Fix:** Utilisation de `tmp_path` pytest fixture pour créer un fichier temporaire cross-platform
- **Files modified:** `tests/unit/adapters/ytdlp/test_stats_probe.py`
- **Commit:** 60d7c2f

**4. [Rule 1 - Bug] Test `test_execution_order_is_declaration_order` dans `test_values.py` cassé**
- **Found during:** Suite complète `tests/unit/`
- **Issue:** Le test existant attendait exactement 5 valeurs dans `StageName`; l'ajout de `STATS` l'a cassé
- **Fix:** Ajout de `StageName.STATS` dans la liste attendue
- **Files modified:** `tests/unit/domain/test_values.py`
- **Commit:** 60d7c2f

## Known Stubs

Aucun stub — tous les modules livrent une implémentation complète. `YtdlpStatsProbe` retourne `VideoStats(video_id=VideoId(0), ...)` avec un sentinel id car le vrai DB id n'est pas connu au moment du probe (S02 résoudra cela avec `uow.videos.get_by_platform_id`). Ce sentinel est documenté et attendu — ce n'est pas un stub mais une décision de design (le probe ne connaît pas la DB).

## Threat Surface

Aucune nouvelle surface réseau non documentée. Les menaces sont toutes dans le `<threat_model>` du plan :

| Flag | File | Description |
|------|------|-------------|
| mitigated: T-DATA-01 | `ytdlp_stats_probe.py` | `_int_or_none()` filtre tout non-int des champs yt-dlp |
| mitigated: T-SQL-01 | `video_stats_repository.py` | SQLAlchemy Core paramétré, `int(video_id)` cast explicite |
| mitigated: T-INPUT-01 | `video_stats_repository.py` | `limit=100` / `limit=200` par défaut, pas de requêtes illimitées |
| accepted: T-PROBE-01 | `ytdlp_stats_probe.py` | Toute exception yt-dlp → `None`, pas de crash propagé |

## Self-Check

### Files Created/Modified — Verification
- `src/vidscope/domain/metrics.py` — FOUND
- `src/vidscope/ports/stats_probe.py` — FOUND
- `src/vidscope/adapters/sqlite/video_stats_repository.py` — FOUND
- `src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py` — FOUND
- `tests/unit/domain/test_metrics_property.py` — FOUND
- `tests/unit/adapters/sqlite/test_video_stats_repository.py` — FOUND
- `tests/unit/adapters/ytdlp/test_stats_probe.py` — FOUND

### Commits — Verification
- `60d7c2f` feat(M009-S01): engagement signals foundation — FOUND

## Self-Check: PASSED

Tous les fichiers créés existent. Le commit 60d7c2f est présent. 671 tests verts. 9/9 contrats import-linter verts. Gate Hypothesis verte (4 propriétés).
