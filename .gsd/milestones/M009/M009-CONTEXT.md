# Phase M009: Engagement signals + velocity time-series — Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

M009 introduit la table `video_stats` append-only pour capturer l'évolution des compteurs dans le temps. La vélocité et le taux d'engagement sont calculés à la lecture depuis l'historique. `vidscope refresh-stats` sonde les vidéos déjà ingérées via yt-dlp `download=False`. `vidscope trending` classe par vélocité. `vidscope watch refresh` est étendu pour rafraîchir les stats en plus des nouvelles vidéos.

**4 slices :**
- S01 : Domain + table `video_stats` + port `StatsProbe` + adapter `YtdlpStatsProbe`
- S02 : `StatsStage` standalone + `vidscope refresh-stats` CLI
- S03 : Extension `vidscope watch refresh` (stats refresh loop)
- S04 : `metrics.py` (pure domain) + `vidscope trending` CLI + MCP tool `vidscope_trending`

**Out of M009 :**
- Scheduler intégré (les users utilisent cron/Task Scheduler — M003)
- Push notifications quand une vidéo passe un seuil de vélocité
- Backfill historique depuis des analytics tiers
- Sentiment par commentaire (seuls les comptaires sont téléchargés)

</domain>

<decisions>
## Implementation Decisions

### D-01 : Granularité du bucket d'idempotence — timestamp exact
Chaque appel à `refresh-stats` crée toujours une nouvelle ligne dans `video_stats`, quelle que soit la fréquence des appels. Pas de déduplication par fenêtre temporelle (pas de bucket horaire/journalier). L'idempotence mentionnée dans le ROADMAP désigne l'idempotence transactionnelle de la ligne elle-même (re-run du stage ne duplique pas via `INSERT ... ON CONFLICT DO NOTHING` sur la clé composite `(video_id, captured_at)` avec résolution à la seconde), pas un bucket de déduplication intentionnel. Deux probes à 30 minutes d'intervalle → 2 lignes → meilleure résolution time-series.

### D-02 : `VideoStats` — champs garantis par plateforme
L'entité `VideoStats` expose 5 compteurs, tous `int | None` :
- `view_count: int | None`
- `like_count: int | None`
- `repost_count: int | None` — **pas `share_count`** : yt-dlp mappe les partages TikTok vers `repost_count`
- `comment_count: int | None`
- `save_count: int | None`

Disponibilité réelle par plateforme (vérifiée dans les extractors yt-dlp) :
| Champ | TikTok | Instagram | YouTube |
|-------|--------|-----------|---------|
| `view_count` | ✅ garanti | ✅ garanti | ✅ garanti |
| `like_count` | ✅ garanti | ✅ garanti | ✅ (peut être caché → `None`) |
| `repost_count` | ✅ garanti | ❌ non exposé | ❌ non exposé |
| `comment_count` | ✅ garanti | ✅ garanti | ✅ garanti |
| `save_count` | ✅ garanti | ❌ non exposé | ❌ non exposé |

`None` = non mesuré (différent de zéro). Ne jamais substituer `0` à `None` — ça fausserait l'`engagement_rate`.

### D-03 : Métriques manquantes → `None`, jamais `0`
Quand yt-dlp ne retourne pas un champ (Instagram sans share, YouTube sans save), on stocke `None`. L'`engagement_rate` dans `metrics.py` ne doit utiliser que les champs non-`None` dans sa formule pour éviter les biais de plateforme.

### D-04 : `vidscope trending` — output et seuils
```
vidscope trending --since <window> [--platform instagram|tiktok|youtube] [--min-velocity 0] [--limit 20]
```
- **`--since` obligatoire** — pas de défaut silencieux (la fenêtre change radicalement les résultats)
- **`--limit 20` par défaut** — `--limit N` pour surcharger
- **`--min-velocity 0` par défaut** — pas de filtre minimum (l'utilisateur resserre si besoin)
- **Colonnes** : rang · titre (40 chars max) · plateforme · velocity_24h (vues/jour) · engagement_rate (%) · dernière capture
- **Tri** : velocity_24h descendant par défaut
- **Format** : `rich` Table (cohérent avec `vidscope status` existant)
- **Scalabilité** : requête SQL avec LIMIT poussé en base — ne charge pas toute la table en mémoire

### D-05 : `vidscope show` — section stats ajoutée
M009 étend `vidscope show <id>` avec une section stats affichant :
- Dernière capture : timestamp + compteurs (view/like/repost/comment/save — `None` si non disponible)
- Vélocité calculée depuis l'historique complet (si ≥2 rows dans `video_stats`)
- Si zéro rows dans `video_stats` : "Aucune stat capturée — lancez `vidscope refresh-stats <id>`"

### Claude's Discretion
- Formule exacte de `views_velocity_24h` (views gained over last 24h window vs average hourly rate × 24 vs linear regression slope)
- Formule `engagement_rate` (like+comment / view_count sur dernière snapshot vs moyenne)
- Formule `viral_coefficient` (optionnel — si définition trop incertaine, peut être omis de S01)
- Placement de la migration (008 monolithique)
- Nombre exact de tests par formule (≥ gate Hypothesis pour monotonicity/additivity/zero-bug)
- Index exact sur `video_stats` (au minimum `(video_id, captured_at)`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap M009
- `.gsd/milestones/M009/M009-ROADMAP.md` — 4 slices, layer architecture, test strategy complète, gate Hypothesis, E2E script `verify-m009.sh`

### Fondation domaine existante
- `src/vidscope/domain/entities.py` — `Video` dataclass (M009 ajoute `VideoStats` séparé, pas de colonnes sur `Video`)
- `src/vidscope/domain/values.py` — `Platform` enum
- `src/vidscope/ports/repositories.py` — protocols Repository existants (patron à miroir pour `VideoStatsRepository`)

### Adapter ytdlp — probe déjà câblé
- `src/vidscope/adapters/ytdlp/downloader.py` — méthode `probe()` (lignes ~278-340) utilise déjà `extract_info(download=False)` ; `YtdlpStatsProbe` peut s'appuyer sur ce pattern ou le réutiliser directement

### Patterns SQLite existants
- `src/vidscope/adapters/sqlite/video_repository.py` — `_video_to_row` / `_row_to_video`, pattern migration
- `src/vidscope/adapters/sqlite/creator_repository.py` — patron side table (FK + upsert) à miroir pour `video_stats`
- `src/vidscope/adapters/sqlite/schema.py` — voir les migrations existantes (001–007) pour numéroter 008

### Pipeline patterns
- `src/vidscope/pipeline/stages/visual_intelligence.py` — stage standalone récent (M008) : patron à suivre pour `StatsStage` non-inclus dans le graphe `add` par défaut
- `src/vidscope/pipeline/runner.py` — comment enregistrer un stage standalone

### CLI patterns
- `src/vidscope/cli/commands/watch.py` — à étendre pour S03 (boucle stats refresh + résumé "N nouvelles vidéos + M stats rafraîchies")
- `src/vidscope/cli/commands/show.py` — à étendre pour D-05 (section stats)
- `src/vidscope/mcp/server.py` — patron tool closure + DomainError trap pour `vidscope_trending`

### Décisions architecturales bloquantes
- `.gsd/DECISIONS.md` — D019-D023 (hexagonal strict, import-linter), D025 (is_satisfied behavior), D006 (SQLAlchemy Core thin layer)
- `.gsd/KNOWLEDGE.md` — règles forbidden moves, idempotence contract, test layering

### Champs yt-dlp par plateforme (vérifiés)
- `.venv/Lib/site-packages/yt_dlp/extractor/tiktok.py` lignes ~525-529, ~679-683, ~719-753 — mapping `view_count`/`like_count`/`repost_count`/`comment_count`/`save_count` (tous garantis)
- `.venv/Lib/site-packages/yt_dlp/extractor/instagram.py` lignes ~103-105, ~151-153 — `view_count`/`like_count`/`comment_count` (pas de `share`/`save`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `YtdlpDownloader.probe()` — déjà `extract_info(download=False)`, retourne `ProbeResult` avec `view_count` dans `metadata`. `YtdlpStatsProbe` peut déléguer à cette méthode ou copier le pattern en extrayant les 5 champs supplémentaires.
- `VisualIntelligenceStage` (M008) — modèle de stage standalone non inclus dans le pipeline `add` par défaut : pattern direct pour `StatsStage`
- `rich` Table — déjà utilisé dans `vidscope status` / `vidscope list`
- `UnitOfWork` — expose tous les repos ; `VideoStatsRepository` doit y être ajouté

### Established Patterns
- Frozen dataclass + `slots=True` pour chaque nouvelle entité
- `_row_to_entity` / `_entity_to_row` helpers dans chaque SQLite adapter
- Migration numérotée (`007_ocr.py` → `008_video_stats.py`)
- Stage `is_satisfied()` → pour `StatsStage` : `False` toujours (append-only, on ne "résume" pas une probe)
- Import-linter strict — `domain/metrics.py` doit avoir zéro import projet (pure stdlib)

### Integration Points
- `ShowVideoUseCase` → étendre pour lire `VideoStatsRepository` et afficher dernière snapshot + vélocité (D-05)
- `RefreshWatchlistUseCase` → étendre pour S03 : après la boucle new-videos, run `StatsStage` sur tous les vidéos connus du créateur
- `Container` (infrastructure) → câbler `YtdlpStatsProbe` + `VideoStatsRepositorySQLite` + `RefreshStatsUseCase` + `ListTrendingUseCase`

</code_context>

<specifics>
## Specific Ideas

- `repost_count` est le nom yt-dlp pour les partages TikTok — ne pas renommer en `share_count` dans l'entité pour rester aligné avec le dict yt-dlp
- L'idempotence de `video_stats` est sur la clé `(video_id, captured_at)` avec timestamp à la seconde — deux probes dans la même seconde seraient dédupliquées, mais c'est un cas négligeable
- `vidscope show` doit afficher un message actionnable si aucun stat n'a été capturé (pas de crash silencieux)
- La gate Hypothesis (`test_metrics_property.py`) est non-négociable selon le ROADMAP — elle doit bloquer le merge si une propriété (monotonicity, additivity, zero-bug) échoue

</specifics>

<deferred>
## Deferred Ideas

- **Push notifications** quand vélocité dépasse un seuil — additive surface, pas M009
- **Backfill historique** depuis analytics tiers — out of scope (on n'a que nos propres observations)
- **`vidscope list --sort-by velocity`** — serait naturel mais hors périmètre M009 ; candidat M010/M011
- **`viral_coefficient`** — si la définition reste floue pendant le planning, peut être omis de S01 sans casser le reste

</deferred>

---

*Phase: M009-engagement-signals-velocity*
*Context gathered: 2026-04-18*
