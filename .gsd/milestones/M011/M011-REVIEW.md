---
phase: M011
reviewed: 2026-04-18T00:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - src/vidscope/adapters/export/__init__.py
  - src/vidscope/adapters/export/csv_exporter.py
  - src/vidscope/adapters/export/json_exporter.py
  - src/vidscope/adapters/export/markdown_exporter.py
  - src/vidscope/adapters/sqlite/collection_repository.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/tag_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/sqlite/video_tracking_repository.py
  - src/vidscope/application/collection_library.py
  - src/vidscope/application/export_library.py
  - src/vidscope/application/search_videos.py
  - src/vidscope/application/set_video_tracking.py
  - src/vidscope/application/tag_video.py
  - src/vidscope/cli/commands/collections.py
  - src/vidscope/cli/commands/export.py
  - src/vidscope/cli/commands/review.py
  - src/vidscope/cli/commands/search.py
  - src/vidscope/cli/commands/tags.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/values.py
  - src/vidscope/mcp/server.py
  - src/vidscope/ports/exporter.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# M011 : Rapport de revue de code

**Reviewed:** 2026-04-18
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Résumé

Revue portant sur l'ensemble des couches M011 : domaine, ports, adapteurs SQLite, cas d'utilisation et CLI. L'architecture hexagonale est bien respectée (les use cases n'importent rien des adapteurs, les ports sont de purs Protocols). Le schéma SQLite est idempotent et correctement migré. La gestion des transactions dans `SqliteUnitOfWork` est robuste.

Trois points méritent attention :

1. **Critique — injection SQL structurelle** dans `_ensure_analysis_v2_columns` : nom et type de colonne interpolés via f-string dans du DDL brut.
2. **Avertissement — bug sémantique** dans `UntagVideoUseCase.execute` : retourne `True` même quand l'assignation était déjà absente (contredit la docstring).
3. **Avertissement — décompte silencieusement inexact** dans `ListCollectionsUseCase` pour les collections de plus de 10 000 vidéos.

---

## Problèmes critiques

### CR-01 : Interpolation f-string dans du DDL SQLite brut (`_ensure_analysis_v2_columns`)

**File:** `src/vidscope/adapters/sqlite/schema.py:475`

**Issue:** Les valeurs `col_name` et `col_type` issues de la liste `new_columns` (lignes 461-471) sont interpolées directement dans un `text(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_type}")`. Actuellement ces valeurs sont des constantes codées en dur, ce qui est sûr. Cependant, le pattern viole la règle "no string interpolation in execute()" documentée dans le commentaire de sécurité en tête de chaque adapteur (T-SQL-M011-02). Si la liste `new_columns` est un jour alimentée dynamiquement (ex. depuis une config ou un schéma externe), cette ligne devient un vecteur d'injection DDL.

SQLite ne supporte pas les paramètres liés dans les instructions DDL (`ALTER TABLE`), mais le nom de colonne peut être entouré de guillemets pour être correctement échappé.

**Fix:**
```python
# Remplacer l'interpolation brute par un nom de colonne quoté
safe_col = col_name.replace('"', '""')   # SQL identifier escaping
conn.execute(
    text(f'ALTER TABLE analyses ADD COLUMN "{safe_col}" {col_type}')
)
# Et si col_type doit aussi être dynamique un jour, valider via allowlist :
ALLOWED_TYPES = {"JSON", "FLOAT", "VARCHAR(32)", "VARCHAR(64)", "BOOLEAN", "TEXT"}
if col_type not in ALLOWED_TYPES:
    raise ValueError(f"DDL type non autorisé : {col_type!r}")
```

---

## Avertissements

### WR-01 : `UntagVideoUseCase.execute` retourne `True` même si l'assignation était absente

**File:** `src/vidscope/application/tag_video.py:44-51`

**Issue:** La docstring de `execute` dit « Return True if an assignment was actually removed ». Or le code retourne `True` dès que le tag existe en base (tag n'est pas None et tag.id n'est pas None), sans vérifier si l'assignation était réellement présente avant l'appel à `unassign`. La méthode `unassign` est un no-op si l'assignation est absente (comportement voulu côté repo), mais le retour de `True` induit les appelants en erreur — le CLI affiche alors « removed tag … from video … » alors que rien n'a été supprimé.

```python
# Code actuel (ligne 51)
uow.tags.unassign(vid, tag.id)
return True   # FAUX : retourne True même si l'assignation n'existait pas
```

**Fix:**

Option 1 — vérifier l'assignation avant suppression :
```python
def execute(self, video_id: int, name: str) -> bool:
    vid = VideoId(int(video_id))
    with self._uow() as uow:
        tag = uow.tags.get_by_name(name)
        if tag is None or tag.id is None:
            return False
        # Vérifie si l'assignation existe avant d'appeler unassign
        assigned_tags = uow.tags.list_for_video(vid)
        if not any(t.id == tag.id for t in assigned_tags):
            return False
        uow.tags.unassign(vid, tag.id)
        return True
```

Option 2 (plus simple) — faire retourner un booléen par `unassign` (modifie le port) :
```python
# Dans TagRepository Protocol et TagRepositorySQLite
def unassign(self, video_id: VideoId, tag_id: int) -> bool:
    result = self._conn.execute(stmt)
    return result.rowcount > 0
```

### WR-02 : `ListCollectionsUseCase` — décompte vidéos silencieusement tronqué à 10 000

**File:** `src/vidscope/application/collection_library.py:93-94`

**Issue:** Pour calculer le `video_count` de chaque collection, le code charge tous les `video_id` en mémoire avec `list_videos(c.id, limit=10_000)` puis appelle `len()` sur la liste. Pour une collection contenant plus de 10 000 vidéos, le décompte affiché sera silencieusement `10 000` au lieu du nombre réel. Il n'y a aucun indicateur (`>10000 ?` ou warning) que la valeur est tronquée.

```python
# Ligne 93-94
vids = uow.collections.list_videos(c.id, limit=10_000)
results.append(CollectionSummary(collection=c, video_count=len(vids)))
```

**Fix:** Ajouter une méthode `count_videos(collection_id: int) -> int` au port `CollectionRepository` (et à son implémentation SQLite via `SELECT COUNT(*)`). À défaut, au moins documenter la limite et/ou renvoyer `10_000+` si la liste est saturée :

```python
vids = uow.collections.list_videos(c.id, limit=10_001)
count = len(vids)
is_capped = count > 10_000
results.append(CollectionSummary(
    collection=c,
    video_count=min(count, 10_000),
    # plus: ajouter un champ `is_count_capped: bool` dans CollectionSummary
))
```

### WR-03 : `MarkdownExporter.write` — accès d'attributs directs sur un objet `Any` sans protection

**File:** `src/vidscope/adapters/export/markdown_exporter.py:53-56`

**Issue:** Les lignes 53-56 accèdent à `rec.title`, `rec.url` et `rec.summary` directement sur des objets typés `Any`. Si un appelant passe un objet qui n'est pas un dataclass `ExportRecord` (violation du contrat non vérifiable à la compilation à cause du type `Any`), une `AttributeError` non informative est levée sans contexte. La même vulnérabilité est absente de `CsvExporter` et `JsonExporter` car ils passent par `dataclasses.asdict()` qui échouerait plus clairement.

```python
# Lignes 53-56 : accès direct sans vérification
lines.append(f"# {rec.title or rec.url}")
if rec.summary:
```

**Fix:** Extraire les champs via `dataclasses.asdict()` (comme le font les deux autres exporteurs) plutôt que d'accéder aux attributs directement, ou ajouter un `hasattr` défensif :

```python
d = dataclasses.asdict(rec)   # cohérent avec csv_exporter et json_exporter
lines.append(f"# {d.get('title') or d.get('url', '')}")
if d.get('summary'):
    lines.append("")
    lines.append(d['summary'])
```

---

## Info

### IN-01 : `CsvExporter.write` — comportement asymétrique quand `records` est vide

**File:** `src/vidscope/adapters/export/csv_exporter.py:33-38`

**Issue:** Quand `records` est vide et `out` est `None` (mode stdout), la fonction retourne silencieusement sans rien écrire — pas même le header CSV. Quand `out` est fourni, un fichier vide est écrit. Ce comportement asymétrique peut surprendre des consommateurs pipant la sortie vers un autre outil qui attend au moins un header.

**Fix:** Écrire le header même à vide, ou documenter explicitement ce choix dans la docstring. Si l'intention est de ne rien écrire du tout, unifier les deux branches :
```python
if not records:
    return  # Comportement uniforme : ne rien écrire dans les deux cas
```

### IN-02 : `TYPE_CHECKING` import inutilisé dans `export_library.py`

**File:** `src/vidscope/application/export_library.py:19-26`

**Issue:** Le bloc `if TYPE_CHECKING: pass` aux lignes 25-26 est vide. L'import `TYPE_CHECKING` à la ligne 19 est lui aussi inutile. Ces deux lignes sont du code mort.

```python
# Lignes 25-26 — bloc vide sans utilité
if TYPE_CHECKING:
    pass
```

**Fix:** Supprimer les deux lignes et l'import `TYPE_CHECKING` de la ligne 19.

### IN-03 : `_parse_tracking_status` dupliqué entre `search.py` et `export.py`

**File:** `src/vidscope/cli/commands/search.py:48-57` et `src/vidscope/cli/commands/export.py:50-59`

**Issue:** La fonction `_parse_tracking_status` est copiée à l'identique dans deux modules CLI. Toute modification du comportement (ex. ajout d'un statut, changement du message d'erreur) devra être répercutée dans les deux fichiers manuellement.

**Fix:** Extraire cette fonction dans le module `vidscope.cli._support` (ou un nouveau `vidscope.cli._parsers`) et l'importer dans les deux commandes :
```python
# Dans cli/_support.py ou cli/_parsers.py
def parse_tracking_status(raw: str | None) -> TrackingStatus | None:
    if raw is None:
        return None
    try:
        return TrackingStatus(raw.strip().lower())
    except ValueError as exc:
        valid = ", ".join(s.value for s in TrackingStatus)
        raise typer.BadParameter(
            f"--status must be one of: {valid}. Got {raw!r}."
        ) from exc
```

---

_Reviewed: 2026-04-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
