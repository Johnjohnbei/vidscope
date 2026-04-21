# Phase M012/S03: MCP output enrichi — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** M012-S03 — MCP output enrichi
**Areas discussed:** Périmètre engagement, Hint vidscope_get_frame_texts, ocr_preview absent vs null

---

## Périmètre engagement

| Option | Description | Selected |
|--------|-------------|----------|
| like + comment only | Exactement ce que le SC spécifie : {like_count, comment_count}. Null si pas de stats. | |
| like + comment + view_count | Ajouter view_count très utile pour évaluer la viabilité d'un contenu. | |
| Tout VideoStats + captured_at | Inclure view_count, like_count, comment_count, repost_count, save_count et la date de capture. | ✓ |

**User's choice:** Tout VideoStats + captured_at
**Notes:** Maximiser l'information disponible pour l'agent. `captured_at` permet de savoir à quelle date les stats ont été enregistrées.

---

## Hint vidscope_get_frame_texts

| Option | Description | Selected |
|--------|-------------|----------|
| Champ séparé ocr_full_tool | Champ machine-readable séparé, l'agent peut l'utiliser directement. | ✓ |
| Hint embedé dans ocr_preview | Le hint est concaténé à la fin du texte preview. Mixe texte et métadonnée. | |
| Docstring seulement | Rien dans la réponse, documenté seulement dans la docstring. Moins découvrable. | |

**User's choice:** Champ séparé `ocr_full_tool`
**Notes:** Machine-readable intentionnellement — un agent peut lire ce champ et appeler directement le tool nommé sans parser un message humain.

---

## ocr_preview absent vs null

| Option | Description | Selected |
|--------|-------------|----------|
| Absent (champ omis) | Le champ est omis du dict pour non-carousels. Correspond à l'intent du SC. | ✓ |
| Null (champ présent) | Le champ est toujours présent avec valeur null. Structure uniforme. | |

**User's choice:** Absent
**Notes:** Pas de bruit dans la réponse pour les reels/vidéos. L'agent utilise `.get("ocr_preview")`.

---

## Claude's Discretion

- Séparateur entre blocs OCR dans `ocr_preview`
- Ordre des champs dans le dict de retour
- Stratégie de tri des `frame_texts` si `frame_id` est null

## Deferred Ideas

Aucune.
