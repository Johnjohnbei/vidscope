---
plan_id: S02-P03
status: completed
completed_at: 2026-04-17
---

# S02-P03 Summary — Câblage IngestStage + harness verify

## Ce qui a été livré

**Fichiers modifiés :**
- `src/vidscope/pipeline/stages/ingest.py` — creator upsert (étape 5) avant video upsert (étape 6) + helper `_creator_from_info`
- `src/vidscope/ports/unit_of_work.py` — `creators: CreatorRepository` ajouté au Protocol `UnitOfWork`
- `tests/unit/pipeline/stages/test_ingest.py` — `TestCreatorWiring` (7 tests) + helpers

**Fichiers créés :**
- `scripts/verify-m006-s02.sh` — harness complet 10 steps

## Shape finale de execute()

1. detect_platform
2. download → outcome
3. platform sanity check
4. media store
5. **[NOUVEAU]** `uow.creators.upsert(_creator_from_info(outcome.creator_info, platform))` si creator_info présent, sinon WARNING log (D-02)
6. `uow.videos.upsert_by_platform_id(video, creator=creator)` — D-03 write-through
7. mutate ctx

## Les 7 tests TestCreatorWiring

| Test | Décision couverte |
|------|-------------------|
| D-01 happy path | creator upsert + video.creator_id + author write-through |
| D-02 None path | ingest OK, creator_id=NULL, WARNING log avec URL |
| D-03 refresh | re-ingest même uploader_id → 1 seule ligne, follower_count mis à jour |
| D-04 rollback | échec video → rollback creator (zéro orphelin) |
| Deux vidéos même créateur | 1 creator row, 2 videos, même FK |
| Régression _youtube_outcome_factory | D-02 path, tests existants inchangés |
| _creator_from_info pur | mapping TypedDict → Creator, sans I/O |

## Self-Check: PASSED

- 698 tests verts (suite complète)
- mypy strict vert (85 fichiers)
- 9 contrats import-linter verts (`pipeline-has-no-adapters` vérifié)
- ruff vert
- `bash scripts/verify-m006-s02.sh --skip-full-suite` exit 0 (10/10 steps)

## Handoff pour M006/S03

La table `creators` est maintenant peuplée à chaque `vidscope add <url>` (quand yt-dlp expose `uploader_id`). `videos.creator_id` FK et `videos.author` cache D-03 sont écrits atomiquement. S03 peut lire `videos.creator_id` → `creators` pour les CLI `creator show/list/videos` et le MCP tool `vidscope_get_creator`.

## Coverage matrix S02

| Décision | P01 | P02 | P03 |
|----------|-----|-----|-----|
| D-01 : CreatorInfo contract | ✓ | ✓ | ✓ |
| D-02 : None path (ingest réussit) | ✓ (rétrocompat) | ✓ | ✓ |
| D-03 : full upsert idempotent | — | — | ✓ |
| D-04 : transaction atomique | — | — | ✓ |
