# Phase M009: Engagement signals + velocity time-series — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-18
**Phase:** M009 — Engagement signals + velocity time-series
**Areas discussed:** Granularité bucket, VideoStats champs plateforme, Métriques manquantes, vidscope trending output, vidscope show stats

---

## A — Granularité du bucket d'idempotence

| Option | Description | Selected |
|--------|-------------|----------|
| Timestamp exact | Toujours insérer, 2 rows si run deux fois en 1h | ✓ |
| Bucket horaire | Max 1 row par heure par vidéo | |
| Bucket journalier | Max 1 row par jour par vidéo | |

**User's choice:** Timestamp exact — 2 lignes si lancé deux fois
**Notes:** Meilleure résolution time-series. L'idempotence reste sur la clé `(video_id, captured_at)` à la seconde pour éviter les doublons stricts.

---

## B — `vidscope trending` : output et seuils

| Option | Description | Selected |
|--------|-------------|----------|
| Recommandation agent | Top 20 / rich Table / --since obligatoire / --limit N / --min-velocity 0 | ✓ |

**User's choice:** Accepté — "ok alors pour B"
**Notes:** `--since` obligatoire sans défaut silencieux. Colonnes : rang, titre (40c), plateforme, velocity_24h, engagement_rate, dernière capture. Scalable via LIMIT SQL côté base.

---

## C — `vidscope show` : intégration des stats

| Option | Description | Selected |
|--------|-------------|----------|
| Oui, section stats dans M009 | Afficher dernière snapshot + vélocité | ✓ |
| Différer | Laisser pour M010/M011 | |

**User's choice:** Oui
**Notes:** Message actionnable si zéro rows dans `video_stats` : "Aucune stat — lancez `vidscope refresh-stats <id>`"

---

## D — Métriques manquantes / champs disponibles par plateforme

| Option | Description | Selected |
|--------|-------------|----------|
| `None` pour non disponible | Sémantique "non mesuré" — ne fausse pas l'engagement_rate | ✓ |
| `0` pour non disponible | Sémantique ambiguë — zéro engagement vs non mesuré | |

**User's choice:** `None` — et vérifier exactement quels champs TikTok et Instagram chargent
**Notes:** Vérification effectuée dans les extractors yt-dlp. TikTok garantit 5 champs (`view_count`, `like_count`, `repost_count`, `comment_count`, `save_count`). Instagram garantit 3 (`view_count`, `like_count`, `comment_count`). Le champ s'appelle `repost_count` (pas `share_count`) dans yt-dlp pour les partages TikTok.

---

## Claude's Discretion

- Formule exacte de `views_velocity_24h`, `engagement_rate`, `viral_coefficient`
- Placement migration 008
- Seuil de tests Hypothesis (nombre de propriétés)

## Deferred Ideas

- `vidscope list --sort-by velocity` — candidat M010/M011
- Push notifications sur seuil de vélocité — additive surface future
- `viral_coefficient` — peut être omis si définition reste floue
