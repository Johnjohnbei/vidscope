# M007 Research — Rich content metadata

**Researched:** 2026-04-18
**Domain:** Metadata extraction, regex URL parsing, SQLite side tables, pipeline extension
**Confidence:** HIGH (codebase verified) / MEDIUM (yt-dlp field names) / HIGH (patterns)

---

## Summary

M007 promeut les champs yt-dlp deja disponibles — description, hashtags, mentions, musique, URLs — vers des tables SQLite de premiere classe interrogeables. Le codebase dispose deja de tous les patterns necessaires : side-table avec FK (M006 `creators`), port Protocol + adapter SQLite (pattern etabli), UnitOfWork extensible, PipelineRunner avec stage sequentiel, import-linter configurable.

La recherche confirme : (1) les cles yt-dlp exactes pour description/tags/music, (2) la strategie regex robuste pour eviter les faux positifs URL, (3) le pattern FTS5 existant est reutilisable tel quel pour indexer `description`, (4) les 4 nouveaux entites suivent exactement le patron `Creator`/`CreatorRepository`.

**Recommandation principale :** Copier fidelement le patron `creator_repository.py` pour chaque side table (hashtags, mentions, links). Pour l'extraction URL, utiliser un regex avec obligation de scheme OU TLD connu + port/chemin obligatoire pour distinguer les URLs des identifiants de fichiers.

---

<user_constraints>
## Decisions utilisateur verifiees (CONTEXT.md)

### Decisions verrouillees
- **D-01** : Pas de `VideoMetadata` entity — `description`, `music_track`, `music_artist` comme colonnes directes sur `Video` (et table `videos`). Migration 004 ajoute ces 3 colonnes.
- **D-02** : Short-URL resolver (t.co, bit.ly) differe a M008/M011. Stockage `url` brute + `normalized_url` uniquement en M007.
- **D-03** : `Mention` = `handle: str` + `platform: Platform | None`, sans FK `creator_id`. Resolution Mention-Creator differee M011.
- **D-04** : Facettes AND implicite + exact match. `--hashtag` = lowercase canonique. `--mention` = case-insensitive. `--has-link` = booleen. `--music-track` = exact match (LIKE au discretion).
- **D-05** : Side tables pour hashtags/mentions/links avec FK `video_id` (meme pattern que `creators` en M006).

### Discretion Claude
- Placement migration (004 monolithique ou scindee)
- Implementation interne `normalized_url` (lowercase scheme+host, strip utm_*)
- `--music-track` : exact vs LIKE
- Nombre exact de tests par entite (>= 8 est le seuil)
- Indexation de `description` dans FTS5 (probable, a confirmer)

### Idees differees (HORS SCOPE M007)
- HEAD-resolver URLs courtes
- Mention-Creator linkage (creator_id FK)
- VideoMetadata entity
- URL deduplication cross-videos
- Link-preview / OpenGraph
</user_constraints>

---

## Stack / Dependencies

### Aucune nouvelle dependance externe

M007 est zero-dep additionnel. Toutes les capacites necessaires sont deja dans l'environnement :

| Capacite | Disponible via | Statut |
|----------|----------------|--------|
| Extraction hashtags/mentions/description | `yt_dlp` (deja installe) | VERIFIED codebase |
| Regex URL | stdlib `re` + `urllib.parse` | VERIFIED - zero dep |
| SQLite side tables | SQLAlchemy Core (deja installe) | VERIFIED codebase |
| FTS5 `search_index` | schema existant | VERIFIED codebase |
| Pipeline stage | `Stage` Protocol existant | VERIFIED codebase |
| MCP tool | `FastMCP` deja installe | VERIFIED codebase |

[VERIFIED: codebase grep] Aucun `pip install` requis pour M007.

### Champs yt-dlp confirmes

| Besoin M007 | Cle info_dict yt-dlp | Disponibilite |
|-------------|----------------------|---------------|
| Description caption | `info["description"]` | TikTok/YT/IG - toujours present si plateforme l'expose |
| Hashtags | `info["tags"]` | Liste de strings (`["sweden", "cooking"]`) — VERIFIED docs yt-dlp common.py |
| Artiste musique | `info["artists"]` (liste, prefere) ou `info["artist"]` (depr.) | TikTok principalement |
| Titre musique (track) | `info["track"]` | TikTok principalement |
| Mentions (@handle) | **Absent** en tant que champ yt-dlp dedie — extraire depuis `description` par regex | [VERIFIED: TikTok extractor] |

[CITED: https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/common.py] Tags = list of strings. `artist` deprecie au profit de `artists` (liste). `track` = titre du morceau.

[ASSUMED] TikTok expose systematiquement `track` et `artists` quand la musique est identifiee. Instagram expose `track` rarement. YouTube pratiquement jamais sauf YouTube Music.

**Consequence pour le planner :**
- `hashtags` : `info.get("tags") or []` — liste de strings, pas de `#` prefixe dans yt-dlp
- `music_track` : `info.get("track")` — peut etre None
- `music_artist` : `_str_or_none(info.get("artists", [None])[0])` si liste, ou `info.get("artist")`
- `mentions` : extraire depuis `description` par regex `@[\w.]+`
- `description` : `info.get("description")`

---

## Architecture Patterns (codebase verifie)

### Pattern etabli : side table avec FK video_id

[VERIFIED: codebase] Le patron `CreatorRepositorySQLite` est le modele exact a reproduire pour `HashtagRepository`, `MentionRepository`, `LinkRepository`.

**Structure type (miroir de `creator_repository.py`) :**
```python
# src/vidscope/adapters/sqlite/hashtag_repository.py
class HashtagRepositorySQLite:
    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def add_for_video(self, video_id: VideoId, tags: list[str]) -> None:
        # DELETE existing then INSERT — idempotent sur re-ingest
        ...

    def list_for_video(self, video_id: VideoId) -> list[Hashtag]:
        ...

    def find_videos_by_hashtag(self, tag: str, *, limit: int = 50) -> list[VideoId]:
        # EXISTS subquery pour D-04 AND implicite
        ...
```

### Pattern UnitOfWork extension

[VERIFIED: `unit_of_work.py`] Ajouter un nouvel attribut dans `UnitOfWork` (port) et dans `SqliteUnitOfWork` (adapter) :

```python
# ports/unit_of_work.py — ajouter apres watch_refreshes:
hashtags: HashtagRepository
mentions: MentionRepository
links: LinkRepository

# adapters/sqlite/unit_of_work.py — dans __enter__:
self.hashtags = HashtagRepositorySQLite(self._connection)
self.mentions = MentionRepositorySQLite(self._connection)
self.links = LinkRepositorySQLite(self._connection)
```

### Pattern schema SQLAlchemy Core

[VERIFIED: `schema.py`] Les 4 nouvelles tables suivent exactement le pattern `creators` :

```python
# schema.py — nouvelles tables M007

# Colonnes directes sur videos (D-01) — via ALTER TABLE en schema.py:init_db
# description TEXT, music_track TEXT, music_artist TEXT

hashtags = Table(
    "hashtags", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    Column("tag", String(255), nullable=False),  # lowercase canonique, sans #
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)
Index("idx_hashtags_tag", hashtags.c.tag)
Index("idx_hashtags_video_id", hashtags.c.video_id)

mentions = Table(
    "mentions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    Column("handle", String(255), nullable=False),  # normalisé lowercase
    Column("platform", String(32), nullable=True),  # Platform | None (D-03)
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)

links = Table(
    "links", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    Column("url", Text, nullable=False),              # brute, verbatim
    Column("normalized_url", Text, nullable=False),   # lowercase scheme+host, strip utm_*
    Column("source", String(32), nullable=False),     # "description" | "transcript" | "ocr"
    Column("position_ms", Integer, nullable=True),    # pour transcript
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)
Index("idx_links_video_id", links.c.video_id)
```

### Pattern migration SQLAlchemy (ALTER TABLE)

[VERIFIED: `schema.py::_ensure_videos_creator_id`] Le patron etabli pour ajouter des colonnes sur une table existante est via `_ensure_*` helper dans `init_db` :

```python
def _ensure_videos_description_columns(conn: Connection) -> None:
    """Ajoute description/music_track/music_artist sur videos existants. Idempotent."""
    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
    if "description" not in cols:
        conn.execute(text("ALTER TABLE videos ADD COLUMN description TEXT"))
    if "music_track" not in cols:
        conn.execute(text("ALTER TABLE videos ADD COLUMN music_track TEXT"))
    if "music_artist" not in cols:
        conn.execute(text("ALTER TABLE videos ADD COLUMN music_artist TEXT"))
```

Appele dans `init_db()` apres `metadata.create_all(engine)`. Pas de fichier migration separe — le pattern existant est inline dans schema.py.

### Pattern nouveau stage pipeline

[VERIFIED: `runner.py`, `transcribe.py`] `MetadataExtractStage` suit le meme contrat que `TranscribeStage` :

```python
class MetadataExtractStage:
    name: str = StageName.METADATA_EXTRACT.value  # nouveau StageName a ajouter

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        # Verifier si des liens existent deja pour ce video
        if ctx.video_id is None:
            return False
        return uow.links.has_any_for_video(ctx.video_id)

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        # 1. Lire transcript depuis ctx.transcript_id (ou uow)
        # 2. Appeler LinkExtractor sur description + transcript.full_text
        # 3. Persister via uow.links.add_for_video(...)
        ...
```

**Ordre dans le pipeline :** `ingest → transcribe → frames → analyze → metadata_extract → index`
MetadataExtractStage APRES TranscribeStage (besoin du transcript). AVANT IndexStage (pour que description soit indexable si decision confirmee).

[ASSUMED] StageName enum devra recevoir un nouveau membre `METADATA_EXTRACT = "metadata_extract"`. Le runner resoudra ce nom via `_resolve_stage_phase` — verifier que la migration DB `pipeline_runs.phase` accepte des valeurs inconnues (TEXT column = ok en SQLite).

### Pattern import-linter pour adapters/text

[VERIFIED: `.importlinter`] Le nouveau sous-module `adapters/text` doit suivre le meme contrat que `adapters/llm`. Contrat a ajouter :

```ini
[importlinter:contract:text-adapter-is-self-contained]
name = text adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.text
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    vidscope.adapters.ytdlp
    vidscope.adapters.whisper
    vidscope.adapters.ffmpeg
    vidscope.adapters.heuristic
    vidscope.adapters.llm
    vidscope.infrastructure
    vidscope.application
    vidscope.pipeline
    vidscope.cli
    vidscope.mcp
```

Et dans les contrats existants (`sqlite-never-imports-fs`, etc.) ajouter `vidscope.adapters.text` comme module forbidden pour les autres adapters.

### Pattern MCP tool (vidscope_list_links)

[VERIFIED: `mcp/server.py`] Patron identique aux tools existants — closure capturant le container :

```python
@mcp.tool()
def vidscope_list_links(video_id: int, source: str | None = None) -> dict[str, Any]:
    """Liste les URLs extraites d'un video (description, transcript, ocr)."""
    try:
        use_case = ListLinksUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(video_id, source=source)
    except DomainError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "video_id": video_id,
        "links": [
            {"url": lk.url, "normalized_url": lk.normalized_url,
             "source": lk.source, "position_ms": lk.position_ms}
            for lk in result.links
        ]
    }
```

---

## Approche d'implementation par slice

### S01 : Domain + storage

**Entites a creer (frozen dataclass + slots=True) :**

```python
# entities.py — nouvelles entites
@dataclass(frozen=True, slots=True)
class Hashtag:
    video_id: VideoId
    tag: str  # lowercase, sans # prefixe
    id: int | None = None

@dataclass(frozen=True, slots=True)
class Mention:
    video_id: VideoId
    handle: str  # lowercase, sans @ prefixe
    platform: Platform | None = None  # D-03
    id: int | None = None

@dataclass(frozen=True, slots=True)
class MusicTrack:
    # NOTE : D-01 impose description/music_track/music_artist sur Video directement
    # MusicTrack entity NON requise — colonnes directes sur Video
    # Cette entite est SUPPRIMEE du plan per D-01
    pass
```

**Video entity — 3 nouvelles colonnes (D-01) :**
```python
@dataclass(frozen=True, slots=True)
class Video:
    # ... champs existants ...
    description: str | None = None    # NOUVEAU
    music_track: str | None = None    # NOUVEAU
    music_artist: str | None = None   # NOUVEAU
```

**video_repository.py — etendre `_video_to_row` / `_row_to_video` :**
```python
# _video_to_row : ajouter
"description": video.description,
"music_track": video.music_track,
"music_artist": video.music_artist,

# _row_to_video : ajouter
description=data.get("description"),
music_track=data.get("music_track"),
music_artist=data.get("music_artist"),
```

**Canonicalisation des hashtags :** `tag.lower().lstrip("#")` — conforme D-04 (`#Coding` == `#coding`).
**Canonicalisation des mentions :** `handle.lower().lstrip("@")`.

### S02 : LinkExtractor port + regex adapter

**Port (protocol) :**
```python
# ports/link_extractor.py
class LinkExtractor(Protocol):
    def extract(self, text: str, *, source: str) -> list[RawLink]:
        """Extrait les URLs brutes d'un texte. Retourne liste vide si aucune."""
        ...

class RawLink(TypedDict):
    url: str
    normalized_url: str
    source: str  # "description" | "transcript" | "ocr"
    position_ms: int | None
```

**Regex robuste pour URL extraction (R044) :**

Le defi principal est d'eviter les faux positifs comme `hello.world` (fichier.extension).

Strategie a deux niveaux :

1. **Niveau 1 - avec scheme :** Regex classique `https?://[^\s<>"{}|\\^`\[\]]+`
2. **Niveau 2 - sans scheme (bare domain) :** Require un TLD connu parmi une liste courte + sous-domaine ou chemin present

```python
# adapters/text/regex_link_extractor.py
import re
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

# Scheme explicite : facile, fiable
_SCHEME_URL = re.compile(
    r'https?://'                        # scheme obligatoire
    r'[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+'  # caracteres URL valides
)

# Bare domain : TLD connu + au moins un dot avant (domaine.tld)
# Liste restreinte pour eviter les faux positifs (pas de .ai, .io seuls sans chemin)
_COMMON_TLDS = r'(?:com|net|org|io|co|fr|uk|de|app|dev|ly|gg|tv|me)'
_BARE_DOMAIN = re.compile(
    r'(?<!\w)'                          # pas precede par un char alphanum
    r'(?:www\.)?'                       # www. optionnel
    r'[a-zA-Z0-9][a-zA-Z0-9\-]{1,61}'  # hostname
    r'\.' + _COMMON_TLDS +
    r'(?:/[^\s<>"\'\]`}|\\^{]*)?'      # chemin optionnel mais prefere
    r'(?=[\s,;)>\]\'"]|$)'             # suivi d'un separateur
)

def extract(self, text: str, *, source: str) -> list[RawLink]:
    results = []
    seen_normalized: set[str] = set()
    for m in _SCHEME_URL.finditer(text):
        url = m.group(0).rstrip(".,;:!?)")  # strip ponctuation finale
        norm = normalize_url(url)
        if norm not in seen_normalized:
            seen_normalized.add(norm)
            results.append(RawLink(url=url, normalized_url=norm, source=source, position_ms=None))
    # Bare domains seulement si pas de scheme deja capture
    for m in _BARE_DOMAIN.finditer(text):
        candidate = "https://" + m.group(0)
        norm = normalize_url(candidate)
        if norm not in seen_normalized:
            seen_normalized.add(norm)
            results.append(RawLink(url=m.group(0), normalized_url=norm, source=source, position_ms=None))
    return results
```

**URL normalizer :**
```python
# adapters/text/url_normalizer.py
def normalize_url(url: str) -> str:
    """Normalise une URL pour deduplication : lowercase scheme+host,
    strip utm_*, strip fragment, trie query params alphabetiquement."""
    parsed = urlparse(url.lower() if not url.startswith("http") else url)
    # Lowercase scheme + host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    # Strip fragment
    # Filter utm_* params + trier les restants
    qs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = sorted((k, v) for k, v in qs if not k.lower().startswith("utm_"))
    normalized = urlunparse((
        scheme, netloc, parsed.path,
        parsed.params, urlencode(filtered), ""  # fragment = ""
    ))
    return normalized.rstrip("/")  # strip trailing slash
```

**Corpus `tests/fixtures/link_corpus.json` — structure attendue :**
```json
{
  "positive": [
    {"text": "Visitez https://example.com", "expected_urls": ["https://example.com"]},
    {"text": "Link: bit.ly/abc123", "expected_urls": ["https://bit.ly/abc123"]},
    {"text": "go to www.shop.com/product?utm_source=tiktok&id=1", "expected_urls": ["https://www.shop.com/product?id=1"]},
    ...  // 50 cas positifs
  ],
  "negative": [
    {"text": "hello.world is not a URL", "expected_urls": []},
    {"text": "version 1.0.0", "expected_urls": []},
    {"text": "file.txt", "expected_urls": []},
    ...  // 30 cas negatifs
  ],
  "edge": [
    {"text": "IDN: https://xn--nxasmq6b.com", "expected_urls": ["https://xn--nxasmq6b.com"]},
    {"text": "URL entre parentheses (https://example.com)", "expected_urls": ["https://example.com"]},
    {"text": "Markdown [link](https://example.com)", "expected_urls": ["https://example.com"]},
    ...  // 20 cas limites
  ]
}
```

### S03 : Pipeline wiring

**IngestStage — extension (sans casser les callers existants) :**

La decision D-01 met description/music_track/music_artist sur Video directement. `IngestStage.execute()` doit donc :

```python
# Dans _info_to_outcome ou directement dans IngestStage.execute :
video = Video(
    platform=outcome.platform,
    # ... champs existants ...
    description=outcome.description,       # NOUVEAU
    music_track=outcome.music_track,       # NOUVEAU
    music_artist=outcome.music_artist,     # NOUVEAU
)
```

Et dans `ytdlp/downloader.py::_info_to_outcome` ajouter :
```python
return IngestOutcome(
    # ... champs existants ...
    description=_str_or_none(info.get("description")),
    hashtags=[str(t).lower() for t in (info.get("tags") or [])],
    mentions=_extract_mentions(info.get("description") or ""),
    music_track=_str_or_none(info.get("track")),
    music_artist=_str_or_none(
        (info.get("artists") or [None])[0]  # premier artiste si liste
        or info.get("artist")
    ),
)
```

Et `IngestOutcome` (port) s'etend avec ces champs optionnels.

**Hashtags/mentions persistance dans IngestStage :**
```python
# Apres uow.videos.upsert_by_platform_id(video, creator=creator):
if outcome.hashtags:
    uow.hashtags.replace_for_video(persisted.id, outcome.hashtags)
if outcome.mentions:
    uow.mentions.replace_for_video(persisted.id, outcome.mentions)
```

**MetadataExtractStage — nouveau stage :**

- Position : apres TranscribeStage dans le pipeline
- `is_satisfied` : `uow.links.has_any_for_video(ctx.video_id)` — resume-safe
- `execute` :
  1. Lire description depuis `uow.videos.get(ctx.video_id).description`
  2. Lire transcript depuis `uow.transcripts.get_for_video(ctx.video_id)`
  3. Appeler `link_extractor.extract(description, source="description")`
  4. Appeler `link_extractor.extract(transcript.full_text, source="transcript")` avec `position_ms` si possible (approximation : None pour l'instant)
  5. Persister via `uow.links.add_many_for_video(ctx.video_id, links)`

**StageName — nouveau membre :**
```python
# values.py
class StageName(StrEnum):
    INGEST = "ingest"
    TRANSCRIBE = "transcribe"
    FRAMES = "frames"
    ANALYZE = "analyze"
    METADATA_EXTRACT = "metadata_extract"  # NOUVEAU
    INDEX = "index"
```

**runner.py / container.py — enregistrement :**
```python
# container.py — construire et inserer MetadataExtractStage
link_extractor = RegexLinkExtractor()
metadata_extract_stage = MetadataExtractStage(link_extractor=link_extractor)

pipeline_runner = PipelineRunner(
    stages=[
        ingest_stage,
        transcribe_stage,
        frames_stage,
        analyze_stage,
        metadata_extract_stage,   # NOUVEAU — apres analyze, avant index
        index_stage,
    ],
    ...
)
```

**FTS5 description indexing :** La table `search_index` existante peut indexer description en ajoutant une row avec `source='description'` depuis `IndexStage` ou `MetadataExtractStage`. Decision a confirmer en planning — recommandation : dans `IndexStage` pour coherence (toutes les indexations au meme endroit).

### S04 : CLI facets + MCP tool

**`vidscope search` — nouveaux flags (pattern de `list.py`) :**
```python
# cli/commands/search.py (ou main.py selon structure)
--hashtag: str | None  # ex: --hashtag cooking
--mention: str | None  # ex: --mention @alice
--has-link: bool       # flag, default False
--music-track: str | None
```

**`vidscope links <id>` — nouvelle commande :**
```python
# cli/commands/links.py
def links_command(video_id: int) -> None:
    """Liste les URLs extraites d'un video."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = ListLinksUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(video_id)
        # Rich table : url | source | position_ms
        ...
```

**SearchLibraryUseCase — extension avec facettes EXISTS subqueries :**
```sql
-- Pour --hashtag cooking :
SELECT v.* FROM videos v
WHERE EXISTS (SELECT 1 FROM hashtags h WHERE h.video_id = v.id AND h.tag = 'cooking')
-- AND avec autres facettes

-- Pour --has-link :
WHERE EXISTS (SELECT 1 FROM links l WHERE l.video_id = v.id)
```

---

## Risks cles / Questions ouvertes

### Risk 1 : StageName enum — pipeline_runs.phase column

[VERIFIED: schema.py] La colonne `pipeline_runs.phase` est `String(32)`. SQLite n'a pas de ENUM native — la valeur est stockee comme string. Ajouter `METADATA_EXTRACT = "metadata_extract"` dans `StageName` ne cassera PAS les anciens enregistrements. Mais `_resolve_stage_phase()` dans `runner.py` leve `StageCrashError` si le nom n'est pas dans l'enum. [ASSUMED] Il faudra donc ajouter `METADATA_EXTRACT` au StageName AVANT de wirer le stage.

**Resolution :** Ajouter `StageName.METADATA_EXTRACT` dans S01 (domain layer) afin que S03 puisse l'utiliser sans conflit.

### Risk 2 : IngestOutcome — frozen dataclass

[VERIFIED: `pipeline.py`] `IngestOutcome` est un `@dataclass(frozen=True, slots=True)`. L'ajouter des champs `description`, `hashtags`, `mentions`, `music_track`, `music_artist` avec des defaults (`= None` ou `= field(default_factory=list)`) est backward-compatible. Les tests existants qui construisent `IngestOutcome(...)` avec positional args pourraient casser si l'ordre change. Utiliser des kwargs uniquement dans les tests.

### Risk 3 : UnitOfWork Protocol — nouveaux attributs

[VERIFIED: `unit_of_work.py`] Ajouter `hashtags: HashtagRepository`, `mentions: MentionRepository`, `links: LinkRepository` au Protocol `UnitOfWork` rompt le structural typing pour tous les InMemory UoW utilises dans les tests existants. Il faudra les etendre egalement.

**Resolution :** Creer des InMemory repos minimalistes pour les tests (pattern etabli — voir `tests/unit/` qui utilisent probablement des stubs). Verifier systematiquement les fichiers de test qui creent des UoW.

### Risk 4 : Regex URL — faux positifs et faux negatifs

[ASSUMED] La liste de TLDs restreinte (_COMMON_TLDS) peut manquer des URLs legitimes avec des TLDs moins courants (.ai, .io, .gg, .app, .dev). Pour M007, privilegier la precision sur le rappel : mieux vaut manquer une URL que stocker des faux positifs. Les edge cases seront documented dans `link_corpus.json`.

**Resolution :** Le corpus de ≥ 100 fixtures est la gate qualite non-negociable (ROADMAP).

### Risk 5 : Position transcript pour liens

[ASSUMED] `MetadataExtractStage` devrait idealement tracker la position en ms des URLs dans le transcript (pour `links.position_ms`). Les segments `TranscriptSegment` ont `start`/`end` en secondes. Trouver l'URL dans quel segment est possible mais ajoute de la complexite. Option simple : `position_ms = None` pour les liens du transcript en M007, avec un `position_ms` approximatif base sur la recherche dans `segments`.

### Q-01 : Monolithique vs scindee pour la migration

La migration 004 (colonnes description/music/hashtags/mentions schema) + 005 (links) peut etre soit une seule migration monolithique, soit deux migrations numerotees. Recommandation : deux — car S01 et S02 sont des slices separees et la separation facilite les rollbacks.

### Q-02 : FTS5 indexation de description

[ASSUMED] Indexer `description` dans FTS5 depuis `IndexStage` (source='description') est la recommandation par coherence. Cela permettra `vidscope search "cooking"` de trouver des videos dont la description contient "cooking" meme si le transcript ne le dit pas. Confirmer lors du planning S03/S04.

### Q-03 : music_artist — premier artiste ou concatene

[ASSUMED] TikTok peut exposer plusieurs artistes dans `info["artists"]` (liste). Pour M007, stocker le premier artiste uniquement dans `music_artist`. Concatenation multi-artiste differee.

---

## Validation Architecture (test strategy par slice)

### Framework existant

[VERIFIED: codebase]
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config | `pyproject.toml` ou `setup.cfg` (non verifie) |
| Quick run | `pytest tests/unit/ -x -q` |
| Full suite | `pytest tests/ -x -q` |
| Architecture | `lint-imports` (`.importlinter`) |

### S01 — tests cibles

| Behaviour | Type | Fichier |
|-----------|------|---------|
| `Video` dataclass avec 3 nouvelles colonnes | unit/domain | `test_entities.py` |
| `Hashtag` canonicalisation lowercase (#Coding → coding) | unit/domain | `test_entities.py` |
| `Mention` handle normalisation | unit/domain | `test_entities.py` |
| `HashtagRepositorySQLite` CRUD + cascade delete | unit/adapter | `test_hashtag_repository.py` |
| `MentionRepositorySQLite` CRUD | unit/adapter | `test_mention_repository.py` |
| `VideoRepositorySQLite` round-trip avec nouveaux champs | unit/adapter | `test_video_repository.py` (etendre) |
| Schema — ALTER TABLE idempotent | unit/adapter | `test_schema.py` (etendre) |
| UnitOfWork expose nouveaux repos | unit/adapter | `test_unit_of_work.py` (etendre) |
| Import-linter contracts (9 → 10 avec text-adapter) | architecture | `test_architecture.py` |

### S02 — tests cibles

| Behaviour | Type | Fichier |
|-----------|------|---------|
| Corpus 100+ strings (50 pos / 30 neg / 20 edge) | unit/adapter | `test_regex_link_extractor.py` |
| URL normalizer — strip utm_*, lowercase, sort params | unit/adapter | `test_url_normalizer.py` |
| Fixture `link_corpus.json` existe et est valide | unit/adapter | meme fichier |
| `LinkRepositorySQLite` CRUD + source filter | unit/adapter | `test_link_repository.py` |
| `normalize_url` idempotence | unit/adapter | `test_url_normalizer.py` |

### S03 — tests cibles

| Behaviour | Type | Fichier |
|-----------|------|---------|
| `IngestStage` persiste description + hashtags + music | integration | `test_ingest_stage.py` |
| `MetadataExtractStage.is_satisfied` retourne True si liens existent | unit/pipeline | `test_metadata_extract_stage.py` |
| `MetadataExtractStage.execute` persiste liens depuis description + transcript | unit/pipeline | `test_metadata_extract_stage.py` |
| Pipeline complet — nouveau stage dans la sequence | integration | `test_pipeline_integration.py` |

### S04 — tests cibles

| Behaviour | Type | Fichier |
|-----------|------|---------|
| `vidscope search --hashtag foo` retourne videos correspondantes | unit/app + CLI | `test_search_library_use_case.py`, `test_search_cmd.py` |
| `vidscope links <id>` affiche URLs extraites | CLI snapshot | `test_links_cmd.py` |
| MCP `vidscope_list_links` retourne shape attendu | unit/mcp | `test_mcp_server.py` |
| Combinaison facettes AND implicite | unit/app | `test_search_library_use_case.py` |

### Seuil qualite minimum par slice

- **S01 :** >= 8 tests par nouveau repo (CONTEXT.md) + 3 tests domain
- **S02 :** corpus >= 100 strings — **gate non-negociable** (ROADMAP)
- **S03 :** tests integration pipeline avec double stub (Downloader + LinkExtractor)
- **S04 :** CLI snapshot + 1 test MCP subprocess

---

## Sources

### PRIMARY (HIGH confidence)
- Codebase verifie : `src/vidscope/adapters/sqlite/` — tous les patterns SQLAlchemy Core
- Codebase verifie : `src/vidscope/pipeline/` — Stage Protocol, PipelineRunner
- Codebase verifie : `src/vidscope/mcp/server.py` — tool closure pattern
- Codebase verifie : `.importlinter` — contrats existants
- [CITED: yt-dlp common.py docs] `tags` = list[str], `track` = str, `artists` = list[str]

### SECONDARY (MEDIUM confidence)
- [WebFetch: github.com/yt-dlp/yt-dlp extractor/tiktok.py] — `track`, `artists` confirmes TikTok
- [WebFetch: github.com/yt-dlp/yt-dlp extractor/common.py] — schema standard info_dict
- [WebSearch: SQLite FTS5 unicode61] — tokeniseur existant compatible description

### TERTIARY (LOW confidence / ASSUMED)
- Disponibilite de `track`/`artists` sur Instagram et YouTube (variable selon plateforme)
- Liste de TLDs optimale pour regex URL (a valider avec corpus)
- Comportement du `StageName` enum avec valeurs inconnues dans pipeline_runs existants

---

## Assumptions Log

| # | Claim | Section | Risque si faux |
|---|-------|---------|----------------|
| A1 | TikTok expose systematiquement `track` et `artists` en info_dict | Stack/Dependencies | music_track/music_artist NULL pour TikTok — pas critique (nullable) |
| A2 | `StageName.METADATA_EXTRACT` peut etre ajoute sans casser pipeline_runs historiques | Risk 1 | Crash runner sur videos anciennement traitees — tester sur DB existante |
| A3 | Les tests existants construisent `IngestOutcome` via kwargs (pas positional) | Risk 2 | Casse de tests — verifier avant implementation |
| A4 | Description doit etre indexee dans FTS5 | Q-02 | Gap de recall si non indexe — confirmer en planning |
| A5 | La liste de TLDs restreinte couvre 95%+ des URLs dans captions short-form | Risk 4 | Faux negatifs sur domaines avec TLDs rares — corpus revelera les gaps |

---

## RESEARCH COMPLETE
