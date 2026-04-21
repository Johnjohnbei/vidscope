---
phase: M012
plan: S03
status: complete
requirements: [R064, R065]
completed: 2026-04-21
---

# M012/S03 — MCP output enrichi : SUMMARY

## Ce qui a été construit

Câblage dans `server.py` pour exposer trois nouvelles données dans `vidscope_get_video` :

1. **R064 — `description`** (D-05) : ajouté dans `_video_to_dict()`, ce qui l'expose automatiquement dans `vidscope_list_videos` également.
2. **R064 — `latest_engagement`** (D-01) : dict `{view_count, like_count, comment_count, repost_count, save_count, captured_at}` ou `null` si aucune `VideoStats` n'existe pour la vidéo.
3. **R065 — `ocr_preview` + `ocr_full_tool`** (D-03/D-04/D-06) : présents uniquement pour les carousels (`content_shape == "carousel"`), absents (pas null) pour reels/vidéos. `ocr_preview` = 5 premiers `FrameText` triés `(frame_id ASC, id ASC)` concaténés avec `\n`. `ocr_full_tool = "vidscope_get_frame_texts"`.

## Fichiers modifiés

- `src/vidscope/mcp/server.py` — `_video_to_dict` + `vidscope_get_video`
- `tests/unit/mcp/test_server.py` — `TestVidscopeGetVideoR064` (6 tests) + `TestVidscopeGetVideoR065` (4 tests) + 3 helpers de seeding

## Décisions de design

- **D-05** : `description` dans `_video_to_dict()` expose le champ dans tous les outils MCP utilisant ce helper, sans duplication.
- **D-01** : `latest_engagement` null vs dict — structure JSON propre, l'agent sait immédiatement si des stats existent.
- **D-03** : `ocr_preview`/`ocr_full_tool` absents (pas null) pour non-carousels — évite le bruit dans le contexte agent.
- **D-06** : tri `(frame_id, id or 0)` pour ordre déterministe même si `id` est null.

## Résultats de tests

- `pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR064` : **6/6 PASSED**
- `pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR065` : **4/4 PASSED**
- `pytest tests/unit -q` : **1683 passed, 0 failed** (baseline 1673 + 10 nouveaux)

## Dépendances confirmées

- **M012/S01** (R060/R061) : `Video.description` existe dans la DB — câblage direct vers `video.description` fonctionne.
- **M012/S02** (R062/R063) : `ShowVideoResult.frame_texts` et `ShowVideoResult.latest_stats` déjà fetchés par `ShowVideoUseCase.execute` — aucune modification du use case nécessaire.

## Surprises

Aucune. Le plan était précis et toutes les interfaces documentées correspondaient au code existant.

## key-files

### created
- tests/unit/mcp/test_server.py::TestVidscopeGetVideoR064 (nouveau bloc de tests)
- tests/unit/mcp/test_server.py::TestVidscopeGetVideoR065 (nouveau bloc de tests)

### modified
- src/vidscope/mcp/server.py::_video_to_dict (+1 ligne : description)
- src/vidscope/mcp/server.py::vidscope_get_video (+30 lignes : latest_engagement + ocr_preview/ocr_full_tool)
- tests/unit/mcp/test_server.py (+225 lignes : imports, helpers, 10 tests)
