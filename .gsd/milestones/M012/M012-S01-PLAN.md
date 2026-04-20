---
phase: M012
plan: S01
type: execute
wave: 1
depends_on: []
files_modified:
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
autonomous: true
requirements: [R060, R061]
must_haves:
  truths:
    - "`IngestOutcome` in `src/vidscope/ports/pipeline.py` has fields `like_count: int | None = None` and `comment_count: int | None = None` after `carousel_items`"
    - "`videos` table has a `description TEXT` nullable column added via `_ensure_description_column` called from `init_db` — idempotent migration"
    - "`VideoRepository._video_to_row()` maps `description` field; `_row_to_video()` reads it back"
    - "`InstaLoaderDownloader.download()` populates `description=post.caption` (full text) and `like_count=post.likes`, `comment_count=post.comments` in the returned `IngestOutcome`"
    - "`YtdlpDownloader._info_to_outcome()` populates `like_count=_int_or_none(info.get('like_count'))` and `comment_count=_int_or_none(info.get('comment_count'))`"
    - "`IngestStage.execute()` passes `description=outcome.description` to `Video(...)` and calls `uow.video_stats.append(VideoStats(...))` when `like_count` or `comment_count` is not None"
    - "Ingestion with null caption/engagement completes without error — `description` and stats remain null gracefully"
    - "`vidscope show <id>` displays `description` and engagement stats from ingestion without running `vidscope refresh-stats` — no show.py changes needed (already reads these fields)"
  artifacts:
    - path: "src/vidscope/ports/pipeline.py"
      provides: "IngestOutcome dataclass extended with engagement fields"
      contains: "like_count: int | None = None"
    - path: "src/vidscope/adapters/sqlite/schema.py"
      provides: "Idempotent migration adding description column to videos"
      contains: "_ensure_description_column"
    - path: "src/vidscope/adapters/sqlite/video_repository.py"
      provides: "Description round-trip between Video entity and SQLite row"
      contains: '"description": video.description'
    - path: "src/vidscope/adapters/instaloader/downloader.py"
      provides: "Instagram carousel/image/reel metadata coherence at ingest"
      contains: "description=post.caption"
    - path: "src/vidscope/adapters/ytdlp/downloader.py"
      provides: "yt-dlp engagement extraction at ingest"
      contains: "like_count=_int_or_none"
    - path: "src/vidscope/pipeline/stages/ingest.py"
      provides: "Persisting description + initial VideoStats during ingest stage"
      contains: "uow.video_stats.append"
  key_links:
    - from: "src/vidscope/adapters/instaloader/downloader.py"
      to: "src/vidscope/ports/pipeline.py::IngestOutcome"
      via: "IngestOutcome construction returning description+like_count+comment_count"
      pattern: "description=post\\.caption.*like_count=post\\.likes"
    - from: "src/vidscope/adapters/ytdlp/downloader.py::_info_to_outcome"
      to: "src/vidscope/ports/pipeline.py::IngestOutcome"
      via: "IngestOutcome construction pulling like_count/comment_count from info dict"
      pattern: "like_count=_int_or_none\\(info\\.get\\(\"like_count\"\\)\\)"
    - from: "src/vidscope/pipeline/stages/ingest.py::IngestStage.execute"
      to: "src/vidscope/adapters/sqlite/video_repository.py"
      via: "Video(description=outcome.description) persisted via uow.videos"
      pattern: "description=outcome\\.description"
    - from: "src/vidscope/pipeline/stages/ingest.py::IngestStage.execute"
      to: "uow.video_stats"
      via: "VideoStats append when downloader provides like_count or comment_count"
      pattern: "uow\\.video_stats\\.append\\(VideoStats"
    - from: "src/vidscope/adapters/sqlite/schema.py::init_db"
      to: "videos.description column"
      via: "_ensure_description_column(conn) inside init_db transaction"
      pattern: "_ensure_description_column\\(conn\\)"
---

<objective>
M012/S01 — Metadata cohérence à l'ingestion.

Tout contenu ingéré (carousel Instagram, image, reel, vidéo yt-dlp) doit produire, dès la fin de `vidscope add <url>`, deux faits observables en DB :

1. **R060** — `videos.description` contient la caption complète du post (non-tronquée), ou `NULL` si le post n'a pas de caption.
2. **R061** — `video_stats` contient une ligne initiale avec `like_count` et/ou `comment_count` quand la plateforme les fournit, sans qu'il soit nécessaire d'exécuter `vidscope refresh-stats`.

Purpose : supprimer l'étape manuelle actuelle (`refresh-stats` obligatoire pour voir l'engagement, description absente sur carousel). `vidscope show <id>` devient source de vérité immédiate après `add`.

Output : schéma DB migré (colonne `description` nullable), port `IngestOutcome` étendu, deux downloaders (Instagram, yt-dlp) qui peuplent ces champs, `IngestStage` qui les persiste, couverture de tests unitaires bout-en-bout.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M012/M012-ROADMAP.md

# Port touché
@src/vidscope/ports/pipeline.py

# Schéma + repo touchés
@src/vidscope/adapters/sqlite/schema.py
@src/vidscope/adapters/sqlite/video_repository.py

# Downloaders touchés
@src/vidscope/adapters/instaloader/downloader.py
@src/vidscope/adapters/ytdlp/downloader.py

# Stage touché
@src/vidscope/pipeline/stages/ingest.py

# Tests existants à étendre
@tests/unit/ports/test_ingest_outcome.py
@tests/unit/adapters/instaloader/test_downloader.py
@tests/unit/adapters/ytdlp/test_downloader.py
@tests/unit/adapters/sqlite/test_video_repository.py
@tests/unit/adapters/sqlite/test_schema.py
@tests/unit/pipeline/stages/test_ingest.py

<interfaces>
<!-- Contrats indispensables à l'exécuteur. Extraits du code existant — pas d'exploration nécessaire. -->

From src/vidscope/ports/pipeline.py (IngestOutcome avant patch) :
```python
@dataclass(frozen=True, slots=True)
class IngestOutcome:
    platform: Platform
    platform_id: PlatformId
    url: str
    media_path: str
    title: str | None = None
    author: str | None = None
    duration: float | None = None
    upload_date: str | None = None
    view_count: int | None = None
    creator_info: CreatorInfo | None = None
    description: str | None = None
    hashtags: tuple[str, ...] = ()
    mentions: tuple[Mention, ...] = ()
    music_track: str | None = None
    music_artist: str | None = None
    media_type: MediaType = MediaType.VIDEO
    carousel_items: tuple[str, ...] = ()
    # NOUVEAUX CHAMPS à ajouter (après carousel_items) :
    # like_count: int | None = None
    # comment_count: int | None = None
```

From src/vidscope/domain (VideoStats) :
```python
@dataclass(frozen=True, slots=True)
class VideoStats:
    video_id: VideoId
    captured_at: datetime   # MUST be UTC-aware, microsecond=0
    view_count: int | None = None
    like_count: int | None = None
    repost_count: int | None = None
    comment_count: int | None = None
    save_count: int | None = None
    id: int | None = None
    created_at: datetime | None = None
```

From src/vidscope/adapters/sqlite/schema.py (pattern de migration idempotente déjà utilisé) :
```python
def _ensure_visual_media_columns(conn: Connection) -> None:
    new_columns = [
        ("thumbnail_key", "TEXT"),
        ("content_shape", "VARCHAR(32)"),
        ("media_type", "VARCHAR(20)"),
    ]
    _ALLOWED = {"TEXT", "VARCHAR(32)", "VARCHAR(20)"}
    _add_columns_if_missing(conn, "videos", new_columns, _ALLOWED)
```
→ Le nouveau `_ensure_description_column` suit exactement ce pattern.

From src/vidscope/adapters/sqlite/schema.py (bloc init_db à étendre) :
```python
def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
        _ensure_analysis_v2_columns(conn)
        _ensure_video_tracking_table(conn)   # M011/S01
        _ensure_tags_collections_tables(conn) # M011/S02
        _ensure_m006_m007_m008_tables(conn)   # M006/M007/M008
        _ensure_visual_media_columns(conn)    # visual_intelligence + media_type
        # À AJOUTER APRÈS :
        # _ensure_description_column(conn)    # M012/S01
```

From src/vidscope/adapters/ytdlp/downloader.py (helper existant) :
```python
# _int_or_none(value) → int ou None, utilisé par _info_to_outcome
# Signature : def _int_or_none(value: Any) -> int | None
```
</interfaces>
</context>

<tasks>

<!-- ====================================================================== -->
<!-- WAVE 1 — Contrats + schéma : parallélisables (fichiers disjoints)      -->
<!-- ====================================================================== -->

<task type="auto" tdd="true">
  <name>T01: Schema migration — add description TEXT column to videos table</name>
  <files>src/vidscope/adapters/sqlite/schema.py</files>
  <read_first>
    - src/vidscope/adapters/sqlite/schema.py (lignes 414-443 pour init_db ; lignes 845-858 pour _ensure_visual_media_columns pattern)
  </read_first>
  <behavior>
    - Appel répété de init_db sur la même engine ne doit pas lever
    - Après init_db sur une fresh DB : PRAGMA table_info(videos) liste une colonne nommée exactement "description" de type TEXT nullable
    - Après init_db sur une DB pré-M012 (sans description) : la colonne est ajoutée, données existantes préservées avec description=NULL
    - Après init_db sur une DB déjà migrée : aucune ALTER TABLE émise, pas d'erreur
  </behavior>
  <action>
Ajouter la fonction de migration juste après `_ensure_visual_media_columns` (vers la ligne 859) :

```python
def _ensure_description_column(conn: Connection) -> None:
    """M012/S01 migration: add description column to videos table.

    Idempotent — safe to call on every startup. Pre-existing rows get NULL;
    new ingest populates from downloader outcome (R060).
    """
    new_columns = [("description", "TEXT")]
    _ALLOWED = {"TEXT"}
    _add_columns_if_missing(conn, "videos", new_columns, _ALLOWED)
```

Dans `init_db`, ajouter l'appel dans le `with engine.begin() as conn:` bloc, immédiatement après `_ensure_visual_media_columns(conn)` :

```python
        _ensure_visual_media_columns(conn)    # visual_intelligence + media_type
        _ensure_description_column(conn)      # M012/S01
```

Ne PAS modifier la définition SQLAlchemy Core de la table `videos` — la colonne est purement additive via ALTER TABLE (cohérent avec pattern M006/M010/M011).
  </action>
  <verify>
    <automated>python -c "from sqlalchemy import create_engine, text; from vidscope.adapters.sqlite.schema import init_db; e=create_engine('sqlite:///:memory:'); init_db(e); init_db(e); cols=[r[1] for r in e.connect().execute(text('PRAGMA table_info(videos)'))]; assert 'description' in cols, cols; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "_ensure_description_column" src/vidscope/adapters/sqlite/schema.py` retourne au moins 2 lignes (définition + appel)
    - `grep -n '"description", "TEXT"' src/vidscope/adapters/sqlite/schema.py` retourne 1 ligne
    - `grep -n "M012/S01" src/vidscope/adapters/sqlite/schema.py` retourne au moins 2 lignes
    - `python -c "from vidscope.adapters.sqlite.schema import _ensure_description_column"` ne lève pas
  </acceptance_criteria>
  <done>
    La fonction `_ensure_description_column` est définie, appelée depuis `init_db`, idempotente, n'ajoute la colonne que si absente. Tests T12 passent.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T02: Port — add like_count / comment_count to IngestOutcome</name>
  <files>src/vidscope/ports/pipeline.py</files>
  <read_first>
    - src/vidscope/ports/pipeline.py (lignes 179-205 pour le dataclass IngestOutcome)
  </read_first>
  <behavior>
    - `IngestOutcome(platform=..., platform_id=..., url=..., media_path=...)` construit sans args supplémentaires → `o.like_count is None` et `o.comment_count is None`
    - `IngestOutcome(..., like_count=42, comment_count=7)` → valeurs préservées (round-trip)
    - Le dataclass reste `frozen=True, slots=True` — aucun autre champ renommé ni modifié
  </behavior>
  <action>
Dans `IngestOutcome` (src/vidscope/ports/pipeline.py), ajouter **exactement** ces deux lignes juste après `carousel_items: tuple[str, ...] = ()` :

```python
    like_count: int | None = None
    comment_count: int | None = None
```

Le dataclass final doit ressembler à :

```python
@dataclass(frozen=True, slots=True)
class IngestOutcome:
    platform: Platform
    platform_id: PlatformId
    url: str
    media_path: str
    title: str | None = None
    author: str | None = None
    duration: float | None = None
    upload_date: str | None = None
    view_count: int | None = None
    creator_info: CreatorInfo | None = None
    description: str | None = None
    hashtags: tuple[str, ...] = ()
    mentions: tuple[Mention, ...] = ()
    music_track: str | None = None
    music_artist: str | None = None
    media_type: MediaType = MediaType.VIDEO
    carousel_items: tuple[str, ...] = ()
    like_count: int | None = None
    comment_count: int | None = None
```

Ne PAS toucher à `__all__`, `Downloader`, ni aux autres classes.
  </action>
  <verify>
    <automated>python -c "from vidscope.ports.pipeline import IngestOutcome; from vidscope.domain import Platform, PlatformId; o=IngestOutcome(platform=Platform.YOUTUBE, platform_id=PlatformId('x'), url='u', media_path='p'); assert o.like_count is None and o.comment_count is None; o2=IngestOutcome(platform=Platform.YOUTUBE, platform_id=PlatformId('x'), url='u', media_path='p', like_count=42, comment_count=7); assert o2.like_count==42 and o2.comment_count==7; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "like_count: int | None = None" src/vidscope/ports/pipeline.py` retourne 1 ligne (dans IngestOutcome)
    - `grep -n "comment_count: int | None = None" src/vidscope/ports/pipeline.py` retourne 1 ligne (dans IngestOutcome)
    - `grep -c "like_count\|comment_count" src/vidscope/ports/pipeline.py` retourne 2 ou plus
    - Aucun autre champ du dataclass n'est modifié ou supprimé (diff minimal : +2 lignes)
  </acceptance_criteria>
  <done>
    `IngestOutcome` expose `like_count: int | None = None` et `comment_count: int | None = None`. Tests T07 passent.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T03: VideoRepository — map description field in row<->Video round-trip</name>
  <files>src/vidscope/adapters/sqlite/video_repository.py</files>
  <read_first>
    - src/vidscope/adapters/sqlite/video_repository.py (méthodes `_video_to_row` et `_row_to_video`)
    - src/vidscope/domain pour vérifier que `Video` dataclass a bien un champ `description: str | None`
  </read_first>
  <behavior>
    - `repo.upsert(Video(..., description="Caption text"))` puis `repo.get(id)` → Video avec `description == "Caption text"`
    - `repo.upsert(Video(..., description=None))` puis `repo.get(id)` → Video avec `description is None`
    - Aucun autre champ existant n'est cassé (platform, platform_id, url, author, title, duration, upload_date, view_count, media_key, thumbnail_key, content_shape, media_type round-trip)
  </behavior>
  <action>
1. Dans `_video_to_row`, ajouter **une seule entrée** au dict retourné, juste après `"media_key": video.media_key,` :

```python
"description": video.description,
```

2. Dans `_row_to_video`, ajouter **une seule entrée** au constructeur `Video(...)`, à une position cohérente avec l'ordre existant dans le Video dataclass (typiquement après `view_count=...` ou avant `media_key=...`) :

```python
description=data.get("description"),
```

Le `.get()` (et non `data["description"]`) est indispensable : sur une DB pré-M012 où la colonne vient d'être ajoutée, les anciennes lignes ont `description=NULL` mais SELECT les inclut ; `.get()` gère aussi le cas théorique où le dict ne contient pas la clé (robustesse).

Ne PAS modifier la liste des colonnes SELECT (SQLAlchemy Core `select(videos)` remonte toutes les colonnes automatiquement, incluant la nouvelle `description` après migration T01).
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n '"description": video.description' src/vidscope/adapters/sqlite/video_repository.py` retourne exactement 1 ligne
    - `grep -n "description=data.get" src/vidscope/adapters/sqlite/video_repository.py` retourne exactement 1 ligne
    - Diff minimal : 2 lignes ajoutées, 0 supprimée
  </acceptance_criteria>
  <done>
    `description` round-trip via VideoRepository (Video → ligne SQLite → Video). Tests T11 passent.
  </done>
</task>

<!-- ====================================================================== -->
<!-- WAVE 2 — Downloaders + IngestStage (dépendent de Wave 1)               -->
<!-- ====================================================================== -->

<task type="auto" tdd="true">
  <name>T04: InstaLoaderDownloader — populate description (full caption) + like_count + comment_count</name>
  <files>src/vidscope/adapters/instaloader/downloader.py</files>
  <read_first>
    - src/vidscope/adapters/instaloader/downloader.py (construction `IngestOutcome(...)` à la fin de `download()`)
    - tests/unit/adapters/instaloader/test_downloader.py (`_make_post` helper : structure du mock `Post` pour savoir quoi étendre en T08)
  </read_first>
  <behavior>
    - Post avec caption "Foo bar..." (300 chars) → outcome.description == caption (texte complet, non tronqué), outcome.title == caption[:200]
    - Post avec caption=None → outcome.description is None, outcome.title is None
    - Post avec likes=123, comments=45 → outcome.like_count == 123, outcome.comment_count == 45
    - Post avec likes=None, comments=None → outcome.like_count is None, outcome.comment_count is None
  </behavior>
  <action>
Dans la construction de `IngestOutcome(...)` à la fin de `download()`, ajouter **exactement** ces trois champs (garder `title=post.caption[:200] if post.caption else None` tel quel) :

```python
    description=post.caption,
    like_count=post.likes if post.likes is not None else None,
    comment_count=post.comments if post.comments is not None else None,
```

Position : immédiatement après les champs actuels (title, author, duration, upload_date, view_count, media_type, carousel_items, etc.). L'ordre des kwargs n'a pas d'importance sémantique mais garder l'ordre cohérent avec l'ordre déclaré dans IngestOutcome facilite la lecture.

Notes d'implémentation :
- `post.caption` est `str | None` dans instaloader — assignation directe sans coalescing (None reste None).
- `post.likes` et `post.comments` sont `int` (la plupart du temps) mais on garde le pattern défensif `if X is not None else None` pour documenter l'intention, bien que techniquement redondant.
- Ne PAS tronquer `description` (contrairement à `title[:200]`) — R060 exige la caption complète pour la recherche plein-texte et l'analyse future.

Ne PAS toucher à la logique d'extraction `media_path`, `media_type`, `carousel_items` — cette tâche est strictement additive sur l'outcome.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/instaloader/test_downloader.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "description=post.caption" src/vidscope/adapters/instaloader/downloader.py` retourne exactement 1 ligne
    - `grep -n "like_count=post.likes" src/vidscope/adapters/instaloader/downloader.py` retourne exactement 1 ligne
    - `grep -n "comment_count=post.comments" src/vidscope/adapters/instaloader/downloader.py` retourne exactement 1 ligne
    - `grep -n "title=post.caption\[:200\]" src/vidscope/adapters/instaloader/downloader.py` retourne toujours 1 ligne (non supprimée)
  </acceptance_criteria>
  <done>
    InstaLoaderDownloader.download() retourne un IngestOutcome avec description/like_count/comment_count peuplés depuis l'objet Post. Tests T08 passent.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T05: YtdlpDownloader — populate like_count + comment_count from info dict</name>
  <files>src/vidscope/adapters/ytdlp/downloader.py</files>
  <read_first>
    - src/vidscope/adapters/ytdlp/downloader.py (fonction `_info_to_outcome` + helper `_int_or_none`)
    - `description=_str_or_none(info.get("description"))` est déjà présent → inchangé
  </read_first>
  <behavior>
    - info = {"like_count": 500, "comment_count": 30, ...} → outcome.like_count == 500, outcome.comment_count == 30
    - info = {} (aucun des deux champs) → outcome.like_count is None, outcome.comment_count is None
    - info = {"like_count": None} → outcome.like_count is None (via _int_or_none)
    - info = {"like_count": "500"} (chaîne) → outcome.like_count == 500 si _int_or_none coerce (sinon None — comportement existant préservé)
  </behavior>
  <action>
Dans `_info_to_outcome`, dans la construction de `IngestOutcome(...)`, ajouter **exactement** ces deux champs immédiatement après `carousel_items=carousel_items,` (ou à la position équivalente — en fin de kwargs juste avant la parenthèse fermante) :

```python
    like_count=_int_or_none(info.get("like_count")),
    comment_count=_int_or_none(info.get("comment_count")),
```

Notes :
- Réutiliser le helper `_int_or_none` existant — ne PAS créer de duplicata.
- `info.get("like_count")` retourne `None` si la clé est absente → `_int_or_none(None)` doit déjà renvoyer `None` (comportement standard du helper).
- Ne PAS modifier la ligne existante `description=_str_or_none(info.get("description"))` (déjà correcte pour R060 côté yt-dlp).
- Ne PAS toucher à `view_count`, `duration`, `upload_date`, ni aux autres extractions.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n 'like_count=_int_or_none(info.get("like_count"))' src/vidscope/adapters/ytdlp/downloader.py` retourne exactement 1 ligne
    - `grep -n 'comment_count=_int_or_none(info.get("comment_count"))' src/vidscope/adapters/ytdlp/downloader.py` retourne exactement 1 ligne
    - `grep -n 'description=_str_or_none(info.get("description"))' src/vidscope/adapters/ytdlp/downloader.py` retourne toujours 1 ligne (préservée)
  </acceptance_criteria>
  <done>
    YtdlpDownloader._info_to_outcome() extrait like_count/comment_count de l'info dict yt-dlp. Tests T09 passent.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T06: IngestStage — wire description into Video + persist initial VideoStats</name>
  <files>src/vidscope/pipeline/stages/ingest.py</files>
  <read_first>
    - src/vidscope/pipeline/stages/ingest.py (intégralité ; identifier la construction Video(...) et la fin de execute())
    - src/vidscope/domain (importabilité de VideoStats)
  </read_first>
  <behavior>
    - Après execute(), la Video persistée a description == outcome.description (peut être None)
    - Si outcome.like_count ou outcome.comment_count est non-None → exactement UNE ligne video_stats insérée pour (video_id, captured_at) avec captured_at UTC-aware, microsecond=0
    - Si outcome.like_count ET outcome.comment_count sont tous deux None → aucune ligne video_stats insérée (pas d'erreur non plus)
    - view_count est aussi transmis à Video (inchangé) ; le VideoStats initial NE contient PAS view_count (uniquement like_count/comment_count) — on reste strict sur R061 (l'engagement = likes/comments, view_count reste dans videos.view_count)
    - Pas de régression : carousel_item_keys, media_key, transcript, analysis_id continuent de fonctionner
  </behavior>
  <action>
Trois modifications **dans cet ordre** dans `src/vidscope/pipeline/stages/ingest.py` :

**1. Imports (en haut du fichier, avec les autres imports)** :

Ajouter si absents :
```python
from datetime import UTC, datetime
from vidscope.domain import VideoStats
```

Note : `datetime` et `UTC` sont peut-être déjà importés — vérifier ; si oui, ne pas dupliquer. `VideoStats` est probablement absent.

**2. Dans la construction `Video(...)`** :

Ajouter exactement ce champ après `view_count=outcome.view_count,` :
```python
description=outcome.description,
```

Position cohérente avec l'ordre du dataclass Video (si l'ordre des kwargs diffère, garder un ordre lisible — la clé est juste de transmettre la valeur).

**3. Persistance du VideoStats initial** :

Après la ligne `ctx.carousel_item_keys = carousel_stored` (ou la ligne équivalente qui finalise l'état du contexte), ajouter **exactement** ce bloc :

```python
        # R061: persist initial engagement snapshot when the downloader
        # surfaced like_count/comment_count at ingest time — avoids the
        # need for a follow-up `vidscope refresh-stats`.
        if outcome.like_count is not None or outcome.comment_count is not None:
            initial_stats = VideoStats(
                video_id=persisted.id,
                captured_at=datetime.now(UTC).replace(microsecond=0),
                like_count=outcome.like_count,
                comment_count=outcome.comment_count,
            )
            uow.video_stats.append(initial_stats)
```

Notes d'implémentation :
- Utiliser le nom exact `persisted` s'il existe déjà dans le scope (c'est le nom conventionnel après `uow.videos.upsert(...)`). Si le nom local diffère (ex: `video`, `saved_video`), utiliser celui déjà en scope — NE PAS introduire un nom incohérent.
- `captured_at` **doit** être UTC-aware et tronqué à la seconde (`replace(microsecond=0)`) — cohérent avec M009/D-01 et la contrainte UNIQUE (video_id, captured_at) de la table video_stats.
- `view_count` NE DOIT PAS être dupliqué dans le VideoStats initial (il reste dans videos.view_count via Video). On ne snapshote que like/comment à l'ingestion.
- Ne PAS wrapper dans un try/except : si `uow.video_stats.append` lève, la transaction doit se rollback naturellement (comportement pipeline standard).
  </action>
  <verify>
    <automated>python -m pytest tests/unit/pipeline/stages/test_ingest.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "description=outcome.description" src/vidscope/pipeline/stages/ingest.py` retourne exactement 1 ligne
    - `grep -n "from vidscope.domain import VideoStats\|VideoStats," src/vidscope/pipeline/stages/ingest.py` retourne au moins 1 ligne (import)
    - `grep -n "uow.video_stats.append" src/vidscope/pipeline/stages/ingest.py` retourne exactement 1 ligne
    - `grep -n "like_count=outcome.like_count" src/vidscope/pipeline/stages/ingest.py` retourne exactement 1 ligne
    - `grep -n "comment_count=outcome.comment_count" src/vidscope/pipeline/stages/ingest.py` retourne exactement 1 ligne
    - `grep -n "captured_at=datetime.now(UTC).replace(microsecond=0)" src/vidscope/pipeline/stages/ingest.py` retourne exactement 1 ligne
    - `grep -n "outcome.like_count is not None or outcome.comment_count is not None" src/vidscope/pipeline/stages/ingest.py` retourne exactement 1 ligne
  </acceptance_criteria>
  <done>
    IngestStage transmet description à Video et persiste un VideoStats initial quand l'engagement est fourni par le downloader. Tests T10 passent.
  </done>
</task>

<!-- ====================================================================== -->
<!-- WAVE 3 — Tests unitaires (dépendent de Waves 1 & 2)                    -->
<!-- ====================================================================== -->

<task type="auto">
  <name>T07: Test — IngestOutcome engagement fields (defaults + round-trip)</name>
  <files>tests/unit/ports/test_ingest_outcome.py</files>
  <read_first>
    - tests/unit/ports/test_ingest_outcome.py (structure existante, imports, fixtures, helper de construction)
  </read_first>
  <action>
Ajouter une nouvelle classe de tests `TestIngestOutcomeEngagement` en fin de fichier (après les classes existantes). Réutiliser les imports / helpers déjà présents (Platform, PlatformId, IngestOutcome).

```python
class TestIngestOutcomeEngagement:
    """R061 — IngestOutcome carries initial engagement counters."""

    def test_engagement_fields_default_to_none(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            url="https://example.com/v/abc123",
            media_path="/tmp/x.mp4",
        )
        assert outcome.like_count is None
        assert outcome.comment_count is None

    def test_engagement_fields_round_trip(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            url="https://example.com/v/abc123",
            media_path="/tmp/x.mp4",
            like_count=42,
            comment_count=7,
        )
        assert outcome.like_count == 42
        assert outcome.comment_count == 7
```

Si Platform ou PlatformId ne sont pas importés en haut du fichier, reprendre les imports existants d'autres tests du même fichier (ne rien inventer).
  </action>
  <verify>
    <automated>python -m pytest tests/unit/ports/test_ingest_outcome.py::TestIngestOutcomeEngagement -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "TestIngestOutcomeEngagement" tests/unit/ports/test_ingest_outcome.py` retourne 1 ligne
    - `grep -n "test_engagement_fields_default_to_none\|test_engagement_fields_round_trip" tests/unit/ports/test_ingest_outcome.py` retourne 2 lignes
    - `grep -c "like_count\|comment_count" tests/unit/ports/test_ingest_outcome.py` retourne au moins 4
    - Les deux tests passent sous pytest
  </acceptance_criteria>
  <done>
    Les deux tests passent ; aucun test existant du fichier n'est cassé.
  </done>
</task>

<task type="auto">
  <name>T08: Test — InstaLoaderDownloader populates description + engagement</name>
  <files>tests/unit/adapters/instaloader/test_downloader.py</files>
  <read_first>
    - tests/unit/adapters/instaloader/test_downloader.py (helper `_make_post`, classe `TestInstaLoaderDownloaderDownload`, style de mocking)
  </read_first>
  <action>
1. Étendre le helper `_make_post` (ou créer une variante si modifier l'existant casse d'autres tests) pour accepter deux nouveaux paramètres optionnels :

```python
def _make_post(*, caption: str | None = "default caption", likes: int | None = 10, comments: int | None = 2, ...):
    post = MagicMock()
    post.caption = caption
    post.likes = likes
    post.comments = comments
    # ... autres attributs existants ...
    return post
```

Si la signature existante utilise un MagicMock sans paramètres dédiés, adapter le pattern en conservant rétrocompatibilité (valeurs par défaut pour `likes` et `comments`).

2. Ajouter quatre tests à `TestInstaLoaderDownloaderDownload` :

```python
def test_caption_populates_description(self, tmp_path: Path) -> None:
    """R060 — full caption goes to outcome.description (not just title)."""
    caption = "A" * 300  # > 200 chars → title tronqué mais description complète
    post = _make_post(caption=caption)
    # ... instancier le downloader avec ses mocks usuels (instaloader client mocké) ...
    outcome = downloader.download(url="https://instagram.com/p/xyz/", destination_dir=str(tmp_path))
    assert outcome.description == caption
    assert outcome.title == caption[:200]

def test_null_caption_gives_null_description(self, tmp_path: Path) -> None:
    post = _make_post(caption=None)
    # ...
    outcome = downloader.download(url="https://instagram.com/p/xyz/", destination_dir=str(tmp_path))
    assert outcome.description is None
    assert outcome.title is None

def test_engagement_stats_populated(self, tmp_path: Path) -> None:
    """R061 — like_count / comment_count extracted from Post."""
    post = _make_post(likes=123, comments=45)
    # ...
    outcome = downloader.download(url="https://instagram.com/p/xyz/", destination_dir=str(tmp_path))
    assert outcome.like_count == 123
    assert outcome.comment_count == 45

def test_none_likes_gives_none_engagement(self, tmp_path: Path) -> None:
    post = _make_post(likes=None, comments=None)
    # ...
    outcome = downloader.download(url="https://instagram.com/p/xyz/", destination_dir=str(tmp_path))
    assert outcome.like_count is None
    assert outcome.comment_count is None
```

Le code du setup (construction du downloader, mocking du client instaloader, tmp_path avec fichier media factice) doit **réutiliser** le pattern déjà présent dans les tests existants de la classe — ne pas inventer une infrastructure différente. Si un helper de setup (fixture, `_make_downloader`) existe, le réutiliser.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/instaloader/test_downloader.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_caption_populates_description\|test_engagement_stats_populated\|test_null_caption_gives_null_description\|test_none_likes_gives_none_engagement" tests/unit/adapters/instaloader/test_downloader.py` retourne 4 lignes
    - `grep -c "like_count\|comment_count" tests/unit/adapters/instaloader/test_downloader.py` retourne au moins 4
    - `grep -c "outcome.description" tests/unit/adapters/instaloader/test_downloader.py` retourne au moins 2
    - Les 4 nouveaux tests passent ; tous les tests existants du fichier passent toujours
  </acceptance_criteria>
  <done>
    Les 4 tests passent et couvrent description (avec/sans caption) et engagement (avec/sans valeurs).
  </done>
</task>

<task type="auto">
  <name>T09: Test — YtdlpDownloader._info_to_outcome engagement extraction</name>
  <files>tests/unit/adapters/ytdlp/test_downloader.py</files>
  <read_first>
    - tests/unit/adapters/ytdlp/test_downloader.py (tests existants pour _info_to_outcome, structure des fixtures info dict)
    - src/vidscope/adapters/ytdlp/downloader.py (signature exacte de _info_to_outcome — savoir ce qu'il faut passer en entrée)
  </read_first>
  <action>
Ajouter une nouvelle classe `TestInfoToOutcomeEngagement` en fin de fichier (ou étendre une classe existante si un pattern `TestInfoToOutcome*` existe déjà) :

```python
from vidscope.adapters.ytdlp.downloader import _info_to_outcome  # si pas déjà importé

class TestInfoToOutcomeEngagement:
    """R061 — yt-dlp info_dict engagement counters flow into IngestOutcome."""

    def _minimal_info(self, **overrides) -> dict:
        """Build the minimum info dict _info_to_outcome accepts.

        Reuse existing fixture/helper if one is defined at module level;
        otherwise extract the shape from an existing passing test in this file.
        """
        base = {
            "id": "abc123",
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "extractor_key": "Youtube",
            # ... autres champs required — copier depuis un test existant ...
        }
        base.update(overrides)
        return base

    def test_like_count_extracted_from_info(self) -> None:
        info = self._minimal_info(like_count=500, comment_count=30)
        outcome = _info_to_outcome(info, media_path="/tmp/x.mp4")  # adapter à la signature réelle
        assert outcome.like_count == 500
        assert outcome.comment_count == 30

    def test_missing_engagement_gives_none(self) -> None:
        info = self._minimal_info()  # pas de like_count ni comment_count
        outcome = _info_to_outcome(info, media_path="/tmp/x.mp4")
        assert outcome.like_count is None
        assert outcome.comment_count is None

    def test_null_engagement_gives_none(self) -> None:
        info = self._minimal_info(like_count=None, comment_count=None)
        outcome = _info_to_outcome(info, media_path="/tmp/x.mp4")
        assert outcome.like_count is None
        assert outcome.comment_count is None
```

**IMPORTANT** : la signature exacte de `_info_to_outcome` (arguments supplémentaires, ordre) doit être lue depuis le source — ne pas deviner. Si un helper `_make_info()` ou une fixture `yt_dlp_info_factory` existe déjà dans le fichier de test, le réutiliser au lieu de `_minimal_info` ci-dessus.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/ytdlp/test_downloader.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_like_count_extracted_from_info\|test_missing_engagement_gives_none" tests/unit/adapters/ytdlp/test_downloader.py` retourne au moins 2 lignes
    - `grep -c "like_count\|comment_count" tests/unit/adapters/ytdlp/test_downloader.py` retourne au moins 4
    - Les nouveaux tests passent ; aucun test existant du fichier n'est cassé
  </acceptance_criteria>
  <done>
    Les trois tests passent ; le flux info dict → IngestOutcome pour like_count/comment_count est verrouillé.
  </done>
</task>

<task type="auto">
  <name>T10: Test — IngestStage persists description + initial VideoStats</name>
  <files>tests/unit/pipeline/stages/test_ingest.py</files>
  <read_first>
    - tests/unit/pipeline/stages/test_ingest.py (FakeDownloader existant, pattern d'utilisation SqliteUoW, fixture tmp_path / engine)
    - src/vidscope/pipeline/stages/ingest.py (pour connaître les noms exacts dans le contexte: ctx.video_id, etc.)
  </read_first>
  <action>
Ajouter trois tests dans le fichier existant, en réutilisant le pattern FakeDownloader + real SqliteUoW déjà en place :

```python
def test_description_persisted_to_video(
    tmp_path: Path,
    # ... fixtures existantes (engine, uow_factory, etc.) ...
) -> None:
    """R060 — outcome.description lands in videos.description after ingest."""
    fake = FakeDownloader(
        outcome=IngestOutcome(
            platform=Platform.INSTAGRAM,
            platform_id=PlatformId("p_12345"),
            url="https://instagram.com/p/12345/",
            media_path=str(tmp_path / "media.mp4"),
            description="Post caption text avec accents éàù",
        ),
    )
    # ... setup stage + ctx + uow identique aux autres tests du fichier ...
    stage.execute(ctx, uow)
    video = uow.videos.get(ctx.video_id)
    assert video.description == "Post caption text avec accents éàù"


def test_initial_stats_created_from_engagement(
    tmp_path: Path,
    # ... fixtures ...
) -> None:
    """R061 — outcome.like_count/comment_count produce an initial video_stats row."""
    fake = FakeDownloader(
        outcome=IngestOutcome(
            platform=Platform.INSTAGRAM,
            platform_id=PlatformId("p_12345"),
            url="https://instagram.com/p/12345/",
            media_path=str(tmp_path / "media.mp4"),
            like_count=100,
            comment_count=5,
        ),
    )
    # ... setup ...
    stage.execute(ctx, uow)
    latest = uow.video_stats.latest_for_video(ctx.video_id)
    assert latest is not None
    assert latest.like_count == 100
    assert latest.comment_count == 5
    # captured_at est UTC-aware et tronqué à la seconde
    assert latest.captured_at.tzinfo is not None
    assert latest.captured_at.microsecond == 0


def test_no_stats_created_when_no_engagement(
    tmp_path: Path,
    # ... fixtures ...
) -> None:
    """When downloader surfaces no engagement, no video_stats row is written."""
    fake = FakeDownloader(
        outcome=IngestOutcome(
            platform=Platform.INSTAGRAM,
            platform_id=PlatformId("p_12345"),
            url="https://instagram.com/p/12345/",
            media_path=str(tmp_path / "media.mp4"),
            like_count=None,
            comment_count=None,
        ),
    )
    # ... setup ...
    stage.execute(ctx, uow)
    latest = uow.video_stats.latest_for_video(ctx.video_id)
    assert latest is None
```

**IMPORTANT** :
- Réutiliser exactement le même pattern (FakeDownloader constructor, instanciation stage, ctx, uow) que les tests existants du fichier — ne pas inventer une nouvelle infrastructure.
- Si `FakeDownloader` n'accepte pas un `outcome` paramétrable, l'étendre de manière rétro-compatible (ajout d'un kwarg avec default matching l'existant).
- Si `uow.video_stats.latest_for_video` n'a pas ce nom exact, vérifier la méthode réelle dans le repo VideoStats et l'utiliser (ex: `get_latest`, `latest_by_video_id`).
- Si le fichier media (tmp_path / "media.mp4") doit réellement exister pour que le stage ne lève pas (copie vers MediaStorage), créer un fichier vide comme les tests existants le font déjà.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/pipeline/stages/test_ingest.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_description_persisted_to_video\|test_initial_stats_created_from_engagement\|test_no_stats_created_when_no_engagement" tests/unit/pipeline/stages/test_ingest.py` retourne 3 lignes
    - Les 3 tests passent
    - Aucun test existant du fichier n'est cassé
  </acceptance_criteria>
  <done>
    Les 3 tests bout-en-bout passent : le stage écrit bien description sur videos ET une ligne video_stats initiale (conditionnelle).
  </done>
</task>

<task type="auto">
  <name>T11: Test — VideoRepository description round-trip</name>
  <files>tests/unit/adapters/sqlite/test_video_repository.py</files>
  <read_first>
    - tests/unit/adapters/sqlite/test_video_repository.py (fixture d'engine / uow / repo, pattern d'upsert+get)
  </read_first>
  <action>
Ajouter un test dans la classe existante (typiquement `TestVideoRepository` ou équivalent) :

```python
def test_description_round_trips(self, repo: VideoRepository) -> None:
    """R060 — videos.description persists via upsert + get."""
    video = Video(
        platform=Platform.INSTAGRAM,
        platform_id=PlatformId("p_99999"),
        url="https://instagram.com/p/99999/",
        description="Caption avec accents éàù",
        # ... autres champs required selon la signature de Video ...
    )
    saved = repo.upsert(video)
    reloaded = repo.get(saved.id)
    assert reloaded.description == "Caption avec accents éàù"

def test_null_description_persists_as_none(self, repo: VideoRepository) -> None:
    video = Video(
        platform=Platform.INSTAGRAM,
        platform_id=PlatformId("p_99998"),
        url="https://instagram.com/p/99998/",
        description=None,
        # ...
    )
    saved = repo.upsert(video)
    reloaded = repo.get(saved.id)
    assert reloaded.description is None
```

Réutiliser les fixtures / helpers déjà présents dans le fichier (engine in-memory, init_db, uow factory). Si un helper `_make_video()` existe, l'étendre pour supporter `description` plutôt que de construire Video à la main.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/sqlite/test_video_repository.py -x -v -k description</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_description_round_trips\|test_null_description_persists_as_none" tests/unit/adapters/sqlite/test_video_repository.py` retourne au moins 2 lignes
    - Les tests passent
    - Aucun test existant cassé
  </acceptance_criteria>
  <done>
    Le round-trip description est verrouillé par test ; confirmation que la colonne + le mapping repo fonctionnent ensemble.
  </done>
</task>

<task type="auto">
  <name>T12: Test — Schema migration idempotence + description column present</name>
  <files>tests/unit/adapters/sqlite/test_schema.py</files>
  <read_first>
    - tests/unit/adapters/sqlite/test_schema.py (tests existants pour _ensure_* autres migrations — pattern d'appel double init_db)
  </read_first>
  <action>
Ajouter un test :

```python
def test_ensure_description_column_idempotent(tmp_path: Path) -> None:
    """M012/S01 — description column added idempotently, second init_db is a no-op."""
    from sqlalchemy import create_engine, text

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    init_db(engine)
    init_db(engine)  # second call must not raise

    with engine.connect() as conn:
        cols = {row[1]: row[2] for row in conn.execute(text("PRAGMA table_info(videos)"))}
    assert "description" in cols
    assert cols["description"].upper() == "TEXT"
```

Si le pattern habituel dans `test_schema.py` utilise in-memory engine ou une fixture `engine`, adapter pour rester cohérent avec les autres tests. Le double appel à `init_db(engine)` est le cœur du test — il vérifie l'idempotence.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/sqlite/test_schema.py::test_ensure_description_column_idempotent -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_ensure_description_column_idempotent" tests/unit/adapters/sqlite/test_schema.py` retourne 1 ligne
    - `grep -c "description" tests/unit/adapters/sqlite/test_schema.py` retourne au moins 2 (dans le nom du test + dans l'assertion)
    - Le test passe
    - Aucun test existant cassé
  </acceptance_criteria>
  <done>
    L'idempotence de la migration M012/S01 est verrouillée par test.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Downloader (instaloader / yt-dlp) → IngestStage | Données externes (caption utilisateur, compteurs serveur) entrent dans le processus VidScope |
| IngestStage → SQLite (videos.description, video_stats) | Ces données sont persistées en clair |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-M012-01 | Tampering | `_ensure_description_column` DDL | mitigate | `_add_columns_if_missing` valide déjà le type DDL contre une allowlist `{"TEXT"}` (protection T-SQL-M011-02 existante). Aucun input utilisateur n'atteint la DDL. |
| T-M012-02 | Injection (SQL) | `videos.description` via caption Instagram | mitigate | SQLAlchemy Core `insert()` / `update()` utilise des paramètres liés (bind params) — la caption est traitée comme donnée, jamais comme SQL. Vérifié dans `_video_to_row` (retourne un dict, pas du SQL). |
| T-M012-03 | Information Disclosure | Caption contenant des données personnelles (emails, téléphones) | accept | Les captions sont déjà publiques (postées sur le réseau social). VidScope est un outil local mono-utilisateur. Pas de nouvelle surface d'exposition. Retrospective : valider ce point si VidScope évolue vers un mode multi-utilisateur / cloud. |
| T-M012-04 | Denial of Service | Caption extrêmement longue (1 MB+) bloquant l'ingest | accept | `description` est `TEXT` (SQLite limite à 1 GB par défaut) ; Instagram/yt-dlp plafonnent en amont (~2200 chars pour Instagram). Pas de troncature nécessaire pour R060. |
| T-M012-05 | Integrity | `video_stats.captured_at` collision si deux ingest rapprochés au même seconde | mitigate | `UNIQUE(video_id, captured_at)` existant + `ON CONFLICT DO NOTHING` dans l'adapter VideoStats (M009/D-01). Ingest ajoute UNE ligne par video → pas de collision intra-ingest. |
| T-M012-06 | Tampering | Un downloader tiers retourne des ints négatifs pour like_count | accept | SQLite accepte les INTEGER négatifs ; les tests (T07-T10) n'assertent pas de validation positive. Si exploité, la valeur s'affiche telle quelle via `vidscope show`. Pas de risque de sécurité, juste d'affichage. |
</threat_model>

<verification>

## Vérification globale de phase

```bash
# 1. Tests unitaires complets du périmètre touché
python -m pytest \
    tests/unit/ports/test_ingest_outcome.py \
    tests/unit/adapters/instaloader/test_downloader.py \
    tests/unit/adapters/ytdlp/test_downloader.py \
    tests/unit/adapters/sqlite/test_video_repository.py \
    tests/unit/adapters/sqlite/test_schema.py \
    tests/unit/pipeline/stages/test_ingest.py \
    -x -v

# 2. Non-régression sur l'ensemble de la suite unit
python -m pytest tests/unit -q

# 3. Vérification grep des ancrages (acceptance_criteria consolidées)
grep -n "_ensure_description_column" src/vidscope/adapters/sqlite/schema.py
grep -n "like_count: int | None = None\|comment_count: int | None = None" src/vidscope/ports/pipeline.py
grep -n '"description": video.description\|description=data.get' src/vidscope/adapters/sqlite/video_repository.py
grep -n "description=post.caption\|like_count=post.likes\|comment_count=post.comments" src/vidscope/adapters/instaloader/downloader.py
grep -n 'like_count=_int_or_none\|comment_count=_int_or_none' src/vidscope/adapters/ytdlp/downloader.py
grep -n "description=outcome.description\|uow.video_stats.append" src/vidscope/pipeline/stages/ingest.py

# 4. Vérification fumée sur une DB fraîche (description column présente)
python -c "
from sqlalchemy import create_engine, text
from vidscope.adapters.sqlite.schema import init_db
e = create_engine('sqlite:///:memory:')
init_db(e)
init_db(e)  # idempotent
with e.connect() as c:
    cols = {r[1]: r[2] for r in c.execute(text('PRAGMA table_info(videos)'))}
    assert 'description' in cols and cols['description'].upper() == 'TEXT'
    print('Schema OK — description:', cols['description'])
"
```

## Checklist must_haves (goal-backward)

- [ ] `IngestOutcome.like_count` et `IngestOutcome.comment_count` existent avec default `None`
- [ ] `videos.description` est une colonne TEXT nullable (PRAGMA table_info le confirme)
- [ ] `init_db` est idempotent (double appel ne lève pas)
- [ ] `InstaLoaderDownloader` renvoie description (caption complète) + likes + comments
- [ ] `YtdlpDownloader` renvoie like_count + comment_count depuis info dict
- [ ] `IngestStage.execute` persiste `description` sur videos et ajoute VideoStats initial si engagement présent
- [ ] `vidscope show <id>` affiche description et engagement sans `refresh-stats` (pas de modification de show.py — déjà câblé)
- [ ] Ingestion gracieuse quand caption/engagement absent (pas d'erreur, champs NULL)

</verification>

<success_criteria>

**R060 couvert** :
1. Après `vidscope add <instagram-carousel-url>`, `videos.description` contient la caption du post (non-null si le post a une caption). → T01+T03+T04+T06+T11
2. Ingestion sans caption disponible ne lève pas — `description` reste NULL gracieusement. → T04 (test null_caption) + T10 (test description None)

**R061 couvert** :
3. Après `vidscope add <url>`, `video_stats` contient une ligne avec `like_count` et/ou `comment_count` si la plateforme les fournit — sans exécuter `vidscope refresh-stats`. → T02+T05+T06+T10
4. Ingestion sans engagement disponible ne crée PAS de ligne video_stats parasite (graceful). → T10 (test_no_stats_created_when_no_engagement)

**Observabilité utilisateur** :
5. `vidscope show <id>` (déjà câblé) affiche description + stats pour un contenu fraîchement ingéré. → aucune modif show.py, couverture indirecte via T10 (ctx.video_id réellement peuplé).

**Robustesse** :
6. Double appel à `init_db` ne lève pas (migration idempotente). → T12
7. Round-trip `description` via VideoRepository (upsert → get). → T11
8. Aucune régression sur la suite `tests/unit`.

</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M012/M012-S01-SUMMARY.md` couvrant :
- Requirements R060 + R061 réalisés
- Fichiers modifiés (src + tests)
- Migration schéma ajoutée (colonne description)
- Résultats `pytest tests/unit`
- Toute surprise rencontrée (signature `_info_to_outcome`, structure FakeDownloader, etc.)
- Impact zéro sur `vidscope show` (déjà compatible)
</output>
