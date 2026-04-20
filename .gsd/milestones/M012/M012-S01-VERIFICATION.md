---
phase: M012-S01
verified: 2026-04-20T22:15:00Z
status: passed
score: 8/8
overrides_applied: 0
---

# Phase M012/S01: Metadata coherence at ingest — Verification Report

**Phase Goal:** Tout contenu ingéré (carousel Instagram, image, reel, vidéo yt-dlp) doit produire, dès la fin de `vidscope add <url>`, deux faits observables en DB: R060 — `videos.description` contient la caption complète du post (non-tronquée), ou NULL si le post n'a pas de caption. R061 — `video_stats` contient une ligne initiale avec `like_count` et/ou `comment_count` quand la plateforme les fournit, sans exécuter `vidscope refresh-stats`.
**Verified:** 2026-04-20T22:15:00Z
**Status:** passed
**Re-verification:** Non — vérification initiale

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `IngestOutcome` a `like_count: int \| None = None` et `comment_count: int \| None = None` après `carousel_items` | VERIFIED | `pipeline.py` lignes 205-206 — deux champs présents dans l'ordre exact spécifié |
| 2 | `videos` table a une colonne `description TEXT` nullable via `_ensure_description_column` appelée depuis `init_db` — migration idempotente | VERIFIED | `schema.py` ligne 863 (définition), ligne 443 (appel init_db), smoke test DB confirme `TEXT` présent après double `init_db` |
| 3 | `VideoRepositorySQLite._video_to_row()` mappe `description`; `_row_to_video()` le relit | VERIFIED | `video_repository.py` ligne 222 (`"description": video.description`) et ligne 245 (`description=data.get("description")`) |
| 4 | `InstaLoaderDownloader.download()` peuple `description=post.caption` et `like_count=post.likes`, `comment_count=post.comments` | VERIFIED | `downloader.py` lignes 109-111 — les trois champs présents, `description` non tronquée (distinct de `title[:200]`) |
| 5 | `YtdlpDownloader._info_to_outcome()` peuple `like_count=_int_or_none(info.get('like_count'))` et `comment_count=_int_or_none(info.get('comment_count'))` | VERIFIED | `downloader.py` lignes 422-423 — exact pattern spécifié |
| 6 | `IngestStage.execute()` passe `description=outcome.description` à `Video(...)` et appelle `uow.video_stats.append(VideoStats(...))` quand `like_count` ou `comment_count` est non-None | VERIFIED | `ingest.py` ligne 183 (Video), lignes 202-209 (bloc conditionnel VideoStats avec `captured_at UTC replace(microsecond=0)`) |
| 7 | Ingestion avec caption/engagement null complète sans erreur — `description` et stats restent null gracieusement | VERIFIED | Tests `test_null_caption_gives_null_description`, `test_none_likes_gives_none_engagement`, `test_no_stats_created_when_no_engagement` — tous passent (162 tests scope OK) |
| 8 | `vidscope show <id>` affiche `description` et engagement stats depuis l'ingestion sans exécuter `vidscope refresh-stats` — pas de changements show.py nécessaires | VERIFIED | `show.py` déjà câblé sur les champs Video.description et VideoStats ; IngestStage persiste ces données → affichage immédiat post-ingest |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `src/vidscope/ports/pipeline.py` | IngestOutcome étendu avec champs engagement | VERIFIED | Lignes 205-206 : `like_count` et `comment_count` avec default `None`, après `carousel_items` |
| `src/vidscope/adapters/sqlite/schema.py` | Migration idempotente colonne description | VERIFIED | `_ensure_description_column` définie ligne 863, appelée ligne 443, colonne aussi ajoutée à la `Table` SQLAlchemy ligne 109 |
| `src/vidscope/adapters/sqlite/video_repository.py` | Round-trip description entre Video et SQLite | VERIFIED | `_video_to_row` ligne 222, `_row_to_video` ligne 245 |
| `src/vidscope/adapters/instaloader/downloader.py` | Métadonnées carousel/image/reel à l'ingest | VERIFIED | 3 champs ajoutés lignes 109-111 |
| `src/vidscope/adapters/ytdlp/downloader.py` | Extraction engagement yt-dlp | VERIFIED | 2 champs ajoutés lignes 422-423 |
| `src/vidscope/pipeline/stages/ingest.py` | Persistance description + VideoStats initial | VERIFIED | `description=outcome.description` ligne 183, bloc conditionnel VideoStats lignes 202-209 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `adapters/instaloader/downloader.py` | `ports/pipeline.py::IngestOutcome` | `description=post.caption` + `like_count=post.likes` | WIRED | Lignes 109-111 : pattern exact `description=post.caption` puis `like_count=post.likes if post.likes is not None else None`, `comment_count=post.comments if post.comments is not None else None` |
| `adapters/ytdlp/downloader.py::_info_to_outcome` | `ports/pipeline.py::IngestOutcome` | `like_count=_int_or_none(info.get("like_count"))` | WIRED | Lignes 422-423 : pattern exact spécifié |
| `pipeline/stages/ingest.py::IngestStage.execute` | `adapters/sqlite/video_repository.py` | `Video(description=outcome.description)` persisted via `uow.videos` | WIRED | Ligne 183 : `description=outcome.description` dans le constructeur Video |
| `pipeline/stages/ingest.py::IngestStage.execute` | `uow.video_stats` | `VideoStats append` conditionnel when `like_count or comment_count is not None` | WIRED | Lignes 202-209 : condition exacte `if outcome.like_count is not None or outcome.comment_count is not None:` |
| `adapters/sqlite/schema.py::init_db` | `videos.description column` | `_ensure_description_column(conn)` dans transaction init_db | WIRED | Ligne 443 : appel présent dans `with engine.begin() as conn:` bloc |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `ingest.py::Video(...)` | `description=outcome.description` | `InstaLoaderDownloader` → `post.caption` / `YtdlpDownloader` → `info.get("description")` | Oui — données réelles provenant du downloader | FLOWING |
| `ingest.py::VideoStats(...)` | `like_count=outcome.like_count`, `comment_count=outcome.comment_count` | `InstaLoaderDownloader` → `post.likes/post.comments` / `YtdlpDownloader` → `info.get("like_count")` | Oui — données réelles provenant du downloader, persistées conditionnellement | FLOWING |
| `video_repository.py::_video_to_row` | `"description": video.description` | `Video` domain entity (champ populé par IngestStage) | Oui — column TEXT nullable dans SQLAlchemy Table + ALTER TABLE migration | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Schéma DB : colonne `description TEXT` présente après double `init_db` | `uv run python -c "init_db(e); init_db(e); assert 'description' in cols..."` | `Schema OK — description: TEXT` | PASS |
| 162 tests du périmètre M012/S01 | `uv run pytest [6 fichiers] -q` | `162 passed, 2 warnings in 1.88s` | PASS |
| Non-régression suite complète tests/unit | `uv run pytest tests/unit -q` | `1658 passed, 180 warnings in 52.31s` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| R060 | M012-S01-PLAN.md | `videos.description` contient la caption complète (non-tronquée) ou NULL | SATISFIED | T01+T03+T04+T06+T11 — colonne migrée, round-trip repo, caption complète depuis instaloader, wire IngestStage, test round-trip |
| R061 | M012-S01-PLAN.md | `video_stats` contient ligne initiale `like_count`/`comment_count` sans `refresh-stats` | SATISFIED | T02+T04+T05+T06+T10 — IngestOutcome étendu, downloaders populés, IngestStage conditionnel, test E2E |

### Anti-Patterns Found

Aucun anti-pattern détecté dans les fichiers modifiés. Pas de TODO/FIXME, pas de `return null`, pas de valeurs hardcodées en placeholder, pas de handlers vides.

### Deviation Notable (documentée dans SUMMARY)

La décision de dévier du plan en ajoutant `Column("description", Text, nullable=True)` à la définition SQLAlchemy `Table` (en plus du `_ensure_description_column` ALTER TABLE) est correcte et documentée. Sans cette modification, `INSERT`/`UPDATE` via SQLAlchemy Core signalerait `Unconsumed column names: description`. Le plan disait "Ne PAS modifier la Table" mais c'était une erreur de planification corrigée à l'exécution — les tests le confirment.

### Human Verification Required

Aucun — tous les comportements critiques sont vérifiables programmatiquement et ont été vérifiés.

## Gaps Summary

Aucun gap. Les 8 must-haves sont vérifiés, les 12 commits documentés existent dans le repo git, 162 tests du périmètre passent, 1658 tests unitaires total sans régression.

---

_Verified: 2026-04-20T22:15:00Z_
_Verifier: Claude (gsd-verifier)_
