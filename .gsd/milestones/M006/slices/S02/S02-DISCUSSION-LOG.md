# Phase M006/S02: Ingest stage populates creator — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in S02-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** M006/S02 — Ingest stage populates creator before video row
**Areas discussed:** Vecteur créateur dans download(), Uploader manquant, Politique de mise à jour, Ordering transactionnel

---

## Vecteur créateur dans download()

| Option | Description | Selected |
|--------|-------------|----------|
| Enrichir IngestOutcome | Ajouter `creator_info: CreatorInfo \| None` à `IngestOutcome`. Extraction depuis l'info_dict déjà disponible — zero appel réseau supplémentaire. | ✓ |
| Réutiliser ProbeResult | Appel `probe()` puis `download()` séquentiellement — double appel réseau. | |
| Champ partagé UoW | Stocker le résultat probe() dans le contexte pipeline. Couplage fort. | |

**User's choice:** Enrichir IngestOutcome  
**Notes:** S01 a déjà étendu ProbeResult mais il serait inutilement coûteux d'appeler probe() à chaque ingest. L'info_dict yt-dlp contient déjà les champs créateur lors du download.

**Follow-up — TypedDict vs dataclass :**

| Option | Description | Selected |
|--------|-------------|----------|
| TypedDict | Léger, directement désérialisable depuis info_dict, idiomatique pour données de transport. | ✓ |
| Dataclass frozen | Mieux typé et immuable, mais asymétrique avec les autres types de transport. | |

---

## Uploader manquant

| Option | Description | Selected |
|--------|-------------|----------|
| Ingest réussit, creator_id=NULL | Vidéo sauvegardée avec creator_id=NULL + WARNING loggé. Compatible avec les compilations. | ✓ |
| Erreur typée, ingest échoue | Lance MissingUploaderError. Bloque des cas légitimes. | |

**User's choice:** Ingest réussit, creator_id=NULL  
**Notes:** Le cas uploader absent est légitime (compilations, playlists mixtes). Bloquer l'ingest serait contre-productif.

---

## Politique de mise à jour

| Option | Description | Selected |
|--------|-------------|----------|
| Upsert complet | Met à jour handle, display_name, follower_count, avatar_url, last_seen_at à chaque re-ingest. Données fraîches. ON CONFLICT DO UPDATE est no-op si identique. | ✓ |
| Upsert partiel | Met à jour seulement last_seen_at. follower_count reste dépassé. | |
| Insert-only | Ignore si ligne existe. Métadonnées jamais mises à jour. | |

**User's choice:** Upsert complet  
**Notes:** `created_at` et `first_seen_at` ne sont pas écrasés (préservés de la première insertion — pattern S01).

---

## Ordering transactionnel

| Option | Description | Selected |
|--------|-------------|----------|
| Même UoW | Upsert créateur + upsert vidéo dans la même transaction. Rollback atomique si vidéo échoue. Déjà supporté par l'UoW S01. | ✓ |
| Deux transactions | Créateur commit séparé, vidéo commit séparé. Peut laisser des lignes créateurs sans vidéos. | |

**User's choice:** Même UoW  
**Notes:** Le runner passe déjà un UoW ouvert à `execute(ctx, uow)` — S02 utilise simplement `uow.creators` sur la connexion partagée existante.

---

## Claude's Discretion

- Nom et position de `CreatorInfo` TypedDict dans `ports/pipeline.py`
- Mapping `handle` / `display_name` → même champ `uploader` de yt-dlp
- Helper interne `_extract_creator_info(info_dict)` dans `YtdlpDownloader`
- Test double `FakeDownloader` pour les tests d'IngestStage

## Deferred Ideas

- Refresh périodique des métadonnées créateur sans re-download → M009
- Déduplication cross-plateforme → hors M006
- Exception typée pour uploader manquant → rejeté (cas légitimes existent)
