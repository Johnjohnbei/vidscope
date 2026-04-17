# Phase M006/S03: CLI + MCP surfaces — Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

S03 câble les use cases applicatifs sur les surfaces utilisateur finales (CLI Typer + MCP FastMCP). S01 a livré la fondation domaine (`Creator` entity, `CreatorRepository`, migration), S02 a peuplé les données à l'ingest. S03 expose ces données à travers :
- 3 commandes CLI (`vidscope creator show/list/videos`)
- Enrichissement inline de `vidscope show` et `vidscope list`
- 1 MCP tool (`vidscope_get_creator`)

**Aucune nouvelle donnée** n'est créée en S03 — S03 lit uniquement ce que S01+S02 ont écrit.

**Out of S03 :**
- Refresh périodique de follower_count → M009
- MCP `vidscope_list_creators` (peut être ajouté en S03 ou différé — décision Claude)
- Backfill de vidéos existantes sans creator_id → déjà livré en S01

</domain>

<decisions>
## Implementation Decisions

### D-01: 3 use cases applicatifs (couche application)
- `GetCreatorUseCase` : résout `(platform, handle)` → `Creator | None` via `CreatorRepository.find_by_handle`
- `ListCreatorsUseCase` : liste avec filtres optionnels `platform` + `min_followers`, retourne `(creators, total)`
- `ListCreatorVideosUseCase` : résout handle → creator, puis liste vidéos via `VideoRepository.list_by_creator`

### D-02: VideoRepository.list_by_creator
`list_by_creator(creator_id: CreatorId, *, limit: int = 50) -> list[Video]` ajouté au Protocol + adapter. Query : `WHERE creator_id = ? ORDER BY created_at DESC LIMIT ?`.

### D-03: Video.creator_id dans l'entity
`Video` dataclass reçoit `creator_id: CreatorId | None = None` (champ optionnel, défaut `None` — rétrocompat totale). Peuplé par `_row_to_video` depuis la colonne DB `videos.creator_id` (déjà présente depuis S01). Permet à `ShowVideoUseCase` de charger le créateur sans query supplémentaire.

### D-04: CLI creator sub-app — platform par défaut youtube
`vidscope creator show <handle>` sans `--platform` assume `youtube`. Convention identique à `vidscope watch add` pour la plateforme par défaut.

### D-05: MCP tool vidscope_get_creator — signature
`vidscope_get_creator(handle: str, platform: str = "youtube") -> dict`. Platform est un `str` (pas un enum) pour la compatibilité JSON-RPC MCP. Validé en début de tool avec `Platform(platform.lower())` → ValueError explicite si invalide.

### Claude's Discretion
- Stratégie dual-filter dans `ListCreatorsUseCase` (list_by_platform puis filter Python — acceptable car limit=200)
- Colonnes Rich Table dans `creator list` et `creator videos`
- Format Panel pour `creator show` (miroir de `vidscope show`)
- Nombre de tests par use case (≥ 8 est le seuil)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Fondation M006
- `src/vidscope/domain/entities.py` — `Creator` dataclass (platform, platform_user_id, handle, display_name, follower_count, is_verified, id)
- `src/vidscope/ports/repositories.py` — `CreatorRepository` Protocol (find_by_handle, list_by_platform, list_by_min_followers, count)
- `src/vidscope/adapters/sqlite/creator_repository.py` — `CreatorRepositorySQLite` (implémentation complète)

### Patterns applicatifs à miroir
- `src/vidscope/application/show_video.py` — pattern GetCreatorUseCase
- `src/vidscope/application/list_videos.py` — pattern ListCreatorsUseCase
- `src/vidscope/application/__init__.py` — comment exporter les use cases

### Patterns CLI à miroir
- `src/vidscope/cli/commands/show.py` — Panel.fit pour creator show
- `src/vidscope/cli/commands/list.py` — Table pour creator list/videos
- `src/vidscope/cli/_support.py` — helpers CLI (acquire_container, fail_user, handle_domain_errors)
- `src/vidscope/cli/app.py` — comment ajouter add_typer

### Patterns MCP à miroir
- `src/vidscope/mcp/server.py` — pattern tool closure + DomainError trap + _video_to_dict helper
- `tests/integration/test_mcp_server.py` — pattern test tool via build_mcp_server

### Architectural contracts
- `.importlinter` — cli/mcp ne peuvent pas importer adapters directement

</canonical_refs>

<specifics>
## Specific Ideas

- `vidscope creator list` sans filtre retourne les créateurs les plus récemment vus (last_seen_at desc)
- `vidscope creator show` affiche `first_seen_at` et `last_seen_at` pour le contexte temporel
- `vidscope creator videos` affiche le total (non paginé) et la page courante
- Le harness `verify-m006-s03.sh` doit exiger que `--skip-live` fonctionne en CI

</specifics>

<deferred>
## Deferred Ideas

- `vidscope_list_creators` MCP tool — différé car `vidscope_get_creator` suffit pour l'usage agent IA
- Refresh périodique follower_count — M009
- `vidscope creator stats <handle>` — M009 (engagement time-series)

</deferred>

---

*Phase: M006/S03*
*Context gathered: 2026-04-17*
