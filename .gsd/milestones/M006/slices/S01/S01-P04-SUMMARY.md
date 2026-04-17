---
plan_id: S01-P04
phase: M006/S01
subsystem: ytdlp-adapter + backfill-script
tags: [ytdlp, probe, creator, backfill, dry-run, argparse, verify]
requirements: [R040, R042]

dependency_graph:
  requires:
    - S01-P01 (ProbeResult étendu avec 6 champs creator)
    - S01-P02 (schema creators + videos.creator_id)
    - S01-P03 (CreatorRepositorySQLite + uow.creators + write-through D-03)
  provides:
    - YtdlpDownloader.probe popule uploader/uploader_id/uploader_url/channel_follower_count/uploader_thumbnail/uploader_verified
    - scripts/backfill_creators.py (argparse, --dry-run par défaut, --apply pour muter)
    - tests/unit/scripts/test_backfill_creators.py (6 tests R042)
    - scripts/verify-s01.sh (harness 10 steps, --skip-backfill-smoke)
  affects:
    - S02 (IngestStage.execute devra upserter creator avant video et passer creator= à VideoRepository.upsert_by_platform_id)

tech_stack:
  added: []
  patterns:
    - _extract_uploader_thumbnail: résolution avatar URL string + list-of-dicts
    - _extract_uploader_verified: bool | None via channel_verified / uploader_verified
    - argparse + --dry-run par défaut + --apply explicit (D-02)
    - Per-video UoW (Ctrl-C safe, idempotent)
    - importlib.util.spec_from_file_location pour tester un script hors package
    - Fusion except (DownloadError, ExtractorError) pour respecter PLR0911

key_files:
  created:
    - scripts/backfill_creators.py
    - scripts/verify-s01.sh
    - tests/unit/scripts/__init__.py
    - tests/unit/scripts/test_backfill_creators.py
  modified:
    - src/vidscope/adapters/ytdlp/downloader.py
    - tests/unit/adapters/ytdlp/test_downloader.py

decisions:
  - "Fusion except (DownloadError, ExtractorError) pour passer PLR0911 — sémantique identique, moins de return statements"
  - "info is None et not isinstance fusionnés en une branche NOT_FOUND — plus simple, même résultat observable"
  - "noqa: BLE001 retirés — ruff du projet n'active pas BLE001, directives ignorées = RUF100"
  - "from sqlalchemy import update déplacé en top-level dans backfill_creators.py — PLC0415"
  - "verify-s01.sh remplace l'ancienne version M001/S01 — même nom, contenu entièrement remplacé pour M006/S01"
  - "Carry-over S02: IngestStage.execute doit upserter creator avant video et passer creator= à upsert_by_platform_id"

metrics:
  duration_seconds: 620
  completed_at: "2026-04-17T14:11:19Z"
  tasks_completed: 4
  tasks_total: 4
  files_modified: 6
---

# Phase M006 Plan S01-P04: YtdlpDownloader.probe creator fields + backfill script + verify harness — Summary

**One-liner:** `YtdlpDownloader.probe` expose les 6 champs creator depuis l'`info_dict` yt-dlp ; `scripts/backfill_creators.py` (argparse, `--dry-run` défaut, per-video UoW, orphan sur 404) migre les rows M001–M005 ; `scripts/verify-s01.sh` atteste S01 shippable en 10 steps.

## Tasks Completed

| # | Tâche | Commit | Fichiers clés |
|---|-------|--------|---------------|
| T12 | YtdlpDownloader.probe : 6 champs creator + helpers + tests | `7f09c66` | `downloader.py`, `test_downloader.py` |
| T13 | scripts/backfill_creators.py (argparse, dry-run, orphan) | `e855580` | `scripts/backfill_creators.py` |
| T14 | Tests backfill : dry-run, apply, orphan, idempotence, N=0 | `6535cf8` | `tests/unit/scripts/` |
| T15 | scripts/verify-s01.sh + corrections ruff PLR0911/F401 | `1c6f810` | `scripts/verify-s01.sh`, `downloader.py`, `test_downloader.py` |

## Verification Results

```
pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q          → 43 passed
pytest tests/unit/scripts/test_backfill_creators.py -x -q          → 6 passed
pytest -q (suite complète)                                          → 667 passed, 5 deselected
ruff check src tests scripts                                        → All checks passed!
mypy src                                                            → Success: no issues found in 85 source files
lint-imports                                                        → Contracts: 9 kept, 0 broken
bash scripts/verify-s01.sh --skip-backfill-smoke                   → ✓ S01 verification PASSED (10/10 steps)
python scripts/backfill_creators.py --help                         → exit 0, --apply + --limit affichés
python scripts/backfill_creators.py (dry-run sandbox vide)         → exit 0, zero writes
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] fixture seeded_engine manquait `created_at` dans l'INSERT raw**
- **Found during:** T14 — première exécution des tests backfill
- **Issue:** `videos.created_at NOT NULL` — l'INSERT sans cette colonne levait une `IntegrityError`
- **Fix:** Ajout de `created_at = CURRENT_TIMESTAMP` dans les 3 VALUES de la fixture
- **Files modified:** `tests/unit/scripts/test_backfill_creators.py`
- **Commit:** `6535cf8`

**2. [Rule 1 - Bug] ruff PLR0911 : trop de `return` dans `probe()` (7 > 6)**
- **Found during:** T15 — `bash scripts/verify-s01.sh --skip-backfill-smoke`
- **Issue:** Le plan demandait d'ajouter un return supplémentaire (`not isinstance` safety), portant le total à 7
- **Fix:** Fusion des deux `except DownloadError` / `except ExtractorError` en `except (DownloadError, ExtractorError)` + fusion des branches `info is None` / `not isinstance` en une seule branche `NOT_FOUND`
- **Files modified:** `src/vidscope/adapters/ytdlp/downloader.py`
- **Commit:** `1c6f810`

**3. [Rule 1 - Bug] ruff F401 : `ProbeResult` importé mais non utilisé dans le test**
- **Found during:** T15 — même run ruff
- **Issue:** `from vidscope.ports import ProbeResult, ProbeStatus` — `ProbeResult` n'était pas référencé dans `test_uploader_fields_populated_from_info_dict`
- **Fix:** Retiré `ProbeResult` de l'import local
- **Files modified:** `tests/unit/adapters/ytdlp/test_downloader.py`
- **Commit:** `1c6f810`

**4. [Rule 1 - Bug] ruff RUF100 + PLC0415 dans backfill_creators.py**
- **Found during:** T13 — `ruff check scripts/backfill_creators.py`
- **Issue:** 3 `# noqa: BLE001` non actifs (BLE001 n'est pas activé) + `from sqlalchemy import update` en corps de fonction (PLC0415)
- **Fix:** Retiré les `noqa` + déplacé l'import en top-level dans le même `from sqlalchemy import select, update`
- **Files modified:** `scripts/backfill_creators.py`
- **Commit:** `e855580`

**5. [Déviation de contenu] verify-s01.sh remplace le fichier existant M001/S01**
- **Context:** `scripts/verify-s01.sh` existait déjà avec le contenu du harness M001/S01
- **Decision:** Remplacement complet — le nom `verify-s01.sh` est canoniquement assigné à M006/S01 par le plan ; l'ancien contenu (socle M001) est couvert par `verify-m001.sh`
- **Impact:** Aucun — les assertions du harness M001/S01 sont redondantes avec `verify-m001.sh`

## Known Stubs

None. Toutes les méthodes sont implémentées avec du vrai code. Le script backfill appelle `container.downloader.probe()` et `uow.creators.upsert()` — aucune valeur hardcodée.

## Carry-over S02 (documenté)

`IngestStage.execute` devra à terme :
1. Appeler `container.downloader.probe(url)` pour obtenir les champs creator depuis l'`info_dict`
2. Construire un `Creator` depuis le `ProbeResult`
3. Upserter le creator via `uow.creators.upsert(creator)`
4. Passer `creator=stored_creator` à `uow.videos.upsert_by_platform_id(video, creator=stored_creator)`

Le seam est en place depuis P03 (kwarg `creator=None` sur `upsert_by_platform_id`). S02 n'a qu'à brancher le producteur.

## Threat Flags

None. Les menaces T-P04-01 à T-P04-06 du plan sont toutes mitigées ou acceptées :
- Injection SQL : toutes les writes passent par SQLAlchemy bind parameters
- `--apply` accidentel : `--dry-run` est le défaut absolu, verrouillé par `test_dry_run_writes_nothing`
- Accès à `uow._connection` : acceptable pour un script one-shot hors du package `vidscope`

## Self-Check: PASSED

| Vérification | Résultat |
|---|---|
| `scripts/backfill_creators.py` présent | FOUND |
| `scripts/verify-s01.sh` présent | FOUND |
| `tests/unit/scripts/__init__.py` présent | FOUND |
| `tests/unit/scripts/test_backfill_creators.py` présent | FOUND |
| `grep -q "uploader=uploader" src/vidscope/adapters/ytdlp/downloader.py` | FOUND |
| `grep -q "def _extract_uploader_thumbnail" downloader.py` | FOUND |
| `grep -q "def _extract_uploader_verified" downloader.py` | FOUND |
| `grep -q "dry_run = not args.apply" backfill_creators.py` | FOUND |
| `grep -q 'f"orphan:{author}"' backfill_creators.py` | FOUND |
| `grep -q "set -euo pipefail" verify-s01.sh` | FOUND |
| `grep -q "TestCreatorsSchema" verify-s01.sh` | FOUND |
| `grep -q "TestWriteThroughAuthor" verify-s01.sh` | FOUND |
| Commits T12..T15 présents | FOUND (`7f09c66`, `e855580`, `6535cf8`, `1c6f810`) |
| `pytest -q` 667 passed | PASSED |
| `ruff check src tests scripts` | PASSED |
| `mypy src` 85 fichiers | PASSED |
| `lint-imports` 9 contrats | PASSED (9 kept, 0 broken) |
| `bash verify-s01.sh --skip-backfill-smoke` | PASSED (10/10 steps) |
