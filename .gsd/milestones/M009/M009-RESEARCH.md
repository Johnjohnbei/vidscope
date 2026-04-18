# Phase M009: Engagement signals + velocity tracking — Research

**Researched:** 2026-04-18
**Domain:** Time-series stats table, velocity metrics, yt-dlp stats probe, SQLite append-only pattern, Hypothesis property tests
**Confidence:** HIGH (tout est basé sur le code existant vérifié en lecture directe + yt-dlp extractor vérifié)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Granularité d'idempotence : timestamp exact (seconde)**
Chaque `refresh-stats` crée toujours une nouvelle ligne. Idempotence transactionnelle via `INSERT ... ON CONFLICT DO NOTHING` sur `(video_id, captured_at)` à la seconde. Deux probes à 30 min d'intervalle → 2 lignes.

**D-02 — Champs `VideoStats` : 5 entiers tous `int | None`**
- `view_count: int | None`
- `like_count: int | None`
- `repost_count: int | None` (pas `share_count` — aligné sur le dict yt-dlp)
- `comment_count: int | None`
- `save_count: int | None`

Disponibilité par plateforme vérifiée dans les extractors yt-dlp :
| Champ | TikTok | Instagram | YouTube |
|-------|--------|-----------|---------|
| `view_count` | garanti | garanti | garanti |
| `like_count` | garanti | garanti | peut être `None` (caché) |
| `repost_count` | garanti | non exposé | non exposé |
| `comment_count` | garanti | garanti | garanti |
| `save_count` | garanti | non exposé | non exposé |

**D-03 — Champ manquant → `None`, jamais `0`**
`engagement_rate` n'utilise que les champs non-`None`.

**D-04 — `vidscope trending` CLI**
```
vidscope trending --since <window> [--platform instagram|tiktok|youtube] [--min-velocity 0] [--limit 20]
```
- `--since` obligatoire, pas de défaut silencieux
- Tri par `velocity_24h` descendant
- Format rich Table (cohérent avec `vidscope status`)
- SQL avec LIMIT poussé en base

**D-05 — `vidscope show` étendu avec section stats**
- Dernière capture : timestamp + compteurs
- Vélocité depuis l'historique complet (si >= 2 rows)
- Si 0 rows : message actionnable, pas de crash

### Claude's Discretion
- Formule exacte de `views_velocity_24h`
- Formule `engagement_rate`
- Formule `viral_coefficient` (peut être omis si définition floue)
- Placement migration (008 monolithique)
- Nombre exact de tests Hypothesis
- Index exact sur `video_stats`

### Deferred Ideas (OUT OF SCOPE)
- Push notifications quand vélocité dépasse un seuil
- Backfill historique depuis analytics tiers
- `vidscope list --sort-by velocity`
- `viral_coefficient` (si définition trop floue)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| R050 | Table `video_stats` append-only time-series — capturer l'évolution des compteurs | S01 : entité `VideoStats`, port `VideoStatsRepository`, adapter SQLite avec migration 008, `StatsProbe` + `YtdlpStatsProbe` |
| R051 | `vidscope refresh-stats` + extension `vidscope watch refresh` | S02 : `StatsStage` + `RefreshStatsUseCase` + CLI `stats.py` ; S03 : `RefreshWatchlistUseCase` étendu + `watch.py` étendu |
| R052 | `vidscope trending --since <window>` classe par vélocité | S04 : `metrics.py` pure-domain, `ListTrendingUseCase`, CLI `trending.py`, MCP tool `vidscope_trending` |
</phase_requirements>

---

## Summary

M009 ajoute une couche de signal temporel par-dessus la fondation hexagonale existante (M001–M008). La table `video_stats` est append-only : chaque sonde yt-dlp crée une nouvelle ligne horodatée, jamais une mise à jour. Les métriques dérivées (`views_velocity_24h`, `engagement_rate`) sont calculées à la lecture dans `metrics.py` — module pure-Python sans aucun import projet.

L'architecture en 4 slices suit exactement les patterns établis : `VideoStats` se modèle sur `FrameText` (side table avec FK `video_id`), `YtdlpStatsProbe` réutilise `extract_info(download=False)` déjà câblé dans `YtdlpDownloader.probe()`, `StatsStage` suit `VisualIntelligenceStage` (standalone, hors pipeline `add` par défaut), `ListTrendingUseCase` suit `SuggestRelatedUseCase`. L'extension de `RefreshWatchlistUseCase` pour S03 est additive : on ajoute une boucle stats après la boucle new-videos existante.

Le seul nouveau risque non-trivial est la gate Hypothesis (`test_metrics_property.py`) qui exige l'installation de `hypothesis` dans le groupe `dev` — ce paquet n'est pas encore dans `pyproject.toml`. Toutes les autres dépendances sont déjà disponibles.

**Recommandation principale :** Implémenter les 4 slices dans l'ordre de dépendance strict S01 → S02 → S03 → S04. Ne pas commencer S02 avant que S01 soit vert. `metrics.py` peut être développé en parallèle de S01 puisqu'il est pure-Python sans imports projet.

---

## Standard Stack

### Core
| Bibliothèque | Version | Usage | Raison |
|-------------|---------|-------|--------|
| SQLAlchemy Core | `>=2.0,<3` (déjà installé) | Table `video_stats`, requêtes trending avec LIMIT | Pattern établi — tous les adapters SQLite l'utilisent |
| yt-dlp | `>=2026.3` (déjà installé) | `extract_info(download=False)` pour sonder les stats | Seul extracteur multi-plateforme viable |
| rich | `>=14.0,<15` (déjà installé) | Table CLI pour `vidscope trending` + `vidscope show` stats | Cohérence avec `vidscope status` / `vidscope list` |
| Typer | `>=0.20,<1` (déjà installé) | CLI `vidscope refresh-stats` + `vidscope trending` | Framework CLI projet établi |
| hypothesis | `>=6.0` (à ajouter) | `test_metrics_property.py` — gate Hypothesis | Property-based testing pour monotonicity/additivity/zero-bug |

[VERIFIED: pyproject.toml — toutes les dépendances sauf hypothesis]
[VERIFIED: grep yt_dlp/extractor/tiktok.py — champs view_count/like_count/repost_count/comment_count/save_count garantis TikTok]

### Dépendances de dev à ajouter

```bash
# Ajouter hypothesis au groupe dev dans pyproject.toml :
# [dependency-groups]
# dev = [
#   ...existing...
#   "hypothesis>=6.0,<7",
# ]
uv sync
```

[ASSUMED] — La version `hypothesis>=6.0,<7` est compatible Python 3.12. Version exacte à vérifier via `npm view hypothesis version` ou équivalent PyPI.

---

## Architecture Patterns

### Structure de fichiers proposée

```
src/vidscope/
├── domain/
│   ├── entities.py          # + VideoStats (frozen dataclass, slots=True)
│   ├── values.py            # + VideoStatsId = NewType("VideoStatsId", int)
│   └── metrics.py           # NEW — pure-Python, zéro import projet
├── ports/
│   ├── repositories.py      # + VideoStatsRepository Protocol
│   └── stats_probe.py       # NEW — StatsProbe Protocol
├── adapters/
│   ├── ytdlp/
│   │   └── ytdlp_stats_probe.py  # NEW — YtdlpStatsProbe
│   └── sqlite/
│       ├── schema.py         # + video_stats table + _ensure_video_stats_table()
│       ├── video_stats_repository.py  # NEW
│       └── unit_of_work.py   # + video_stats: VideoStatsRepository
├── pipeline/
│   └── stages/
│       └── stats_stage.py   # NEW — StatsStage (standalone, hors add)
├── application/
│   ├── refresh_stats.py     # NEW — RefreshStatsUseCase
│   ├── list_trending.py     # NEW — ListTrendingUseCase
│   ├── watchlist.py         # MODIFIED — RefreshWatchlistUseCase étendu S03
│   └── show_video.py        # MODIFIED — ShowVideoResult étendu D-05
├── cli/
│   ├── commands/
│   │   ├── stats.py         # NEW — vidscope refresh-stats
│   │   ├── trending.py      # NEW — vidscope trending
│   │   ├── watch.py         # MODIFIED — résumé S03
│   │   └── show.py          # MODIFIED — section stats D-05
│   └── app.py               # + add_typer(stats_app) + add_typer(trending_app)
├── mcp/
│   ├── tools/
│   │   └── trending.py      # NEW ou inline dans server.py
│   └── server.py            # + vidscope_trending tool
└── infrastructure/
    └── container.py         # + YtdlpStatsProbe + VideoStatsRepositorySQLite
                             # + RefreshStatsUseCase + ListTrendingUseCase
```

[VERIFIED: lecture directe de tous les fichiers existants — aucun conflit de nommage]

### Pattern 1 : Entité VideoStats — frozen dataclass slots=True

```python
# Source: entities.py existant (patron FrameText)
# domain/entities.py

@dataclass(frozen=True, slots=True)
class VideoStats:
    """Snapshot de stats pour une vidéo à un instant donné.

    Append-only : une nouvelle ligne par sonde, jamais d'UPDATE.
    Idempotence : UNIQUE(video_id, captured_at) à la seconde (D-01).
    Champs manquants → None, jamais 0 (D-03).
    """
    video_id: VideoId
    captured_at: datetime          # UTC-aware, résolution seconde
    view_count: int | None = None
    like_count: int | None = None
    repost_count: int | None = None
    comment_count: int | None = None
    save_count: int | None = None
    id: int | None = None
    created_at: datetime | None = None
```

### Pattern 2 : Port VideoStatsRepository — Protocol runtime_checkable

```python
# Source: ports/repositories.py existant (patron HashtagRepository / FrameTextRepository)
# ports/repositories.py

@runtime_checkable
class VideoStatsRepository(Protocol):
    def append(self, stats: VideoStats) -> VideoStats:
        """INSERT ... ON CONFLICT DO NOTHING sur (video_id, captured_at).
        Retourne l'entité avec id populé, ou l'entité existante si conflit.
        JAMAIS d'UPDATE — append-only (D031).
        """
        ...

    def list_for_video(
        self, video_id: VideoId, *, limit: int = 100
    ) -> list[VideoStats]:
        """Retourne les rows pour video_id ordonnées par captured_at ASC."""
        ...

    def latest_for_video(self, video_id: VideoId) -> VideoStats | None:
        """Retourne la row la plus récente ou None."""
        ...

    def has_any_for_video(self, video_id: VideoId) -> bool:
        """True si au moins une row existe pour video_id."""
        ...

    def list_videos_with_min_snapshots(
        self, min_snapshots: int = 2, *, limit: int = 200
    ) -> list[VideoId]:
        """Retourne les video_id ayant >= min_snapshots rows.
        Utilisé par ListTrendingUseCase pour filtrer les candidats.
        """
        ...
```

### Pattern 3 : Table SQLite video_stats — append-only avec UNIQUE

```python
# Source: schema.py existant — patron frame_texts / hashtags
# adapters/sqlite/schema.py

video_stats = Table(
    "video_stats",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("view_count", Integer, nullable=True),
    Column("like_count", Integer, nullable=True),
    Column("repost_count", Integer, nullable=True),
    Column("comment_count", Integer, nullable=True),
    Column("save_count", Integer, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    ),
    UniqueConstraint(
        "video_id", "captured_at",
        name="uq_video_stats_video_id_captured_at",
    ),
)
Index("idx_video_stats_video_id", video_stats.c.video_id)
Index("idx_video_stats_captured_at", video_stats.c.captured_at)
```

Upgrade guard pour DBs existantes (patron `_ensure_videos_visual_columns`) :

```python
def _ensure_video_stats_table(conn: Connection) -> None:
    tables = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "video_stats" in tables:
        return
    conn.execute(text(
        "CREATE TABLE video_stats ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE, "
        "captured_at DATETIME NOT NULL, "
        "view_count INTEGER, like_count INTEGER, "
        "repost_count INTEGER, comment_count INTEGER, save_count INTEGER, "
        "created_at DATETIME NOT NULL, "
        "UNIQUE(video_id, captured_at)"
        ")"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_stats_video_id "
        "ON video_stats(video_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_stats_captured_at "
        "ON video_stats(captured_at)"
    ))
```

### Pattern 4 : StatsProbe Port + YtdlpStatsProbe Adapter

```python
# Source: ports/stats_probe.py — nouveau fichier, patron ProbeResult existant
# adapters/ytdlp/ytdlp_stats_probe.py — réutilise extract_info(download=False)

# Port (pure Python, stdlib only)
@runtime_checkable
class StatsProbe(Protocol):
    def probe_stats(self, url: str) -> VideoStats | None:
        """Retourne un VideoStats non-persisté avec captured_at=now().
        Retourne None si la plateforme ne retourne pas les stats.
        Ne lève jamais — erreurs encodées dans le retour None.
        """
        ...

# Adapter (adapters/ytdlp/)
class YtdlpStatsProbe:
    def probe_stats(self, url: str) -> VideoStats | None:
        options = {"quiet": True, "skip_download": True, ...}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            return None
        return VideoStats(
            video_id=VideoId(0),  # non-persisté, le caller fournit video_id
            captured_at=_truncate_to_second(datetime.now(UTC)),
            view_count=_int_or_none(info.get("view_count")),
            like_count=_int_or_none(info.get("like_count")),
            repost_count=_int_or_none(info.get("repost_count")),
            comment_count=_int_or_none(info.get("comment_count")),
            save_count=_int_or_none(info.get("save_count")),
        )
```

Note critique : `captured_at` doit être tronqué à la seconde (`replace(microsecond=0)`) pour que la contrainte UNIQUE `(video_id, captured_at)` fonctionne correctement (D-01).

[VERIFIED: yt_dlp/extractor/tiktok.py lignes 525-529 — repost_count = share_count, save_count = collect_count]
[VERIFIED: adapters/ytdlp/downloader.py ligne 304 — extract_info(download=False) pattern déjà utilisé dans probe()]

### Pattern 5 : StatsStage — standalone, hors pipeline add par défaut

```python
# Source: pipeline/stages/visual_intelligence.py — patron VisualIntelligenceStage
# pipeline/stages/stats_stage.py

class StatsStage:
    name: str = StageName.STATS.value  # StageName.STATS à ajouter dans values.py

    def __init__(self, *, stats_probe: StatsProbe) -> None:
        self._probe = stats_probe

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        # Toujours False — append-only, on ne "résume" jamais une probe stats
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        # 1. Probe via StatsProbe (download=False)
        # 2. Remplacer video_id=0 par ctx.video_id
        # 3. uow.video_stats.append(stats)
        # 4. Retourner StageResult(ok=True, ...)
        ...
```

`is_satisfied` retourne toujours `False` pour `StatsStage` : la logique "append-only" signifie qu'on veut toujours créer une nouvelle row sauf déduplification sur `(video_id, captured_at)` qui est gérée au niveau SQL.

### Pattern 6 : metrics.py — module pure-domain, zéro import projet

```python
# Source: KNOWLEDGE.md — "domain/metrics.py doit avoir zéro import projet (pure stdlib)"
# domain/metrics.py

from __future__ import annotations
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vidscope.domain.entities import VideoStats

def views_velocity_24h(history: list["VideoStats"]) -> float | None:
    """Vues gagnées par 24h, calculé par régression linéaire ou delta simple.

    Retourne None si history a < 2 rows.
    Retourne 0.0 si view_count est None sur toutes les rows.
    """
    rows_with_views = [r for r in history if r.view_count is not None]
    if len(rows_with_views) < 2:
        return None
    first, last = rows_with_views[0], rows_with_views[-1]
    delta_views = (last.view_count or 0) - (first.view_count or 0)
    delta_seconds = (last.captured_at - first.captured_at).total_seconds()
    if delta_seconds <= 0:
        return None
    return delta_views / delta_seconds * 86400  # vues/jour

def engagement_rate(latest: "VideoStats") -> float | None:
    """(like + comment) / view_count sur la dernière snapshot.

    Retourne None si view_count est None ou 0.
    N'utilise que les champs non-None (D-03).
    """
    if latest.view_count is None or latest.view_count == 0:
        return None
    numerator = (latest.like_count or 0) + (latest.comment_count or 0)
    return numerator / latest.view_count
```

Note sur `viral_coefficient` : étant donné l'ambiguïté de définition documentée dans CONTEXT.md, le planning doit l'omettre de S01. C'est dans "Claude's Discretion" mais le risque de définition floue justifie l'omission.

[VERIFIED: KNOWLEDGE.md ligne 15 — "domain/ has zero project imports (pure stdlib + typing only)"]
[VERIFIED: CONTEXT.md — viral_coefficient dans Claude's Discretion avec mention explicite "peut être omis de S01"]

### Pattern 7 : Extension UnitOfWork — video_stats repo

```python
# Source: ports/unit_of_work.py + adapters/sqlite/unit_of_work.py existants
# Additions in both files:

# ports/unit_of_work.py — ajouter dans UnitOfWork Protocol
video_stats: VideoStatsRepository

# adapters/sqlite/unit_of_work.py — dans __enter__
self.video_stats = VideoStatsRepositorySQLite(self._connection)
```

### Pattern 8 : ListTrendingUseCase — SQL avec LIMIT en base

```python
# Source: CONTEXT.md D-04 — "requête SQL avec LIMIT poussé en base"
# application/list_trending.py

class ListTrendingUseCase:
    """Classe les vidéos par velocity_24h sur la fenêtre donnée.

    La requête SQL évite de charger toute video_stats en mémoire :
    - Agrège view_count min/max par video_id sur la fenêtre temporelle
    - Calcule un delta approximatif en SQL
    - Filtre par platform et min_velocity si fournis
    - Retourne au plus `limit` résultats
    """
```

Note : le calcul exact de `velocity_24h` sera dans `metrics.py` (pure-domain), mais pour la requête de ranking SQL on peut utiliser une approximation `(max_views - min_views) / hours * 24`. L'exact `metrics.views_velocity_24h` est appelé sur les résultats pour l'affichage.

### Anti-Patterns à éviter

- **Ajouter `view_count` directement sur `Video`** : la table `videos` a déjà un `view_count` snapshot-at-ingest. `video_stats` est la source de vérité temporelle — ne pas confondre.
- **`StatsStage` dans le pipeline add par défaut** : doit rester standalone (non enregistré dans `PipelineRunner.stages` par défaut) — même pattern que `VisualIntelligenceStage` qui est standalone.
- **Stocker 0 quand yt-dlp retourne None** : viole D-03, fausse l'`engagement_rate` sur Instagram et YouTube.
- **`captured_at` avec microseconds** : la contrainte UNIQUE est à la seconde — `datetime.now(UTC).replace(microsecond=0)` obligatoire.
- **`viral_coefficient` avec définition floue** : mieux l'omettre que de livrer une métrique trompeuse.
- **Importer yt-dlp dans domain/ ou ports/** : interdit par import-linter (`domain-is-pure` + `ports-are-pure`).

---

## Don't Hand-Roll

| Problème | Ne pas construire | Utiliser à la place | Raison |
|---------|-------------------|---------------------|--------|
| Téléchargement metadata sans média | Appel custom requests | `yt_dlp.YoutubeDL.extract_info(download=False)` | Déjà testé dans `probe()` de `YtdlpDownloader` |
| Idempotence sur timestamp | Logique applicative de dédup | `INSERT ... ON CONFLICT DO NOTHING` sur `UNIQUE(video_id, captured_at)` | SQLite gère ça en atomique |
| Ranking en mémoire | Charger toute video_stats | SQL avec `GROUP BY video_id, MAX/MIN view_count, LIMIT N` | Scalabilité (D-04) |
| Property-based testing des formules | Tests exhaustifs manuels | Hypothesis `@given` avec `st.lists`, `st.integers` | Découvre les edge cases non prévus (négatifs, overflow) |
| Rich Table pour trending | Formatting manuel | `rich.table.Table` — déjà utilisé dans `watch.py` et `list.py` | Cohérence visuelle et ASCII-safe (KNOWLEDGE.md) |

---

## Runtime State Inventory

> Pas de phase rename/refactor — section non applicable.

M009 est une phase **additive** (nouveaux fichiers + extensions). Aucune donnée existante en base n'est renommée. Le seul impact sur l'état runtime est :

- **Table `video_stats`** : créée par `_ensure_video_stats_table()` dans `init_db()` au premier démarrage après le merge. Aucune migration de données existantes requise.
- **`StageName.STATS`** : nouvelle valeur d'enum. Les `pipeline_runs` existants avec les anciens stages ne sont pas affectés (enum est additif).
- **`UnitOfWork.video_stats`** : nouveau champ. Les tests existants qui mockent `UnitOfWork` devront ajouter ce champ — à vérifier au moment de l'implémentation.

---

## Common Pitfalls

### Pitfall 1 : `captured_at` avec microseconds casse l'UNIQUE constraint
**Ce qui arrive :** Deux appels dans la même seconde créent deux rows distinctes alors qu'elles devraient être dédupliquées. Ou inversement, deux appels légitimement distants sont dédupliqués si on arrondit trop large.
**Cause racine :** `datetime.now(UTC)` inclut les microseconds ; SQLite stocke avec une résolution sous-seconde.
**Comment éviter :** Toujours `captured_at = datetime.now(UTC).replace(microsecond=0)` dans `YtdlpStatsProbe.probe_stats()`.
**Signe d'alerte :** Test d'idempotence avec deux probes dans la même seconde qui crée 2 rows.

### Pitfall 2 : `engagement_rate` biaisé par champs absents remplacés par 0
**Ce qui arrive :** Instagram n'expose pas `repost_count`/`save_count`. Si on stocke 0, `engagement_rate` compare des plateformes avec des formules différentes.
**Cause racine :** Tentation de "normaliser" les None en 0.
**Comment éviter :** Respecter D-03 — `None` partout où yt-dlp ne retourne pas le champ. `metrics.engagement_rate` ne doit utiliser que les champs `not None`.
**Signe d'alerte :** Test sur Instagram qui affiche un taux d'engagement différent selon la présence de `repost_count=0` vs `repost_count=None`.

### Pitfall 3 : `StatsStage` enregistré dans le pipeline add
**Ce qui arrive :** Chaque `vidscope add <url>` exécute une probe stats en plus de l'ingest normal, ralentissant la commande principale et peuplant des rows non désirées.
**Cause racine :** Copier le pattern `AnalyzeStage` (enregistré dans le pipeline add) au lieu de `VisualIntelligenceStage` (standalone).
**Comment éviter :** Instancier `StatsStage` dans `build_container()` mais NE PAS l'inclure dans la liste `stages=` du `PipelineRunner`. Il doit être accessible via `container.stats_stage` uniquement pour `RefreshStatsUseCase`.
**Signe d'alerte :** Le test `vidscope add <url>` crée une row `video_stats`.

### Pitfall 4 : `metrics.py` qui importe des entités projet directement
**Ce qui arrive :** Import-linter échoue avec `domain-is-pure` contract violated.
**Cause racine :** `VideoStats` est dans `domain/entities.py` — on est tenté de l'importer directement.
**Comment éviter :** Utiliser `TYPE_CHECKING` pour les annotations de type, ou passer les données comme des dicts/tuples simples si les annotations causent des problèmes avec import-linter.
**Alternative confirmée :** `from __future__ import annotations` + `if TYPE_CHECKING: from vidscope.domain.entities import VideoStats` est un pattern stdlib (pas d'import runtime). Vérifier que import-linter tolère ce pattern (il le fait sur les autres modules domain).

### Pitfall 5 : `vidscope trending --since` sans validation du format window
**Ce qui arrive :** `--since 7d` fonctionne mais `--since 7` ou `--since 1week` crashe avec une erreur cryptique.
**Cause racine :** Parsing naïf du format window.
**Comment éviter :** Définir un parser de window strict (`7d`, `24h`, `30d`, etc.) avec erreur claire sur format invalide. Le schéma `N(d|h|w)` couvre 99% des cas d'usage.

### Pitfall 6 : `RefreshWatchlistUseCase` étendu qui casse les tests existants
**Ce qui arrive :** L'extension S03 ajoute `stats_probe` au constructeur de `RefreshWatchlistUseCase`, cassant les 23 tests unitaires existants.
**Cause racine :** Injection de dépendance obligatoire vs optionnelle.
**Comment éviter :** Rendre `stats_probe: StatsProbe | None = None` avec comportement conditionnel, ou créer un nouveau use case `RefreshStatsForWatchlistUseCase` séparé appelé depuis le CLI. La deuxième option est plus propre architecturalement.
**Recommandation :** Séparer clairement `RefreshWatchlistUseCase` (M003, inchangé) et l'extension stats dans un appel séparé depuis le CLI `watch.py` — le CLI orchestre les deux.

### Pitfall 7 : Hypothesis non installé bloque la gate de merge
**Ce qui arrive :** `test_metrics_property.py` échoue avec `ModuleNotFoundError: No module named 'hypothesis'`.
**Cause racine :** `hypothesis` n'est pas dans `pyproject.toml` (vérifié).
**Comment éviter :** Ajouter `"hypothesis>=6.0,<7"` dans `[dependency-groups] dev = [...]` dans `pyproject.toml` et relancer `uv sync` dans Wave 0.

[VERIFIED: pyproject.toml ligne 209-215 — hypothesis absent des dev dependencies]

---

## Code Examples

### Append avec ON CONFLICT DO NOTHING

```python
# Source: adapters/sqlite/video_repository.py — patron sqlite_insert
# adapters/sqlite/video_stats_repository.py

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

def append(self, stats: VideoStats) -> VideoStats:
    payload = _stats_to_row(stats)
    stmt = sqlite_insert(video_stats_table).values(**payload)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["video_id", "captured_at"]
    )
    self._conn.execute(stmt)
    # Récupérer la row existante ou insérée
    existing = self.latest_for_video(stats.video_id)
    return existing or stats
```

### Requête trending SQL avec LIMIT en base

```python
# Source: CONTEXT.md D-04 — "requête SQL avec LIMIT poussé en base"
# adapters/sqlite/ ou application/list_trending.py

from sqlalchemy import select, func, text

# Approximation SQL pour ranking :
# Pour chaque video_id dans la fenêtre temporelle,
# delta_views = MAX(view_count) - MIN(view_count)
# velocity_approx = delta_views / elapsed_hours * 24
since_dt = datetime.now(UTC) - timedelta(hours=window_hours)

subq = (
    select(
        video_stats_table.c.video_id,
        (func.max(video_stats_table.c.view_count) -
         func.min(video_stats_table.c.view_count)).label("delta_views"),
        func.count(video_stats_table.c.id).label("snapshot_count"),
    )
    .where(video_stats_table.c.captured_at >= since_dt)
    .where(video_stats_table.c.view_count.isnot(None))
    .group_by(video_stats_table.c.video_id)
    .having(text("snapshot_count >= 2"))
    .order_by(text("delta_views DESC"))
    .limit(limit)
    .subquery()
)
```

### Test Hypothesis — gate property metrics

```python
# Source: ROADMAP M009 — test_metrics_property.py obligatoire
# tests/unit/domain/test_metrics_property.py

from hypothesis import given, assume, settings
from hypothesis import strategies as st
from vidscope.domain.metrics import views_velocity_24h, engagement_rate

@given(
    st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        min_size=2,
        max_size=50,
    )
)
def test_velocity_is_non_negative_for_monotonically_increasing_views(view_counts):
    """Monotonicity : si view_count croît, velocity >= 0."""
    # Construire une liste de VideoStats avec view_counts croissants
    history = _make_history(sorted(view_counts))
    result = views_velocity_24h(history)
    if result is not None:
        assert result >= 0.0
```

### CLI trending avec rich Table et ASCII-safe (KNOWLEDGE.md)

```python
# Source: cli/commands/watch.py — patron Table existant
# KNOWLEDGE.md ligne 104 — "use plain ASCII tags in CLI output"
# cli/commands/trending.py

from rich.table import Table
from vidscope.cli._support import console

table = Table(title=f"Trending ({len(results)})", show_header=True)
table.add_column("#", justify="right", style="dim")
table.add_column("title", max_width=40)
table.add_column("platform")
table.add_column("velocity_24h", justify="right")  # vues/jour
table.add_column("engagement%", justify="right")
table.add_column("last capture")

for i, item in enumerate(results, 1):
    table.add_row(
        str(i),
        (item.title or "?")[:40],
        item.platform.value,
        f"{item.velocity_24h:.0f}" if item.velocity_24h else "-",
        f"{item.engagement_rate*100:.1f}%" if item.engagement_rate else "-",
        item.last_captured_at.strftime("%Y-%m-%d %H:%M"),
    )
console.print(table)
```

---

## State of the Art

| Ancienne approche | Approche actuelle | Depuis | Impact |
|-------------------|-------------------|--------|--------|
| `videos.view_count` = snapshot unique d'ingest | `video_stats` append-only + calcul à la lecture | M009 | Velocity et tendances deviennent calculables |
| Stage always-in-pipeline | Stage standalone (VisualIntelligenceStage M008) | M008 | `StatsStage` suit le même patron |
| `StageName` sans STATS | `StageName.STATS` ajouté à l'enum | M009 | Cohérence avec pipeline_runs tracking |

**Déprécié / attention :**
- `videos.view_count` : reste présent comme snapshot d'ingest mais ne doit PAS être utilisé pour le trending — utiliser `video_stats` uniquement.

---

## Assumptions Log

| # | Claim | Section | Risk si faux |
|---|-------|---------|--------------|
| A1 | `hypothesis>=6.0,<7` est compatible Python 3.12 et aucun conflit de version | Standard Stack | Faible — hypothesis 6.x supporte Python 3.12 depuis longtemps ; à vérifier via PyPI au moment du Wave 0 |
| A2 | `TYPE_CHECKING` pattern dans `metrics.py` est toléré par import-linter (pas d'import runtime de `domain`) | Architecture Patterns | Faible — ce pattern est déjà utilisé dans `ports/unit_of_work.py` ligne 47-51 [VERIFIED] |
| A3 | Instagram expose `view_count` et `like_count` via `extract_info(download=False)` avec cookies valides | StatsProbe | Moyen — non vérifié sur un vrai compte Instagram avec cookies ; les extractors yt-dlp le documentent mais la plateforme peut changer |
| A4 | La formule `velocity_24h = delta_views / elapsed_seconds * 86400` (régression linéaire simplifiée) est acceptable comme recommandation "Claude's Discretion" | metrics.py | Faible — la formule est dans Claude's Discretion ; si le planneur préfère une autre formule, ce n'est pas un blocant |

---

## Open Questions

1. **Séparation ou extension de `RefreshWatchlistUseCase` pour S03**
   - Ce qu'on sait : le use case existant a 23 tests et prend `pipeline_runner + downloader + clock + unit_of_work_factory`
   - Ce qui est flou : ajouter `stats_probe: StatsProbe | None = None` rend l'extension rétrocompatible mais complique la logique ; créer un use case séparé est plus propre mais double le code CLI
   - Recommandation : laisser `RefreshWatchlistUseCase` inchangé (M003) ; le CLI `watch refresh` appelle successivement les deux use cases : `RefreshWatchlistUseCase` (nouvelles vidéos) puis `RefreshStatsForWatchlistUseCase` (stats refresh). Cela préserve les 23 tests existants.

2. **`StageName.STATS` dans l'enum ou pas ?**
   - Ce qu'on sait : `StageName` est dans `domain/values.py` et `pipeline_runs.phase` stocke la valeur string
   - Ce qui est flou : `StatsStage` écrit-il dans `pipeline_runs` ? Si oui, `StageName.STATS` est nécessaire. Si non (stage standalone sans pipeline_runs tracking), ce n'est pas nécessaire.
   - Recommandation : `StatsStage` DOIT écrire dans `pipeline_runs` pour la visibilité `vidscope status` — donc `StageName.STATS = "stats"` doit être ajouté.

3. **Format exact de `--since` window**
   - Ce qu'on sait : le CONTEXT.md mentionne `--since 7d` comme exemple ; `--since` est obligatoire sans défaut
   - Ce qui est flou : faut-il supporter `24h`, `7d`, `30d` uniquement, ou aussi `1w`, `2h` etc. ?
   - Recommandation : parser minimal `N(h|d)` — heures et jours suffisent pour le cas d'usage. Convertir en `timedelta` avec une fonction `parse_window(s: str) -> timedelta`.

---

## Environment Availability

| Dépendance | Requise par | Disponible | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| yt-dlp | `YtdlpStatsProbe.probe_stats()` | oui | `>=2026.3` dans `.venv` | — |
| SQLAlchemy | `VideoStatsRepositorySQLite` | oui | `>=2.0` | — |
| rich | CLI `vidscope trending` | oui | `>=14.0` | — |
| Typer | CLI stats + trending | oui | `>=0.20` | — |
| hypothesis | `test_metrics_property.py` | **non** | absent de pyproject.toml | Aucun — à ajouter dans Wave 0 |
| Python 3.12+ | Tout | oui | 3.12 (pyproject.toml) | — |

[VERIFIED: pyproject.toml — hypothesis absent, toutes les autres dépendances présentes]

**Dépendances manquantes sans fallback :**
- `hypothesis` — bloque `test_metrics_property.py` (gate non-négociable selon ROADMAP). Action Wave 0 : ajouter `"hypothesis>=6.0,<7"` dans `[dependency-groups] dev` de `pyproject.toml` et relancer `uv sync`.

---

## Validation Architecture

### Test Framework
| Propriété | Valeur |
|-----------|--------|
| Framework | pytest 9.x (pyproject.toml `>=9.0,<10`) |
| Fichier config | `pyproject.toml` `[tool.pytest.ini_options]` |
| Commande rapide | `uv run pytest tests/unit/ -x -q` |
| Suite complète | `uv run pytest -x -q` (hors integration par défaut) |

### Phase Requirements → Test Map

| Req ID | Comportement | Type de test | Commande automatisée | Fichier existant ? |
|--------|-------------|-------------|---------------------|---------------------|
| R050 | `VideoStats` frozen dataclass immutable | unit domain | `pytest tests/unit/domain/test_entities.py -x` | ❌ Wave 0 |
| R050 | `VideoStats` — None != 0 pour champs absents | unit domain | `pytest tests/unit/domain/test_entities.py -x` | ❌ Wave 0 |
| R050 | `velocity_24h` monotonicity (Hypothesis) | unit domain property | `pytest tests/unit/domain/test_metrics_property.py -x` | ❌ Wave 0 |
| R050 | `engagement_rate` zero-bug (Hypothesis) | unit domain property | `pytest tests/unit/domain/test_metrics_property.py -x` | ❌ Wave 0 |
| R050 | `YtdlpStatsProbe` — download=False forcé | unit adapter | `pytest tests/unit/adapters/ytdlp/test_stats_probe.py -x` | ❌ Wave 0 |
| R050 | `VideoStatsRepositorySQLite` append-only (pas d'UPDATE) | unit adapter | `pytest tests/unit/adapters/sqlite/test_video_stats_repository.py -x` | ❌ Wave 0 |
| R050 | Idempotence `(video_id, captured_at)` — double append dans la même seconde = 1 row | unit adapter | `pytest tests/unit/adapters/sqlite/test_video_stats_repository.py -x` | ❌ Wave 0 |
| R050 | Migration 008 — `video_stats` créée sur DB existante | unit adapter | `pytest tests/unit/adapters/sqlite/test_schema.py -x` | fichier existe, test à ajouter |
| R051 | `StatsStage.is_satisfied` toujours False | unit pipeline | `pytest tests/unit/pipeline/ -x` | ❌ Wave 0 |
| R051 | `RefreshStatsUseCase` avec probe+repo InMemory | unit application | `pytest tests/unit/application/test_refresh_stats.py -x` | ❌ Wave 0 |
| R051 | `vidscope refresh-stats --all` CLI snapshot | unit CLI | `pytest tests/unit/cli/test_stats.py -x` | ❌ Wave 0 |
| R051 | `vidscope watch refresh` résumé avec stats-refreshed counter | unit CLI | `pytest tests/unit/cli/test_watch.py -x` | fichier existe, test à ajouter |
| R052 | `ListTrendingUseCase` ranking correctness | unit application | `pytest tests/unit/application/test_list_trending.py -x` | ❌ Wave 0 |
| R052 | `vidscope trending --since 7d` CLI snapshot | unit CLI | `pytest tests/unit/cli/test_trending.py -x` | ❌ Wave 0 |
| R052 | `vidscope_trending` MCP tool | unit MCP | `pytest tests/unit/mcp/ -x` | fichier existe, test à ajouter |
| Architecture | 9 contrats import-linter verts + metrics.py pure | architecture | `pytest tests/architecture/ -x` | fichier existe |

### Sampling Rate
- **Par commit de tâche :** `uv run pytest tests/unit/ -x -q`
- **Par merge de wave :** `uv run pytest -x -q` (inclut architecture)
- **Gate de phase :** Suite complète verte + `test_metrics_property.py` Hypothesis vert avant `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/domain/test_entities.py` — ajouter tests VideoStats (immuabilité, None != 0)
- [ ] `tests/unit/domain/test_metrics_property.py` — créer avec Hypothesis (monotonicity, additivity, zero-bug)
- [ ] `tests/unit/adapters/ytdlp/test_stats_probe.py` — créer (download=False forcé, shape de retour)
- [ ] `tests/unit/adapters/sqlite/test_video_stats_repository.py` — créer (append-only, idempotence)
- [ ] `tests/unit/pipeline/` — ajouter `test_stats_stage.py`
- [ ] `tests/unit/application/test_refresh_stats.py` — créer
- [ ] `tests/unit/application/test_list_trending.py` — créer
- [ ] `tests/unit/cli/test_stats.py` — créer
- [ ] `tests/unit/cli/test_trending.py` — créer
- [ ] `pyproject.toml` — ajouter `"hypothesis>=6.0,<7"` dans dev group + `uv sync`

---

## Security Domain

> `security_enforcement` non configuré (absent = activé).

### Applicable ASVS Categories

| Catégorie ASVS | Applicable | Contrôle standard |
|----------------|-----------|-------------------|
| V2 Authentication | non | Single-user local tool (R032) |
| V3 Session Management | non | Single-user local tool |
| V4 Access Control | non | Single-user local tool |
| V5 Input Validation | oui (faible) | Parser `--since` window avec validation stricte |
| V6 Cryptography | non | Pas de chiffrement impliqué |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Mitigation standard |
|---------|--------|---------------------|
| SQL injection via `--since` window ou `--platform` | Tampering | SQLAlchemy Core parameterized queries — pas de `.raw()` ou `text()` avec f-string |
| Données yt-dlp non validées stockées telles quelles | Tampering | `_int_or_none()` helper sur chaque champ stats (pattern déjà utilisé dans `downloader.py`) |
| `--limit 0` ou valeur négative | DOS | Validation Typer `min=1` sur `--limit` |

**Note :** VidScope est un outil local single-user (R032). La surface d'attaque est minimale. Les validations à appliquer sont défensives, pas une contrainte de sécurité critique.

---

## Sources

### Primary (HIGH confidence)
- Lecture directe `src/vidscope/domain/entities.py` — structure existante des entités
- Lecture directe `src/vidscope/ports/repositories.py` — patron Protocol runtime_checkable
- Lecture directe `src/vidscope/adapters/sqlite/schema.py` — patron table SQLite + _ensure_* helpers
- Lecture directe `src/vidscope/adapters/sqlite/unit_of_work.py` — câblage repos dans __enter__
- Lecture directe `src/vidscope/adapters/ytdlp/downloader.py` lignes 278-350 — `extract_info(download=False)` pattern
- Lecture directe `src/vidscope/pipeline/stages/visual_intelligence.py` — patron stage standalone
- Lecture directe `src/vidscope/cli/commands/watch.py` — patron rich Table + handle_domain_errors
- Lecture directe `src/vidscope/application/show_video.py` — patron ShowVideoResult extensible
- Lecture directe `.venv/Lib/site-packages/yt_dlp/extractor/tiktok.py` lignes 525-529 — champs garantis TikTok
- Lecture directe `pyproject.toml` — dépendances actuelles, absence de hypothesis
- Lecture directe `.importlinter` — 9 contrats, dont `domain-is-pure` et `ports-are-pure`
- Lecture directe `.gsd/KNOWLEDGE.md` — forbidden moves, idempotence contract, test layering

### Secondary (MEDIUM confidence)
- `.gsd/milestones/M009/M009-CONTEXT.md` — décisions D-01 à D-05 (décisions utilisateur)
- `.gsd/milestones/M009/M009-ROADMAP.md` — architecture 4 slices, stratégie de test

### Tertiary (LOW confidence)
- Aucun — toutes les claims sont vérifiées sur le code existant

---

## Metadata

**Confidence breakdown :**
- Standard stack : HIGH — tout vérifié dans pyproject.toml et code existant
- Architecture : HIGH — patterns vérifiés par lecture directe des 8+ fichiers sources
- Pitfalls : HIGH — déduits des patterns existants et des décisions CONTEXT.md
- Test map : MEDIUM — les fichiers Wave 0 n'existent pas encore (normal à ce stade)

**Research date :** 2026-04-18
**Valid until :** 2026-05-18 (stable — pas de dépendances yt-dlp fragiles dans ce scope)
