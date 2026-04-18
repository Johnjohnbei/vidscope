# Phase M007: Rich content metadata — Discussion Log

> **Audit trail uniquement.** Ne pas utiliser comme input pour le planning, la recherche, ou l'exécution.
> Les décisions sont capturées dans CONTEXT.md — ce log préserve les alternatives considérées.

**Date:** 2026-04-17
**Phase:** M007 — Rich content metadata
**Zones discutées:** Placement de description, Short-URL resolver, Mention→Creator linkage, Logique des facettes de recherche

---

## Placement de description

| Option | Description | Sélectionné |
|--------|-------------|-------------|
| Colonne sur Video | description: str \| None ajouté à Video entity + table videos. Zéro JOIN, cohérent avec title/author/view_count. | ✓ |
| Entité VideoMetadata séparée | VideoMetadata dataclass + table video_metadata (1-to-1). Plus propre architecturalement mais ajoute JOIN. | |
| Description sur Video + autres champs à plat | description, music_track, music_artist directement sur Video (pas de VideoMetadata). | |

**Choix de l'utilisateur :** Colonne sur Video
**Notes :** Suite logique — music_track et music_artist également ajoutés comme colonnes sur Video (même raisonnement : cohérence avec champs scalaires existants, zéro JOIN).

---

## Short-URL resolver

| Option | Description | Sélectionné |
|--------|-------------|-------------|
| Déférer à M008/M011 | Stocker URL brute + normalized_url. Pas de réseau suppl. | ✓ |
| Flag optionnel en S02 | resolve_short_urls: bool = False. HEAD request pour suivre redirections. Latence + dépendance réseau. | |

**Choix de l'utilisateur :** Déférer à M008/M011
**Notes :** Le roadmap marquait déjà "(optional flag)" — la décision confirme que M007 reste zero-network à l'ingest.

---

## Mention → Creator linkage

| Option | Description | Sélectionné |
|--------|-------------|-------------|
| String brut uniquement | handle: str + platform: Platform \| None. Pas de FK. Join dérivable en M011. | ✓ |
| FK creator_id optionnelle | Lookup CreatorRepository.find_by_handle après extraction. N DB lookups par ingest. | |

**Choix de l'utilisateur :** String brut uniquement
**Notes :** Évite la complexité O(n) à l'ingest. Le lien Mention↔Creator sera dérivé en M011 via JOIN quand il y a un vrai usage.

---

## Logique des facettes de recherche

| Option | Description | Sélectionné |
|--------|-------------|-------------|
| AND implicite | Chaque facette affine le résultat. --hashtag coding --mention @alice = les deux requis. | ✓ |
| OR implicite | L'un ou l'autre suffit. Moins utile pour filtrer précisément. | |

**Choix hashtag match :**

| Option | Description | Sélectionné |
|--------|-------------|-------------|
| Exact match | --hashtag coding = uniquement #coding après canonicalisation lowercase. | ✓ |
| Préfixe LIKE | --hashtag cod = #coding, #codingchallenge... Ambigu, bruyant. | |

**Choix de l'utilisateur :** AND implicite + exact match
**Notes :** L'utilisateur peut cumuler plusieurs --hashtag si besoin d'union.

---

## Claude's Discretion

- Placement de la migration (monolithique ou scindée)
- Implémentation interne de `normalized_url`
- `--music-track` : exact vs LIKE
- Nombre de tests par entité
- Indexation de `description` dans FTS5

## Deferred Ideas

- HEAD-resolver URLs courtes → M008/M011
- Mention→Creator linkage → M011
- VideoMetadata entity → abandonné
- URL deduplication cross-videos → out of scope
- Link-preview / OpenGraph → out of scope
