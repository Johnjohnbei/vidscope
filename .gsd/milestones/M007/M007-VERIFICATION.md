---
phase: M007-rich-content-metadata
verified: 2026-04-18T11:07:23Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
re_verification: null
gaps: []
deferred: []
human_verification: []
---

# Phase M007 : Vérification de l'objectif

**Objectif de la phase :** Rich content metadata — descriptions, liens, hashtags, mentions, musique. Promouvoir le payload yt-dlp (description, hashtags, mentions, musique, URLs brutes) en tables side first-class afin que l'utilisateur puisse interroger "tous les videos mentionnant @X", "tous les videos avec un lien dans la caption", "tous les videos utilisant le son Y". L'extraction de liens s'exécute aussi sur le transcript.
**Vérifié :** 2026-04-18T11:07:23Z
**Statut :** passed
**Re-vérification :** Non — vérification initiale

## Objectif atteint

### Vérités observables

| # | Vérité | Statut | Preuve |
|---|--------|--------|--------|
| 1 | Video possède les colonnes description, music_track, music_artist (R045) | VERIFIEE | `entities.py` lignes 83-85 : 3 champs `str \| None = None` ; `schema.py` : ALTER TABLE idempotent via `_ensure_videos_metadata_columns` |
| 2 | Tables SQLite hashtags/mentions/links avec FK CASCADE (R043, R044) | VERIFIEE | `schema.py` : 3 tables avec `ForeignKey("videos.id", ondelete="CASCADE")` + index dédiés |
| 3 | Ports HashtagRepository, MentionRepository, LinkRepository existent (R043, R044) | VERIFIEE | `ports/repositories.py` lignes 389, 431, 473 : 3 Protocols `@runtime_checkable` |
| 4 | RegexLinkExtractor dans `adapters/text/` avec corpus >= 100 entrées (R044) | VERIFIEE | Fichier présent ; corpus `link_corpus.json` : 51 positifs + 32 négatifs + 20 edge = 103 total |
| 5 | MetadataExtractStage existe et est câblé dans le container (R044) | VERIFIEE | Stage présent ; container.py instancie `RegexLinkExtractor()` + `MetadataExtractStage(link_extractor=...)` ; pipeline = 6 stages dans l'ordre canonique |
| 6 | IngestStage persiste hashtags et mentions (R043) | VERIFIEE | `ingest.py` : appels `uow.hashtags.replace_for_video` et `uow.mentions.replace_for_video` avec rebinding VideoId(0) → persisted.id |
| 7 | `vidscope search` accepte --hashtag, --mention, --has-link, --music-track (R046) | VERIFIEE | `cli/commands/search.py` : 4 options Typer présentes ; `search --help` confirme la présence des 4 flags |
| 8 | `vidscope links <id>` commande existe (R046) | VERIFIEE | `cli/commands/links.py` : `links_command` avec `ListLinksUseCase` ; enregistrée dans `app.py` |
| 9 | MCP tool `vidscope_list_links` enregistré (R046) | VERIFIEE | `mcp/server.py` ligne 345 : `def vidscope_list_links` ; `list_tools()` async confirme le tool dans les 8 tools enregistrés |
| 10 | 10 contrats import-linter verts (R044 qualité architecture) | VERIFIEE | `lint-imports` : `Contracts: 10 kept, 0 broken` — dont `text-adapter-is-self-contained` (10e contrat ajouté en S02-P02) |
| 11 | Suite de tests complète verte | VERIFIEE | `pytest -q` : **935 passed**, 5 deselected (5 pré-existants désactivés) |
| 12 | mypy propre | VERIFIEE | `mypy src` : `Success: no issues found in 99 source files` |

**Score :** 12/12 vérités vérifiées

### Artéfacts requis

| Artéfact | Attendu | Statut | Détails |
|----------|---------|--------|---------|
| `src/vidscope/domain/entities.py` | Video + 3 colonnes, Hashtag, Mention, Link frozen dataclasses | VERIFIEE | Lignes 83-85 (description/music), classes Hashtag (l.267), Mention (l.291), Link (l.317) |
| `src/vidscope/domain/values.py` | StageName.METADATA_EXTRACT | VERIFIEE | Ligne 95 : `METADATA_EXTRACT = "metadata_extract"` |
| `src/vidscope/adapters/sqlite/schema.py` | Tables hashtags, mentions, links + _ensure_videos_metadata_columns | VERIFIEE | Tables l.248, l.273, l.298 ; helper l.390 ; appelé dans init_db l.354 |
| `src/vidscope/adapters/sqlite/hashtag_repository.py` | HashtagRepositorySQLite avec canonicalisation | VERIFIEE | Fichier créé ; `_canonicalise_tag` + DELETE-INSERT idempotent |
| `src/vidscope/adapters/sqlite/mention_repository.py` | MentionRepositorySQLite avec canonicalisation | VERIFIEE | Fichier créé ; `_canonicalise_handle` + gestion platform optionnelle |
| `src/vidscope/adapters/sqlite/link_repository.py` | LinkRepositorySQLite avec dédup (normalized_url, source) | VERIFIEE | Fichier créé ; `add_many_for_video` avec in-memory dedup |
| `src/vidscope/ports/repositories.py` | HashtagRepository, MentionRepository, LinkRepository Protocols | VERIFIEE | 3 Protocols `@runtime_checkable` avec toutes les méthodes requises |
| `src/vidscope/ports/link_extractor.py` | LinkExtractor Protocol + RawLink TypedDict | VERIFIEE | Fichier créé ; Protocol `extract(text, *, source) -> list[RawLink]` |
| `src/vidscope/adapters/text/__init__.py` | Package adapters/text | VERIFIEE | Fichier présent ; exporte `RegexLinkExtractor` et `normalize_url` |
| `src/vidscope/adapters/text/url_normalizer.py` | normalize_url pure stdlib | VERIFIEE | Fichier présent ; 6 règles de normalisation idempotentes |
| `src/vidscope/adapters/text/regex_link_extractor.py` | RegexLinkExtractor deux passes + _COMMON_TLDS | VERIFIEE | `_COMMON_TLDS`, `_SCHEME_URL`, `_BARE_DOMAIN` présents |
| `tests/fixtures/link_corpus.json` | Corpus >= 100 strings (50+/30-/20 edge) | VERIFIEE | 103 entrées (51/32/20) — gate non-négociable satisfaite |
| `src/vidscope/pipeline/stages/metadata_extract.py` | MetadataExtractStage : is_satisfied + execute | VERIFIEE | Fichier créé ; `name = StageName.METADATA_EXTRACT.value` ; DI LinkExtractor |
| `src/vidscope/infrastructure/container.py` | Pipeline 6 stages dans l'ordre canonique | VERIFIEE | `stage_names = ('ingest', 'transcribe', 'frames', 'analyze', 'metadata_extract', 'index')` |
| `src/vidscope/pipeline/stages/ingest.py` | IngestStage persiste description/music + hashtags + mentions | VERIFIEE | `description=outcome.description` l.172 ; `uow.hashtags.replace_for_video` l.202 ; `uow.mentions.replace_for_video` l.215 |
| `src/vidscope/application/list_links.py` | ListLinksUseCase + ListLinksResult | VERIFIEE | Fichier créé ; `found` bool + filtre source optionnel |
| `src/vidscope/application/search_library.py` | SearchLibraryUseCase avec 4 facettes ET-implicite | VERIFIEE | Params `hashtag`, `mention`, `has_link`, `music_track` + intersection Python `set` |
| `src/vidscope/cli/commands/links.py` | `vidscope links <id>` avec Rich table | VERIFIEE | Fichier créé ; table Rich colonnes id/source/url/position |
| `src/vidscope/cli/commands/search.py` | `vidscope search` avec 4 flags | VERIFIEE | `--hashtag`, `--mention`, `--has-link`, `--music-track` présents |
| `src/vidscope/mcp/server.py` | `vidscope_list_links` tool | VERIFIEE | Enregistré via `@mcp.tool()` ; `list_tools()` confirme présence |
| `.importlinter` | 10 contrats dont text-adapter-is-self-contained | VERIFIEE | 10 contrats (`grep -c "\[importlinter:contract:"` = 10) |

### Vérification des liens clés (wiring)

| De | Vers | Via | Statut | Détails |
|----|------|-----|--------|---------|
| `IngestStage` | `uow.hashtags.replace_for_video` | UnitOfWork transaction | CÂBLE | Appel après `uow.videos.upsert_by_platform_id` dans même transaction |
| `IngestStage` | `uow.mentions.replace_for_video` | VideoId rebinding | CÂBLE | `rebound_mentions` remplace VideoId(0) → persisted.id avant écriture |
| `MetadataExtractStage` | `RegexLinkExtractor` | DI LinkExtractor | CÂBLE | `__init__(*, link_extractor: LinkExtractor)` ; container injecte `RegexLinkExtractor()` |
| `MetadataExtractStage` | `uow.links.add_many_for_video` | UnitOfWork | CÂBLE | Appelé toujours (même liste vide pour idempotence) |
| `SearchLibraryUseCase` | `uow.hashtags.find_video_ids_by_tag` | AND-implicite | CÂBLE | Intersection Python `set` sur `facet_sets` |
| `vidscope links` CLI | `ListLinksUseCase` | container.unit_of_work | CÂBLE | `links_command` → `acquire_container()` → `ListLinksUseCase` |
| `vidscope_list_links` MCP | `ListLinksUseCase` | container.unit_of_work | CÂBLE | Outil MCP délègue au même use case que la CLI |
| `adapters/text` | `domain` + `ports` uniquement | import-linter | CABLE (architecture) | Contrat `text-adapter-is-self-contained` : 0 violations |

### Trace de flux de données (Niveau 4)

| Artéfact | Variable de données | Source | Données réelles | Statut |
|----------|---------------------|--------|-----------------|--------|
| `Video.description` | `info.get("description")` | yt-dlp info_dict | yt-dlp payload réel | FLOWING |
| `hashtags` table | `info["tags"]` via `_extract_hashtags` | yt-dlp info_dict | Liste réelle de tags plateforme | FLOWING |
| `mentions` table | regex `_MENTION_PATTERN` sur description | yt-dlp info_dict | Handles extraits du texte | FLOWING |
| `links` table | `RegexLinkExtractor.extract()` sur description + transcript | DB (video.description, transcript.full_text) | URLs réelles extraites | FLOWING |
| `SearchLibraryUseCase` facettes | `find_video_ids_by_tag/handle/link` | SQLite queries indexées | Requêtes DB réelles sur tables side | FLOWING |

### Vérifications comportementales (Niveau 7b)

| Comportement | Commande | Résultat | Statut |
|-------------|---------|---------|--------|
| Corpus gate 100+ strings | `json.load("link_corpus.json")` — total=103 | positive=51, negative=32, edge=20 | PASSE |
| Pipeline 6 stages ordonnés | `build_container().pipeline_runner.stage_names` | `('ingest', 'transcribe', 'frames', 'analyze', 'metadata_extract', 'index')` | PASSE |
| CLI search --hashtag présent | `vidscope search --help` | `--hashtag` dans stdout | PASSE |
| CLI links command présent | `vidscope links --help` | exit 0 | PASSE |
| MCP tool enregistré | `server.list_tools()` async | `vidscope_list_links` dans la liste | PASSE |
| Suite de tests complète | `pytest -q` | 935 passed, 5 deselected | PASSE |
| mypy propre | `mypy src` | no issues in 99 files | PASSE |
| import-linter 10 contrats | `lint-imports` | 10 kept, 0 broken | PASSE |

### Couverture des exigences

| Exigence | Plan source | Description | Statut | Preuve |
|---------|-------------|-------------|--------|--------|
| R043 | S01-P01, S01-P02, S03-P01 | Hashtags et mentions comme tables side avec FK CASCADE | SATISFAITE | Tables `hashtags`/`mentions`, ports Protocols, IngestStage persiste via UoW |
| R044 | S02-P01, S02-P02, S03-P02 | Extraction de liens (description + transcript) avec corpus >= 100 | SATISFAITE | `RegexLinkExtractor`, `links` table, `MetadataExtractStage`, corpus 103 strings |
| R045 | S01-P01, S01-P02 | description, music_track, music_artist comme colonnes directes sur videos | SATISFAITE | `Video` dataclass étendue, `_ensure_videos_metadata_columns`, round-trip préservé |
| R046 | S04-P01, S04-P02 | `vidscope search` facettes + `vidscope links <id>` + MCP `vidscope_list_links` | SATISFAITE | CLI search avec 4 flags, commande links, MCP tool enregistré |

### Anti-patterns détectés

Aucun anti-pattern bloquant identifié. Quelques notes :

| Fichier | Ligne | Pattern | Sévérité | Impact |
|---------|-------|---------|----------|--------|
| `tests/unit/application/test_list_creator_videos.py` | 8 | F401 unused import `ListCreatorVideosResult` | Info | Pré-existant, hors scope M007 |
| `tests/unit/application/test_list_creators.py` | 114-116 | E501 lignes trop longues | Info | Pré-existant, hors scope M007 |

### Vérification humaine requise

Aucun — toutes les vérifications ont pu être effectuées programmatiquement.

### Résumé

M007 atteint son objectif : les 12 vérités observables sont confirmées dans le code réel. Les 4 requirements (R043-R046) sont satisfaits. La phase a livré :

- **S01** : Domain (Video+3 colonnes, Hashtag, Mention, StageName.METADATA_EXTRACT) + persistance SQLite (tables hashtags/mentions avec FK CASCADE, ports Protocols, adapters idempotents)
- **S02** : Link entity + LinkExtractor port + LinkRepository + `adapters/text` submodule (URLNormalizer + RegexLinkExtractor deux passes) + corpus 103 strings + 10e contrat import-linter
- **S03** : IngestStage étendu (description/music/hashtags/mentions) + nouveau MetadataExtractStage (extraction liens depuis description + transcript, resume-safe) + pipeline 6 stages
- **S04** : SearchLibraryUseCase avec 4 facettes AND-implicites + ListLinksUseCase + CLI `vidscope search --hashtag/--mention/--has-link/--music-track` + CLI `vidscope links <id>` + MCP `vidscope_list_links`

**935 tests passent**, mypy propre sur 99 fichiers, 10 contrats import-linter verts.

---

_Vérifié : 2026-04-18T11:07:23Z_
_Vérificateur : Claude (gsd-verifier)_
