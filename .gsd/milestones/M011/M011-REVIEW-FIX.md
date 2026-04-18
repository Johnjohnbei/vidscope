---
phase: M011
fixed_at: 2026-04-18T00:00:00Z
review_path: .gsd/milestones/M011/M011-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# M011 : Rapport de correction de revue de code

**Fixed at:** 2026-04-18
**Source review:** .gsd/milestones/M011/M011-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (1 Critical, 3 Warning)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01 : Interpolation f-string dans du DDL SQLite brut (`_ensure_analysis_v2_columns`)

**Files modified:** `src/vidscope/adapters/sqlite/schema.py`
**Commit:** fe3af1c
**Applied fix:** Ajout d'une allowlist `_ALLOWED_DDL_TYPES` pour valider `col_type` avant toute exécution DDL, et remplacement de l'interpolation brute du nom de colonne par un identifiant SQL correctement quoté (`"` avec doublage des guillemets internes via `replace('"', '""')`). Toute valeur `col_type` absente de l'allowlist lève désormais `ValueError` avant d'atteindre le `conn.execute`.

### WR-01 : `UntagVideoUseCase.execute` retourne `True` même si l'assignation était absente

**Files modified:** `src/vidscope/application/tag_video.py`
**Commit:** 1fd48ff
**Applied fix:** Option 1 du reviewer : appel à `uow.tags.list_for_video(vid)` pour vérifier que l'assignation existe réellement avant d'appeler `unassign`. Si le tag n'est pas dans la liste des tags assignés, la méthode retourne `False` sans appeler `unassign`. La docstring a été complétée pour documenter ce comportement explicitement.

### WR-02 : `ListCollectionsUseCase` — décompte vidéos silencieusement tronqué à 10 000

**Files modified:** `src/vidscope/application/collection_library.py`
**Commit:** 874df13
**Applied fix:** Deux changements coordonnés : (1) `CollectionSummary` reçoit un nouveau champ `is_count_capped: bool = False` documenté dans la docstring ; (2) `ListCollectionsUseCase.execute` fetche désormais `limit=10_001` au lieu de `10_000`, détecte la saturation (`len(vids) > 10_000`), plafonne `video_count` à `min(len(vids), 10_000)` et passe `is_count_capped=True` quand la collection dépasse le seuil. Les appelants peuvent ainsi afficher "10 000+" au lieu d'un nombre silencieusement faux.

### WR-03 : `MarkdownExporter.write` — accès d'attributs directs sur un objet `Any` sans protection

**Files modified:** `src/vidscope/adapters/export/markdown_exporter.py`
**Commit:** 6863418
**Applied fix:** Le résultat de `dataclasses.asdict(rec)` (déjà appelé pour le frontmatter YAML) est maintenant capturé dans la variable `d`. Les accès directs `rec.title`, `rec.url` et `rec.summary` sont remplacés par `d.get('title')`, `d.get('url', '')` et `d.get('summary')`. Le comportement est identique pour les `ExportRecord` valides ; pour tout objet non-dataclass, l'erreur se produit désormais sur `dataclasses.asdict(rec)` avec un message clair, cohérent avec `CsvExporter` et `JsonExporter`.

---

_Fixed: 2026-04-18_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
