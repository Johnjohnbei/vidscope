# Phase M012/S03: MCP output enrichi — Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Enrichir `vidscope_get_video` pour qu'un agent obtienne un portrait complet d'un contenu
(description, engagement complet, aperçu OCR pour carousels) en un seul appel MCP.

Le travail est principalement du câblage : les données existent déjà dans `ShowVideoResult`
— `video.description`, `latest_stats`, et `frame_texts` sont déjà récupérés par
`ShowVideoUseCase`. Il s'agit de les exposer dans la réponse MCP.

Cette phase ne touche pas le pipeline, les entités, ni les repositories.

</domain>

<decisions>
## Implementation Decisions

### D-01 : Périmètre de `latest_engagement`
Inclure tous les champs de `VideoStats` + `captured_at` :
- `view_count: int | None`
- `like_count: int | None`
- `comment_count: int | None`
- `repost_count: int | None`
- `save_count: int | None`
- `captured_at: str` (ISO-8601, UTC)

La valeur entière de `latest_engagement` est `null` si aucune stats n'existe pour la vidéo.

### D-02 : Signalement de `vidscope_get_frame_texts`
Champ séparé `ocr_full_tool` à côté de `ocr_preview` :
```json
{
  "ocr_preview": "Build in public. 5 tips...\nSlide 2: ...",
  "ocr_full_tool": "vidscope_get_frame_texts"
}
```
Machine-readable, l'agent peut l'utiliser directement sans parser du texte.

### D-03 : `ocr_preview` pour non-carousels
Absent du dict (champ omis, pas `null`). Pas de bruit dans la réponse pour les reels/vidéos.
L'agent utilise `.get("ocr_preview")` pour vérifier. `ocr_full_tool` est également absent.

### D-04 : Détection carousel
Utiliser `video.content_shape == "carousel"` (champ déjà présent dans `Video` et dans
`_video_to_dict`). Si `content_shape` est null ou autre valeur, pas d'`ocr_preview`.

### D-05 : `description` dans la réponse
Ajouter `description` directement dans `_video_to_dict()` (avec les autres métadonnées
de base). Cela l'expose également dans `vidscope_list_videos` — c'est acceptable car
`description` est une métadonnée fondamentale d'une vidéo.

### D-06 : Nombre de blocs OCR pour `ocr_preview`
Les 5 premiers `FrameText` triés par `frame_id` ASC, concaténés avec `\n`. Si moins de 5
blocs existent, tous sont inclus.

### Claude's Discretion
- Séparateur entre les blocs OCR dans `ocr_preview` (suggestion : `\n`)
- Ordre exact des champs dans le dict de retour
- Stratégie de tri des `frame_texts` si `frame_id` est null

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MCP Server
- `src/vidscope/mcp/server.py` — Fichier principal à modifier (tool `vidscope_get_video`, helper `_video_to_dict`)

### Use Case & Domain
- `src/vidscope/application/show_video.py` — `ShowVideoResult` contient déjà toutes les données nécessaires (`latest_stats`, `frame_texts`, `video.description`)
- `src/vidscope/domain/entities.py` — `Video.description`, `VideoStats` (tous les champs), `FrameText`

### Requirements
- `.gsd/REQUIREMENTS.md` §R064 — `description` + `latest_engagement` dans `vidscope_get_video`
- `.gsd/REQUIREMENTS.md` §R065 — `ocr_preview` + `ocr_full_tool` pour carousels
- `.gsd/milestones/M012/M012-ROADMAP.md` §M012/S03 — Success criteria complets

### Tests existants
- `tests/unit/mcp/test_server.py` (ou équivalent) — À étendre pour les nouveaux champs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_video_to_dict(video: Video)` — Helper existant ligne 66 de `server.py`. Ajouter `description` ici.
- `ShowVideoResult.latest_stats: VideoStats | None` — Données engagement déjà fetchées
- `ShowVideoResult.frame_texts: tuple[FrameText, ...]` — Blocs OCR déjà fetchés
- `vidscope_get_frame_texts` — Tool MCP existant, c'est lui que `ocr_full_tool` référence

### Established Patterns
- Pattern de retour `vidscope_get_video` : dict racine avec `found`, `video`, `transcript`, `frame_count`, `analysis`
- Tous les nouveaux champs (`latest_engagement`, `ocr_preview`, `ocr_full_tool`) vont dans le dict racine au même niveau
- `None` mappé à `null` JSON automatiquement par FastMCP

### Integration Points
- `vidscope_get_video` (ligne 208) — Seul point à modifier dans `server.py`
- `_video_to_dict` (ligne 66) — Ajouter `description` ici pour cohérence avec `list_videos`

</code_context>

<specifics>
## Specific Ideas

- L'utilisateur veut `captured_at` dans `latest_engagement` pour que l'agent sache à quelle
  date les stats ont été capturées — pas seulement les compteurs.
- `ocr_full_tool: "vidscope_get_frame_texts"` est machine-readable intentionnellement :
  un agent peut lire ce champ et appeler directement le tool nommé sans parser un message humain.

</specifics>

<deferred>
## Deferred Ideas

Aucune idée hors-scope n'a été soulevée — la discussion est restée dans le périmètre de la phase.

</deferred>

---

*Phase: M012-S03-mcp-output-enrichi*
*Context gathered: 2026-04-21*
