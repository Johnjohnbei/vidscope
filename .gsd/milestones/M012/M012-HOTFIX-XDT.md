---
type: hotfix
milestone: M012
applied: 2026-04-22
status: complete
requirements: [R062]
---

# M012 HOTFIX — XDTGraphSidecar : carousels Instagram mal détectés

## Symptôme observé

Sur les carousels Instagram récents, le pipeline produisait :
- `media_type: VIDEO` (au lieu de `carousel`)
- `carousel_items: ()` — aucun slide
- `analysis: null` — OCR ne trouvait rien

Test réel : `DXbelfmFXxY` (carousel 9 slides) → 0 images, 0 blocs OCR, analyse nulle.

## Root cause

Instagram a commencé à retourner `"XDTGraphSidecar"` dans le champ `__typename` des réponses API
au lieu de l'ancien `"GraphSidecar"`. instaloader 4.15.1 normalise ce préfixe uniquement dans
`_obtain_metadata()`, qui n'est jamais appelé quand `_node` contient déjà `__typename`.

Deux comparaisons échouaient silencieusement :
1. `post.typename == "GraphSidecar"` dans notre `_download_images()` → branche carousel non empruntée
2. `get_sidecar_nodes()` interne à instaloader → même condition, 0 nœuds retournés

Chemin de dégradation :
```
InstaLoaderDownloader → 0 images → IngestError("no downloadable images found")
→ PlatformRoutingDownloader fallback yt-dlp
→ yt-dlp télécharge une vidéo → media_type=VIDEO, carousel_items=()
→ FramesStage extrait des frames vidéo (pas des slides)
→ OCR tourne sur frames vidéo → 0 blocs texte
→ analysis: null
```

Les tests existants ne couvraient pas ce cas car ils mockaient `post.typename = "GraphSidecar"`
directement — sans toucher à `_node`.

## Fix

**Fichier :** `src/vidscope/adapters/instaloader/downloader.py`

```python
_XDT_TYPENAME_MAP: dict[str, str] = {
    "XDTGraphSidecar": "GraphSidecar",
    "XDTGraphImage":   "GraphImage",
    "XDTGraphVideo":   "GraphVideo",
}

def _normalize_post_typename(post: Any) -> None:
    """Normalise les typenames XDT dans _node avant toute vérification."""
    try:
        raw = post._node.get("__typename", "")
        if raw in _XDT_TYPENAME_MAP:
            post._node["__typename"] = _XDT_TYPENAME_MAP[raw]
    except (AttributeError, TypeError):
        pass
```

Appelé au début de `_download_images()` — avant le `post.typename == "GraphSidecar"` check.
Le patch in-place sur `_node` répare à la fois notre vérification ET `get_sidecar_nodes()`.

## Tests ajoutés

**Fichier :** `tests/unit/adapters/instaloader/test_downloader.py`

| Classe | Test | Ce qu'il vérifie |
|--------|------|-----------------|
| `TestDownloadImages` | `test_xdt_carousel_downloads_all_images` | `XDTGraphSidecar` → 2 slides téléchargés, `_node` patché |
| `TestDownloadImages` | `test_xdt_image_normalised` | `XDTGraphImage` → image unique téléchargée |
| `TestNormalizePostTypename` | `test_xdt_sidecar_normalized` | XDTGraphSidecar → GraphSidecar |
| `TestNormalizePostTypename` | `test_xdt_image_normalized` | XDTGraphImage → GraphImage |
| `TestNormalizePostTypename` | `test_xdt_video_normalized` | XDTGraphVideo → GraphVideo |
| `TestNormalizePostTypename` | `test_already_canonical_unchanged` | GraphSidecar reste GraphSidecar |
| `TestNormalizePostTypename` | `test_missing_node_attr_does_not_raise` | post sans `_node` ne lève pas d'exception |
| `TestNormalizePostTypename` | `test_node_without_typename_unchanged` | `_node` sans `__typename` → dict inchangé |

Total suite : **1700 passed, 0 failed** (baseline 1692 + 8 nouveaux).

## Validation réelle

URL testée : `https://www.instagram.com/p/DXbelfmFXxY/`

| Avant fix | Après fix |
|-----------|-----------|
| `media_type: VIDEO` | `media_type: carousel` ✅ |
| `carousel_items: 0` | `9 slides téléchargés` ✅ |
| `on-screen text: 0 blocks` | `138 blocks` ✅ |
| `analysis: null` | `score=59.1, 8 keywords, 3 topics` ✅ |

## Bug connu post-fix (hors scope)

`UnicodeEncodeError: 'charmap' codec can't encode character '米'` dans `show.py` quand le texte
OCR contient des caractères non-cp1252 (caractères CJK, etc.). Le pipeline s'exécute entièrement —
c'est un crash d'affichage en fin de commande sur la console Windows. Fix : forcer
`PYTHONIOENCODING=utf-8` ou filtrer en `errors='replace'` dans l'output rich. À adresser en M012/S04
ou en hotfix séparé.
