---
plan_id: S03-P03
phase: M006/S03
plan: 03
subsystem: mcp
tags: [mcp-tool, creator, get-creator, e2e-harness, fastmcp]
dependency_graph:
  requires:
    - M006/S03-P01  # GetCreatorUseCase disponible
    - M006/S01-P03  # CreatorRepositorySQLite + UoW wiring
  provides:
    - vidscope_get_creator MCP tool
    - _creator_to_dict helper
    - scripts/verify-m006-s03.sh harness E2E
  affects:
    - src/vidscope/mcp/server.py
    - tests/unit/mcp/test_server_creator.py
    - tests/unit/mcp/test_server.py
tech_stack:
  added: []
  patterns:
    - MCP tool closure avec GetCreatorUseCase injection via container
    - _creator_to_dict DTO helper (11 champs JSON-serializable)
    - Platform validation explicite avant use case (ValueError from None)
    - Test via _tool_manager._tools[name].fn (FastMCP internal API)
    - E2E harness bash avec steps conditionnels (--skip-live, --skip-full-suite)
key_files:
  created:
    - tests/unit/mcp/test_server_creator.py
    - scripts/verify-m006-s03.sh
  modified:
    - src/vidscope/mcp/server.py
    - tests/unit/mcp/test_server.py
decisions:
  - "Platform validation avec raise ValueError from None (B904) avant le use case — message explicite au client MCP"
  - "Script verify-m006-s03.sh avec step 2 conditionnel (skip si S03-P02 absent) pour execution parallele"
  - "test_server_registers_six_tools -> seven_tools pour inclure vidscope_get_creator"
  - "Container sandbox via build_container() + monkeypatch VIDSCOPE_DATA_DIR (pattern miroir test_server.py)"
metrics:
  duration: "~20 min"
  completed: "2026-04-17"
  tasks: 3
  files_changed: 4
---

# Phase M006 Plan S03-P03 : MCP tool + E2E harness — Summary

**One-liner :** `vidscope_get_creator` MCP tool + `_creator_to_dict` helper ajoutés à `build_mcp_server`, 8 tests unitaires verts, harness `verify-m006-s03.sh` 8 étapes créé.

## Fichiers créés / modifiés

| Fichier | Action | Description |
|---------|--------|-------------|
| `src/vidscope/mcp/server.py` | modifié | Ajout imports `GetCreatorUseCase`, `Creator`, `Platform` + `_creator_to_dict` helper + `vidscope_get_creator` tool |
| `tests/unit/mcp/test_server_creator.py` | créé | 8 tests unitaires pour `vidscope_get_creator` |
| `tests/unit/mcp/test_server.py` | modifié | `test_server_registers_six_tools` → `seven_tools` (ajout `vidscope_get_creator`) |
| `scripts/verify-m006-s03.sh` | créé | Harness E2E 8 étapes pour M006/S03 |

## Shape finale du tool MCP

### vidscope_get_creator

```python
@mcp.tool()
def vidscope_get_creator(handle: str, platform: str = "youtube") -> dict[str, Any]:
    """Return the full profile of a creator identified by handle."""
    # Platform validation -> ValueError from None si invalide
    # GetCreatorUseCase.execute(plat, handle) -> GetCreatorResult
    # found=False -> {"found": False, "handle": handle, "platform": platform}
    # found=True  -> {"found": True, "creator": _creator_to_dict(result.creator)}
```

### _creator_to_dict (11 champs)

```python
{
    "id": int | None,
    "platform": str,           # creator.platform.value
    "platform_user_id": str,
    "handle": str | None,
    "display_name": str | None,
    "profile_url": str | None,
    "avatar_url": str | None,
    "follower_count": int | None,
    "is_verified": bool | None,
    "first_seen_at": str | None,  # ISO format
    "last_seen_at": str | None,   # ISO format
}
```

## Tests MCP creator (8 tests)

| Test | Vérifie |
|------|---------|
| `test_found_returns_creator_dict` | handle connu → `found=True`, dict avec handle + platform |
| `test_not_found_returns_found_false` | handle inconnu → `found=False`, handle préservé |
| `test_creator_dict_includes_follower_count` | follower_count présent dans le dict |
| `test_invalid_platform_raises_value_error` | platform invalide → `ValueError("unknown platform")` |
| `test_default_platform_is_youtube` | appel sans `platform` → youtube par défaut |
| `test_tiktok_platform` | `platform="tiktok"` → trouvé, dict platform=tiktok |
| `test_creator_dict_has_all_fields` | les 11 clés attendues sont présentes |
| `test_tool_registered_in_build_mcp_server` | `vidscope_get_creator` dans `_tool_manager._tools` |

## Harness verify-m006-s03.sh

8 étapes :
1. Fichiers clés S03 existent (application + mcp)
2. vidscope creator dans --help (skip si S03-P02 absent)
3. vidscope_get_creator dans server.py (grep)
4. Tests unitaires S03 : application + MCP (+ CLI si S03-P02 présent)
5. Suite complète pytest (skip avec --skip-full-suite)
6. 9 contrats import-linter verts
7. mypy vert sur src/
8. E2E live : vidscope add + creator list (skip avec --skip-live)

Résultat avec `--skip-live --skip-full-suite` : **5 PASS · 0 FAIL · 3 SKIP**

## Résultats de vérification

- `python -m uv run pytest tests/unit/mcp/test_server_creator.py -q` : **8 passed**
- `python -m uv run pytest -q` : **726 passed, 5 deselected** (aucune régression)
- `python -m uv run mypy src` : **Success: no issues found in 88 source files**
- `python -m uv run lint-imports` : **9 kept, 0 broken**
- `bash scripts/verify-m006-s03.sh --skip-live --skip-full-suite` : **exit 0**

## Commits atomiques

| Hash | Message |
|------|---------|
| `9ed8b92` | feat(M006/S03-P03): ajouter vidscope_get_creator tool + _creator_to_dict helper dans mcp/server.py |
| `e128ef6` | test(M006/S03-P03): 8 tests unitaires vidscope_get_creator + corrections B904 + test count |
| `bdf3e2d` | feat(M006/S03-P03): créer scripts/verify-m006-s03.sh — harness E2E 8 étapes |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Container frozen dataclass incompatible avec __new__ pour le fixture de test**
- **Trouvé pendant :** Task 2
- **Problème :** Le plan utilisait `Container.__new__(Container)` + assignation directe des champs, mais `Container` est `@dataclass(frozen=True, slots=True)` — TypeError au runtime
- **Fix :** Utilisation de `build_container()` avec `monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))` + `reset_config_cache()` — pattern identique à `test_server.py`
- **Fichiers modifiés :** `tests/unit/mcp/test_server_creator.py`
- **Commit :** `e128ef6`

**2. [Rule 1 - Bug] test_server_registers_six_tools échoue avec le nouveau tool**
- **Trouvé pendant :** Task 2
- **Problème :** Le test existant vérifiait exactement 6 tools — avec `vidscope_get_creator` ajouté, il en compte 7
- **Fix :** Renommer en `test_server_registers_seven_tools` + ajouter `vidscope_get_creator` dans le set attendu
- **Fichiers modifiés :** `tests/unit/mcp/test_server.py`
- **Commit :** `e128ef6`

**3. [Rule 1 - Bug] B904 ruff — raise ValueError sans from**
- **Trouvé pendant :** Task 2 (vérification ruff)
- **Problème :** Dans le bloc `except ValueError`, `raise ValueError(...)` sans `from None` viole B904
- **Fix :** `raise ValueError(...) from None` — distingue l'exception du contexte Platform
- **Fichiers modifiés :** `src/vidscope/mcp/server.py`
- **Commit :** `e128ef6`

**4. [Rule 1 - Bug] set -euo pipefail interagit avec ((PASS++)) quand PASS=0**
- **Trouvé pendant :** Task 3
- **Problème :** `((0))` retourne exit code 1 en bash — le script s'arrêtait après le premier PASS
- **Fix :** Remplacer `((PASS++))` / `((FAIL++))` / `((SKIP++))` par `PASS=$((PASS + 1))` etc.
- **Fichiers modifiés :** `scripts/verify-m006-s03.sh`
- **Commit :** `bdf3e2d`

## Handoff : M006/S03 — état des plans

| Plan | Statut | Ce qu'il livre |
|------|--------|----------------|
| S03-P01 | Complet | GetCreatorUseCase, ListCreatorsUseCase, ListCreatorVideosUseCase |
| S03-P02 | Parallèle (autre agent) | CLI `vidscope creator show/list/videos` |
| S03-P03 | **Complet** | MCP `vidscope_get_creator` + harness `verify-m006-s03.sh` |

Une fois S03-P02 fusionné, le harness `verify-m006-s03.sh` détectera automatiquement les tests CLI et la commande `vidscope creator` (step 2 et step 4 conditionnels).

## Known Stubs

Aucun stub — le tool `vidscope_get_creator` lit les données réelles depuis la DB SQLite via `GetCreatorUseCase` → `CreatorRepository.find_by_handle`.

## Threat Flags

Aucune nouvelle surface de sécurité non couverte par le `<threat_model>` du plan :
- T-S03P03-01 (SQLAlchemy paramétré) : respecté
- T-S03P03-02 (platform invalide) : mitigé via `ValueError from None`
- T-S03P03-03 (avatar_url public) : accepté

## Self-Check: PASSED

Fichiers créés :
- `tests/unit/mcp/test_server_creator.py` — FOUND
- `scripts/verify-m006-s03.sh` — FOUND

Fichiers modifiés :
- `src/vidscope/mcp/server.py` contient `vidscope_get_creator` — FOUND
- `tests/unit/mcp/test_server.py` contient `seven_tools` — FOUND

Commits vérifiés :
- `9ed8b92` — FOUND
- `e128ef6` — FOUND
- `bdf3e2d` — FOUND
