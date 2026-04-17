---
plan_id: S02-P02
status: completed
completed_at: 2026-04-17
---

# S02-P02 Summary — _extract_creator_info dans YtdlpDownloader

## Ce qui a été livré

**Fichiers modifiés :**
- `src/vidscope/adapters/ytdlp/downloader.py` — `_extract_creator_info` helper + `_info_to_outcome` étendu avec `creator_info=`
- `tests/unit/adapters/ytdlp/test_downloader.py` — 9 nouveaux tests `TestCreatorInfoExtraction`

## Localisation de _extract_creator_info

Inséré juste avant `_extract_uploader_thumbnail` (~ligne 598). Réutilise :
- `_str_or_none` — platform_user_id, handle, display_name, profile_url
- `_int_or_none` — follower_count
- `_extract_uploader_thumbnail` — avatar_url
- `_extract_uploader_verified` — is_verified

## Les 9 tests couvrent

1. Happy path complet (tous les champs)
2. D-02 uploader_id absent → None
3. D-02 uploader_id vide → None
4. Minimal (seul uploader_id, reste None)
5. Fallback channel_id quand uploader_id absent
6. Avatar liste de dicts yt-dlp
7. follower_count non-int → None
8. Fallback channel_followers
9. Régression : TestHappyPath existant reste vert

## Self-Check: PASSED

- 52 tests downloader verts (9 nouveaux + 43 existants)
- mypy vert, ruff vert
- 9 contrats import-linter verts

## Handoff

**P03** : `IngestOutcome.creator_info` est maintenant populé par le downloader — `IngestStage` peut le consommer.
