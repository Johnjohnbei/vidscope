---
phase: M012-S01
reviewed: 2026-04-20T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/vidscope/ports/pipeline.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/adapters/instaloader/downloader.py
  - src/vidscope/adapters/ytdlp/downloader.py
  - src/vidscope/pipeline/stages/ingest.py
  - tests/unit/ports/test_ingest_outcome.py
  - tests/unit/adapters/instaloader/test_downloader.py
  - tests/unit/adapters/ytdlp/test_downloader.py
  - tests/unit/adapters/sqlite/test_video_repository.py
  - tests/unit/adapters/sqlite/test_schema.py
  - tests/unit/pipeline/stages/test_ingest.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# M012/S01 — Rapport de revue de code

**Revue :** 2026-04-20
**Profondeur :** standard
**Fichiers revus :** 12
**Statut :** issues_found

## Résumé

La phase M012/S01 ajoute la cohérence des métadonnées à l'ingestion : champ `description` sur la table `videos`, compteurs d'engagement `like_count` / `comment_count` dans `IngestOutcome`, migration idempotente via `_ensure_description_column`, et création d'un snapshot `VideoStats` initial dans `IngestStage`. L'architecture est propre, la séparation des couches est respectée, et les tests couvrent les cas nominaux ainsi que les cas limites essentiels.

Aucun problème de sécurité critique n'a été identifié. La protection anti-injection DDL de `_add_columns_if_missing` est correcte (allowlist de types + échappement de l'identifiant de colonne). Trois points méritent attention : une injection DDL partielle restante sur le paramètre `table_name`, une expression redondante dans `InstaLoaderDownloader`, et deux absences de test qui réduisent la couverture du comportement réel.

---

## Avertissements

### WR-01 : Paramètre `table_name` non validé dans `_add_columns_if_missing`

**Fichier :** `src/vidscope/adapters/sqlite/schema.py:559,568`

**Problème :** La fonction `_add_columns_if_missing` valide correctement le type de colonne via une allowlist et échappe l'identifiant de colonne, mais le paramètre `table_name` est interpolé directement dans `PRAGMA table_info({table_name})` (ligne 559) et dans `ALTER TABLE {table_name} ADD COLUMN ...` (ligne 568) sans aucune validation ni échappement. Actuellement, les trois appelants passent des littéraux de chaînes codées en dur (`"videos"`, `"analyses"`), donc il n'y a pas de risque immédiat. Mais le commentaire de la fonction mentionne explicitement la défense contre l'injection DDL (T-SQL-M011-02), et cette protection est incomplète : un futur appelant qui passerait un `table_name` issu d'une source externe ouvrirait une injection DDL.

**Correctif :**
```python
_ALLOWED_TABLES: frozenset[str] = frozenset({
    "videos",
    "analyses",
    "transcripts",
    # ajouter les tables autorisées au fur et à mesure
})

def _add_columns_if_missing(
    conn: Connection,
    table_name: str,
    new_columns: list[tuple[str, str]],
    allowed_types: set[str],
) -> None:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Table non autorisée : {table_name!r}")
    # ... reste inchangé
```

---

### WR-02 : Test d'idempotence de la migration `description` ne couvre pas une base existante sans la colonne

**Fichier :** `tests/unit/adapters/sqlite/test_schema.py:118`

**Problème :** Le test `test_ensure_description_column_idempotent` appelle `init_db(engine)` deux fois sur une base fraîche. Il vérifie que le deuxième appel ne lève pas d'exception et que la colonne est présente. Cependant, il ne couvre pas le cas le plus risqué : une base de données pré-M012 qui possède déjà la table `videos` **sans** la colonne `description`. C'est exactement le scénario de production lors d'une mise à jour. Les autres migrations (visuelles, M010) ont un test dédié à ce cas (cf. `test_adds_columns_to_db_missing_them`). L'absence de ce test réduit la confiance en la migration en production.

**Correctif :** Ajouter un test qui crée manuellement la table `videos` sans la colonne `description`, appelle `_ensure_description_column`, puis vérifie la présence de la colonne :

```python
def test_ensure_description_column_on_pre_m012_db(self, tmp_path: object) -> None:
    from pathlib import Path
    from vidscope.adapters.sqlite.schema import _ensure_description_column
    from vidscope.infrastructure.sqlite_engine import build_engine

    db_path = Path(str(tmp_path)) / "pre_m012.db"
    eng = build_engine(db_path)
    with eng.begin() as conn:
        conn.execute(text(
            "CREATE TABLE videos ("
            "id INTEGER PRIMARY KEY, "
            "platform TEXT NOT NULL, "
            "platform_id TEXT NOT NULL UNIQUE, "
            "url TEXT NOT NULL, "
            "created_at TEXT NOT NULL"
            ")"
        ))
        _ensure_description_column(conn)
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
    assert "description" in cols
```

---

### WR-03 : Absence de test unitaire pour le cas où seul `comment_count` est présent (sans `like_count`)

**Fichier :** `tests/unit/pipeline/stages/test_ingest.py:584`

**Problème :** La condition de création du snapshot `VideoStats` dans `IngestStage.execute()` est `if outcome.like_count is not None or outcome.comment_count is not None` (ligne 202 de `ingest.py`). Les tests couvrent le cas « les deux non nuls » et le cas « tous les deux None », mais pas les cas asymétriques : `like_count=42, comment_count=None` ou `like_count=None, comment_count=5`. Ces deux branches de la condition `or` peuvent se comporter différemment selon la plateforme (Instagram n'expose pas toujours les deux). Si la logique était un `and` au lieu d'un `or`, le test ne le détecterait pas.

**Correctif :** Ajouter deux tests paramétrés :

```python
@pytest.mark.parametrize("like_count,comment_count", [
    (42, None),
    (None, 5),
])
def test_stats_created_when_only_one_engagement_field_present(
    self, engine, media_storage, cache_dir, like_count, comment_count
) -> None:
    downloader = FakeDownloader(
        outcome_factory=_instagram_outcome_factory(
            "p_partial01",
            like_count=like_count,
            comment_count=comment_count,
        )
    )
    stage = IngestStage(downloader=downloader, media_storage=media_storage, cache_dir=cache_dir)
    ctx = PipelineContext(source_url="https://instagram.com/p/p_partial01/")
    with SqliteUnitOfWork(engine) as uow:
        stage.execute(ctx, uow)
    with SqliteUnitOfWork(engine) as uow:
        latest = uow.video_stats.latest_for_video(ctx.video_id)
        assert latest is not None
```

---

## Informations

### IN-01 : Expression redondante `post.likes if post.likes is not None else None`

**Fichier :** `src/vidscope/adapters/instaloader/downloader.py:110-111`

**Problème :** Les lignes 110-111 font :
```python
like_count=post.likes if post.likes is not None else None,
comment_count=post.comments if post.comments is not None else None,
```
L'expression ternaire `x if x is not None else None` est équivalente à `x` directement. Elle ne filtre pas les zéros ou les falsy non-None. C'est du code superflu qui n'apporte aucune transformation.

**Correctif :**
```python
like_count=post.likes,
comment_count=post.comments,
```

---

### IN-02 : Import `re` en milieu de fichier dans `ytdlp/downloader.py`

**Fichier :** `src/vidscope/adapters/ytdlp/downloader.py:47`

**Problème :** L'import `import re` (ligne 47) est intercalé entre deux blocs d'imports du projet, après les imports tiers (`yt_dlp`). La convention PEP 8 / isort place les imports de la bibliothèque standard avant les imports tiers. Ici l'ordre est : stdlib (`pathlib`, `typing`) → tiers (`yt_dlp`) → stdlib (`re`) → projet.

**Correctif :** Déplacer `import re` avec les autres imports stdlib en tête de fichier :
```python
import re
from pathlib import Path
from typing import Any, Final
```

---

### IN-03 : La migration `_ensure_description_column` ne teste pas le type de colonne sur les données de migration (base existante)

**Fichier :** `tests/unit/adapters/sqlite/test_schema.py:118`

**Problème :** Le test existant vérifie que `cols["description"].upper() == "TEXT"` après un `init_db` complet sur une base fraîche. Mais il ne vérifie pas que les lignes **préexistantes** dans `videos` survivent à la migration avec `description IS NULL`. Les migrations `_ensure_visual_media_columns` et `_ensure_analysis_v2_columns` ont des tests dédiés à la survie des données (par exemple `test_pre_existing_rows_survive_migration`). Ce test est absent pour la colonne `description`.

**Correctif :** Ajouter un test similaire à `test_pre_existing_rows_survive_migration` pour la colonne `description` :

```python
def test_pre_m012_rows_survive_description_migration(self, tmp_path: object) -> None:
    from pathlib import Path
    from vidscope.adapters.sqlite.schema import _ensure_description_column
    from vidscope.infrastructure.sqlite_engine import build_engine

    db_path = Path(str(tmp_path)) / "pre_m012_data.db"
    eng = build_engine(db_path)
    with eng.begin() as conn:
        conn.execute(text(
            "CREATE TABLE videos (id INTEGER PRIMARY KEY, platform TEXT NOT NULL, "
            "platform_id TEXT NOT NULL UNIQUE, url TEXT NOT NULL, created_at TEXT NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO videos (platform, platform_id, url, created_at) "
            "VALUES ('youtube', 'pre_row', 'https://example.com', '2026-01-01')"
        ))
        _ensure_description_column(conn)

    with eng.connect() as conn:
        row = conn.execute(
            text("SELECT platform_id, description FROM videos WHERE platform_id = 'pre_row'")
        ).mappings().first()
    assert row is not None
    assert row["platform_id"] == "pre_row"
    assert row["description"] is None
```

---

_Revue réalisée le : 2026-04-20_
_Réviseur : Claude (gsd-code-reviewer)_
_Profondeur : standard_
