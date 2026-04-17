# Phase M007: Rich content metadata — Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

M007 promeut les champs yt-dlp déjà disponibles (`description`, hashtags, mentions, musique, URLs) vers des tables de première classe interrogeables. Zéro nouvelle dépendance externe, zéro ML, zéro réseau supplémentaire à l'ingest.

**4 slices :**
- S01 : Domain + storage (nouvelles colonnes sur `Video` + side tables hashtags/mentions/links)
- S02 : LinkExtractor port + regex adapter + link persistence
- S03 : Pipeline wiring (IngestStage étendu + MetadataExtractStage nouveau)
- S04 : CLI facets + MCP tool `vidscope_list_links`

**Out of M007 :**
- HEAD-resolver pour URLs courtes → différé M008/M011
- Mention→Creator linkage → dérivable par JOIN en M011
- URL deduplication cross-videos → out of scope (roadmap explicit)
- Link-preview / OpenGraph → out of scope explicite

</domain>

<decisions>
## Implementation Decisions

### D-01 : Pas de VideoMetadata entity — description + musique sur Video directement
`VideoMetadata` dataclass et table séparée sont abandonnés. À la place, 3 colonnes ajoutées à `Video` entity et à la table `videos` :
- `description: str | None`
- `music_track: str | None`
- `music_artist: str | None`

Cohérent avec le pattern existant (`title`, `author`, `view_count` sur `Video`). Zéro JOIN pour `vidscope show`. Migration 004 ajoute ces 3 colonnes.

### D-02 : Short-URL resolver différé
Le HEAD-resolver pour t.co/bit.ly est différé à M008/M011. En M007 on stocke `url` (brute) + `normalized_url` uniquement. Pas de requête réseau supplémentaire à l'ingest.

### D-03 : Mention = handle brut + platform optionnelle, sans FK Creator
`Mention` entity stocke `handle: str` et `platform: Platform | None`. Pas de `creator_id` FK. La résolution Mention↔Creator est dérivable par JOIN au besoin (M011). Évite N DB lookups par ingest.

### D-04 : Facettes de recherche — AND implicite + exact match
- Multi-facettes combinées : **AND implicite** — chaque filtre affine le résultat (EXISTS subqueries)
- `--hashtag <tag>` : exact match après canonicalisation lowercase (`#Coding` = `#coding`)
- `--mention <handle>` : exact match sur `handle` normalisé (case-insensitive)
- `--has-link` : booléen — au moins un lien extrait pour la vidéo
- `--music-track <title>` : exact match sur `music_track` column (Claude's discretion sur LIKE)

### D-05 : Side tables conservées pour hashtags/mentions/links
Hashtags, mentions, et links restent en side tables avec FK `video_id` (même pattern que `creators` en M006). Ces entités peuvent apparaître plusieurs fois par vidéo.

### Claude's Discretion
- Placement de la migration (004 monolithique ou scindée)
- Implémentation interne de `normalized_url` (lowercase scheme+host, strip utm_*)
- `--music-track` : exact vs LIKE selon ce qui est le plus utile
- Nombre exact de tests par entité (≥8 est le seuil)
- Indexation de `description` dans FTS5 (probable mais à confirmer lors du planning)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap M007
- `.gsd/milestones/M007/M007-ROADMAP.md` — 4 slices, layer architecture, test strategy, exigence corpus regex

### Fondation domaine existante
- `src/vidscope/domain/entities.py` — `Video` dataclass (colonnes à étendre), `Creator` (patron à miroir)
- `src/vidscope/domain/values.py` — `Platform` et types de valeur
- `src/vidscope/ports/repositories.py` — protocols Repository existants (patron à miroir)
- `src/vidscope/adapters/sqlite/video_repository.py` — `_video_to_row` / `_row_to_video` à étendre
- `src/vidscope/adapters/sqlite/creator_repository.py` — patron side table (FK + upsert) à miroir

### Pipeline patterns
- `src/vidscope/pipeline/stages/ingest.py` — IngestStage à étendre (description + hashtags + mentions + music)
- `src/vidscope/pipeline/stages/transcribe.py` — TranscribeStage (MetadataExtractStage s'insère après)
- `src/vidscope/pipeline/runner.py` — comment enregistrer un nouveau stage

### Patterns CLI/MCP (M006/S03)
- `src/vidscope/cli/commands/list.py` — pattern filtre à miroir pour --hashtag/--mention
- `src/vidscope/mcp/server.py` — pattern tool closure + DomainError trap

### Architecture
- `.importlinter` — nouveau contrat `text-adapter-is-self-contained` requis pour S02 `adapters/text`

### Fixtures regex corpus (à créer en S02)
- `tests/fixtures/link_corpus.json` — ≥100 strings (50 positifs, 30 négatifs, 20 edge) — gate non-négociable

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Video` dataclass — étendre avec 3 nouvelles colonnes (description, music_track, music_artist)
- `src/vidscope/adapters/ytdlp/downloader.py` — `info_dict` déjà parsé pour Creator en M006/S02 ; même point d'accès pour description/hashtags/music
- `CreatorRepositorySQLite` — patron side table avec FK + upsert à copier pour hashtags/mentions/links
- `IngestStage` — déjà restructuré en M006/S02 pour injecter creator info — patron à suivre

### Established Patterns
- Frozen dataclass + `slots=True` pour chaque entité
- `_row_to_entity` / `_entity_to_row` helpers dans chaque SQLite adapter
- Migration numérotée (`003_creators.py` → `004_metadata.py`)
- `UnitOfWork` expose tous les repos — chaque nouveau side table repo doit y être ajouté
- Import-linter contrats stricts — `adapters/text` nouveau sous-module doit être self-contained

### Integration Points
- `IngestStage.execute()` — extraction description/hashtags/mentions/music depuis `info_dict`
- Après `TranscribeStage` — `MetadataExtractStage` nouveau lit transcript pour link extraction
- `SearchLibraryUseCase` — à étendre avec EXISTS subqueries pour les 4 facettes
- `vidscope show` (`ShowVideoUseCase`) — affiche automatiquement description/music (sur Video)
- `IndexStage` (FTS5) — description probablement à indexer (confirmer en planning)

</code_context>

<specifics>
## Specific Ideas

- `vidscope links <id>` est la commande phare de M007 — liste les URLs extraites de description + transcript avec leur source
- `vidscope search --hashtag cooking --mention @alice` → AND implicite, résultats affinés
- MCP tool `vidscope_list_links` expose les liens à un agent IA
- Corpus regex `tests/fixtures/link_corpus.json` est une gate non-négociable — failing regression = broken build
- La `source` column sur `links` distingue `description` vs `transcript` (et potentiellement `ocr` pour M008)

</specifics>

<deferred>
## Deferred Ideas

- **HEAD-resolver URLs courtes** (t.co, bit.ly) — différé M008/M011
- **Mention→Creator linkage** (creator_id FK) — dérivable par JOIN, différé M011
- **VideoMetadata entity** — abandonné au profit de colonnes directes sur Video
- **URL deduplication cross-videos** — out of scope (roadmap explicit)
- **Link-preview / OpenGraph** — out of scope explicite roadmap

</deferred>

---

*Phase: M007-rich-content-metadata*
*Context gathered: 2026-04-17*
