---
plan_id: S03-P03
phase: M006/S03
plan: 03
type: execute
wave: 2
depends_on: [S03-P01]
files_modified:
  - src/vidscope/mcp/server.py
  - scripts/verify-m006-s03.sh
autonomous: true
requirements: [R041]
must_haves:
  truths:
    - "vidscope_get_creator MCP tool retourne found/creator dict pour un handle valide"
    - "vidscope_get_creator retourne found=False sans lever d'exception quand le créateur est absent"
    - "vidscope_get_creator est enregistré dans build_mcp_server et visible dans mcp.tool list"
    - "9 contrats import-linter verts (mcp n'importe pas adapters)"
  artifacts:
    - path: "src/vidscope/mcp/server.py"
      provides: "vidscope_get_creator tool dans build_mcp_server"
      contains: "vidscope_get_creator"
    - path: "scripts/verify-m006-s03.sh"
      provides: "Harness E2E 8 étapes pour M006/S03"
      contains: "vidscope creator show"
  key_links:
    - from: "src/vidscope/mcp/server.py"
      to: "GetCreatorUseCase"
      via: "import + instantiation dans vidscope_get_creator closure"
      pattern: "GetCreatorUseCase"
---

<objective>
Livrer le MCP tool `vidscope_get_creator` et le harness de vérification E2E pour M006/S03.

**Ce plan consomme `GetCreatorUseCase` de S03-P01.** Il peut s'exécuter en parallèle avec S03-P02 car il ne touche pas la CLI.

Périmètre exact :
1. Ajouter `vidscope_get_creator(handle: str, platform: str = "youtube")` dans `mcp/server.py` via `build_mcp_server`
2. Créer `scripts/verify-m006-s03.sh` — harness 8 étapes vérifiant la slice complète
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M006/M006-ROADMAP.md
@.gsd/milestones/M006/slices/S03/S03-P01-SUMMARY.md
@src/vidscope/mcp/server.py
@src/vidscope/application/__init__.py
@tests/integration/test_mcp_server.py
@.importlinter

<interfaces>
<!-- Pattern MCP tool existant dans server.py — reproduire exactement -->

```python
@mcp.tool()
def vidscope_get_video(video_id: int) -> dict[str, Any]:
    """..."""
    try:
        use_case = SomeUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(...)
    except DomainError as exc:
        raise ValueError(str(exc)) from exc

    if not result.found:
        return {"found": False, ...}

    return {"found": True, ...}
```

Contrainte architecture (.importlinter) :
- `vidscope.mcp` NE DOIT PAS importer `vidscope.adapters` ni `vidscope.cli`
- Import légal : `vidscope.application`, `vidscope.domain`, `vidscope.infrastructure.container`

Creator dict shape (reprend Creator entity) :
```python
{
    "id": int | None,
    "platform": str,
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
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
<name>Task 1: Ajouter vidscope_get_creator dans mcp/server.py</name>

<read_first>
- `src/vidscope/mcp/server.py` lignes 1-95 — imports existants + `_video_to_dict` helper + début de `build_mcp_server`
- `src/vidscope/mcp/server.py` lignes 95-295 — pattern de chaque tool existant (closures, DomainError trap, dict return)
- `src/vidscope/mcp/server.py` lignes 44-55 — import de `vidscope.application` (ajouter `GetCreatorUseCase`)
- `src/vidscope/domain/__init__.py` — voir si `Creator` est exporté (pour `_creator_to_dict` helper)
- `src/vidscope/domain/entities.py` lignes 214-247 — Creator dataclass shape
</read_first>

<action>
**Fichier : `src/vidscope/mcp/server.py`**

**Modification 1 : Ajouter import de GetCreatorUseCase**

Dans le bloc import `from vidscope.application import (...)`, ajouter `GetCreatorUseCase` (ordre alphabétique) :
```python
from vidscope.application import (
    GetCreatorUseCase,
    GetStatusUseCase,
    IngestVideoUseCase,
    ListVideosUseCase,
    SearchLibraryUseCase,
    ShowVideoUseCase,
    SuggestRelatedUseCase,
)
```

**Modification 2 : Ajouter import de Creator et Platform**

Dans la ligne `from vidscope.domain import DomainError, Video, VideoId`, ajouter `Creator` et `Platform` :
```python
from vidscope.domain import Creator, DomainError, Platform, Video, VideoId
```

**Modification 3 : Ajouter `_creator_to_dict` helper**

Juste après la définition de `_video_to_dict` (avant `build_mcp_server`), ajouter :

```python
def _creator_to_dict(creator: Creator) -> dict[str, Any]:
    """Convert a Creator entity to a JSON-serializable dict."""
    return {
        "id": int(creator.id) if creator.id is not None else None,
        "platform": creator.platform.value,
        "platform_user_id": str(creator.platform_user_id),
        "handle": creator.handle,
        "display_name": creator.display_name,
        "profile_url": creator.profile_url,
        "avatar_url": creator.avatar_url,
        "follower_count": creator.follower_count,
        "is_verified": creator.is_verified,
        "first_seen_at": creator.first_seen_at.isoformat() if creator.first_seen_at else None,
        "last_seen_at": creator.last_seen_at.isoformat() if creator.last_seen_at else None,
    }
```

**Modification 4 : Ajouter `vidscope_get_creator` dans `build_mcp_server`**

À la fin de `build_mcp_server`, juste avant `_ = VideoId` et `return mcp`, ajouter :

```python
    @mcp.tool()
    def vidscope_get_creator(
        handle: str, platform: str = "youtube"
    ) -> dict[str, Any]:
        """Return the full profile of a creator identified by handle.

        ``handle`` is the human-facing @-name (e.g. ``"@alice"`` or
        ``"alice"`` — both work). ``platform`` is one of ``youtube``,
        ``tiktok``, or ``instagram`` (default: ``youtube``).

        Returns ``{"found": False, "handle": handle}`` when no creator
        matches — never raises on a miss.
        """
        try:
            plat = Platform(platform.lower())
        except ValueError:
            raise ValueError(
                f"unknown platform '{platform}'. Valid values: youtube, tiktok, instagram"
            )

        try:
            use_case = GetCreatorUseCase(
                unit_of_work_factory=container.unit_of_work
            )
            result = use_case.execute(plat, handle)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        if not result.found or result.creator is None:
            return {"found": False, "handle": handle, "platform": platform}

        return {
            "found": True,
            "creator": _creator_to_dict(result.creator),
        }
```

Aussi ajouter `Creator` à la ligne silencieux en bas :
```python
    _ = VideoId, Creator  # referenced in helpers, silence mypy unused warning
```
(Ou simplement supprimer le `_ = VideoId` existant et ne pas ajouter cette ligne — Creator est utilisé dans `_creator_to_dict` qui est appelé dans le tool.)
</action>

<verify>
  <automated>python -m uv run python -c "from vidscope.mcp.server import build_mcp_server; print('import ok')"</automated>
</verify>

<acceptance_criteria>
- `grep -q "vidscope_get_creator" src/vidscope/mcp/server.py` exit 0
- `grep -q "GetCreatorUseCase" src/vidscope/mcp/server.py` exit 0
- `grep -q "_creator_to_dict" src/vidscope/mcp/server.py` exit 0
- `grep -q "def _creator_to_dict" src/vidscope/mcp/server.py` exit 0
- `python -m uv run python -c "from vidscope.mcp.server import build_mcp_server; print('ok')"` sort `ok`
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0 (mcp ne doit pas importer adapters)
</acceptance_criteria>

<done>
`vidscope_get_creator` tool enregistré dans `build_mcp_server`. Import-linter vert.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 2: Tests unitaires pour vidscope_get_creator</name>

<read_first>
- `tests/integration/test_mcp_server.py` — pattern pour tester les tools MCP (comment `build_mcp_server` est appelé avec un container sandbox)
- `src/vidscope/mcp/server.py` (après Task 1) — `build_mcp_server` retourne un `FastMCP` — les tools sont des fonctions dans les closures
- `tests/unit/application/conftest.py` — `uow_factory` et pattern `Container` mockable
</read_first>

<action>
Créer `tests/unit/mcp/__init__.py` (vide) et `tests/unit/mcp/test_server_creator.py` :

**Fichier 1 : `tests/unit/mcp/__init__.py`** (nouveau) :
```python
"""Unit tests for the MCP server layer — creator tools."""
```

**Fichier 2 : `tests/unit/mcp/test_server_creator.py`** (nouveau fichier) :

```python
"""Unit tests for vidscope_get_creator MCP tool (M006/S03-P03)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.infrastructure.container import Container
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.mcp.server import build_mcp_server
from vidscope.ports import UnitOfWork


@pytest.fixture()
def container(tmp_path: Path) -> Container:
    engine = build_engine(tmp_path / "mcp_test.db")
    init_db(engine)

    def uow_factory() -> UnitOfWork:
        return SqliteUnitOfWork(engine)

    c = Container.__new__(Container)
    c._uow_factory = uow_factory  # type: ignore[attr-defined]
    c.unit_of_work = uow_factory  # type: ignore[attr-defined]
    return c


def _insert_creator(
    container: Container,
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_alice",
    follower_count: int | None = 42000,
) -> Creator:
    creator = Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        follower_count=follower_count,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with container.unit_of_work() as uow:
        return uow.creators.upsert(creator)


def _get_tool(container: Container, tool_name: str):
    """Extract a tool function from the FastMCP server instance."""
    mcp = build_mcp_server(container)
    # FastMCP stores tools in _tool_manager._tools dict keyed by name
    tools = mcp._tool_manager._tools
    assert tool_name in tools, f"Tool '{tool_name}' not found. Available: {list(tools.keys())}"
    return tools[tool_name].fn


class TestVidscopeGetCreatorTool:
    def test_found_returns_creator_dict(self, container: Container) -> None:
        _insert_creator(container, "@alice")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@alice", platform="youtube")

        assert result["found"] is True
        assert "creator" in result
        assert result["creator"]["handle"] == "@alice"
        assert result["creator"]["platform"] == "youtube"

    def test_not_found_returns_found_false(self, container: Container) -> None:
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@ghost", platform="youtube")

        assert result["found"] is False
        assert result["handle"] == "@ghost"

    def test_creator_dict_includes_follower_count(self, container: Container) -> None:
        _insert_creator(container, "@rich", follower_count=100000, platform_user_id="rich")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@rich", platform="youtube")

        assert result["found"] is True
        assert result["creator"]["follower_count"] == 100000

    def test_invalid_platform_raises_value_error(self, container: Container) -> None:
        tool_fn = _get_tool(container, "vidscope_get_creator")
        with pytest.raises(ValueError, match="unknown platform"):
            tool_fn(handle="@alice", platform="snapchat")

    def test_default_platform_is_youtube(self, container: Container) -> None:
        _insert_creator(container, "@yt", Platform.YOUTUBE, "yt")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        # Call without platform arg — defaults to youtube
        result = tool_fn(handle="@yt")
        assert result["found"] is True

    def test_tiktok_platform(self, container: Container) -> None:
        _insert_creator(container, "@tt", Platform.TIKTOK, "tt_uid")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@tt", platform="tiktok")
        assert result["found"] is True
        assert result["creator"]["platform"] == "tiktok"

    def test_creator_dict_has_all_fields(self, container: Container) -> None:
        _insert_creator(container, "@full", platform_user_id="full")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@full", platform="youtube")

        creator = result["creator"]
        expected_keys = {
            "id", "platform", "platform_user_id", "handle", "display_name",
            "profile_url", "avatar_url", "follower_count", "is_verified",
            "first_seen_at", "last_seen_at",
        }
        assert expected_keys.issubset(set(creator.keys()))

    def test_tool_registered_in_build_mcp_server(self, container: Container) -> None:
        mcp = build_mcp_server(container)
        tool_names = list(mcp._tool_manager._tools.keys())
        assert "vidscope_get_creator" in tool_names
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/mcp/test_server_creator.py -x -q</automated>
</verify>

<acceptance_criteria>
- `test -f tests/unit/mcp/__init__.py` exit 0
- `test -f tests/unit/mcp/test_server_creator.py` exit 0
- `python -m uv run pytest tests/unit/mcp/test_server_creator.py -x -q` exit 0 (8 tests verts)
- `python -m uv run pytest -q` exit 0 (suite complète sans régression)
- `python -m uv run mypy src` exit 0
- `python -m uv run ruff check src tests` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
8 tests MCP verts. `vidscope_get_creator` testé : found, not_found, invalid_platform, default_platform, all_fields.
</done>
</task>

<task type="auto" tdd="false">
<name>Task 3: Créer scripts/verify-m006-s03.sh — harness E2E 8 étapes</name>

<read_first>
- `scripts/verify-m006-s02.sh` — harness S02 à miroir (structure, étapes, couleurs)
- `src/vidscope/cli/app.py` — commandes disponibles dans `vidscope`
- `.gsd/milestones/M006/M006-ROADMAP.md` §"Done when" pour S03 — les conditions exactes
</read_first>

<action>
**Fichier : `scripts/verify-m006-s03.sh`** (nouveau fichier) :

```bash
#!/usr/bin/env bash
# verify-m006-s03.sh — harness E2E pour M006/S03 (CLI + MCP surfaces)
#
# Usage:
#   bash scripts/verify-m006-s03.sh               # full suite avec réseau
#   bash scripts/verify-m006-s03.sh --skip-live   # skip les étapes live network
#   bash scripts/verify-m006-s03.sh --skip-full-suite  # skip pytest suite complète
#
# Sortie : PASS / FAIL par étape + exit 0 si tout passe

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0; SKIP=0
SKIP_LIVE=false; SKIP_FULL_SUITE=false

for arg in "$@"; do
  case $arg in
    --skip-live)          SKIP_LIVE=true ;;
    --skip-full-suite)    SKIP_FULL_SUITE=true ;;
  esac
done

step() {
  local num="$1" label="$2"
  echo -e "${YELLOW}[${num}/${TOTAL_STEPS}]${NC} ${label}"
}

ok()   { echo -e "  ${GREEN}✓ PASS${NC}: $1"; ((PASS++)); }
fail() { echo -e "  ${RED}✗ FAIL${NC}: $1"; ((FAIL++)); }
skip() { echo -e "  ${YELLOW}○ SKIP${NC}: $1"; ((SKIP++)); }

TOTAL_STEPS=8

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " VERIFY M006/S03 — CLI + MCP surfaces"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# -------------------------------------------------------------------
# Step 1 : Fichiers clés livrés
# -------------------------------------------------------------------
step 1 "Fichiers clés S03 existent"
missing=()
for f in \
  "src/vidscope/cli/commands/creators.py" \
  "src/vidscope/application/get_creator.py" \
  "src/vidscope/application/list_creators.py" \
  "src/vidscope/application/list_creator_videos.py" \
  "src/vidscope/mcp/server.py"; do
  [ -f "$f" ] || missing+=("$f")
done
if [ ${#missing[@]} -eq 0 ]; then
  ok "Tous les fichiers cibles existent"
else
  fail "Fichiers manquants: ${missing[*]}"
fi

# -------------------------------------------------------------------
# Step 2 : creator_app enregistré dans la CLI
# -------------------------------------------------------------------
step 2 "vidscope creator apparaît dans --help"
if python -m uv run vidscope --help 2>&1 | grep -q "creator"; then
  ok "vidscope creator visible dans --help"
else
  fail "vidscope creator absent de --help"
fi

# -------------------------------------------------------------------
# Step 3 : vidscope_get_creator dans MCP server
# -------------------------------------------------------------------
step 3 "vidscope_get_creator enregistré dans MCP server"
if grep -q "vidscope_get_creator" src/vidscope/mcp/server.py; then
  ok "vidscope_get_creator trouvé dans server.py"
else
  fail "vidscope_get_creator manquant dans server.py"
fi

# -------------------------------------------------------------------
# Step 4 : Tests unitaires S03 verts
# -------------------------------------------------------------------
step 4 "Tests unitaires S03 verts"
if python -m uv run pytest tests/unit/application/test_get_creator.py \
     tests/unit/application/test_list_creators.py \
     tests/unit/application/test_list_creator_videos.py \
     tests/unit/cli/test_creators.py \
     tests/unit/mcp/test_server_creator.py \
     -x -q --tb=short 2>&1 | tail -3 | grep -q "passed"; then
  ok "Tests unitaires S03 verts"
else
  fail "Des tests unitaires S03 échouent — relancer avec -v pour détails"
fi

# -------------------------------------------------------------------
# Step 5 : Suite complète sans régression
# -------------------------------------------------------------------
step 5 "Suite complète pytest sans régression"
if [ "$SKIP_FULL_SUITE" = true ]; then
  skip "Skipped (--skip-full-suite)"
else
  if python -m uv run pytest -q --tb=short 2>&1 | tail -3 | grep -qE "passed|no tests"; then
    ok "Suite complète verte"
  else
    fail "Régression dans la suite complète — relancer avec -v pour détails"
  fi
fi

# -------------------------------------------------------------------
# Step 6 : Architecture contracts verts
# -------------------------------------------------------------------
step 6 "9 contrats import-linter verts"
if python -m uv run lint-imports 2>&1 | grep -q "Kept" && \
   ! python -m uv run lint-imports 2>&1 | grep -q "BROKEN"; then
  ok "import-linter : 9 contrats verts"
else
  fail "import-linter : contrats cassés"
fi

# -------------------------------------------------------------------
# Step 7 : mypy strict vert
# -------------------------------------------------------------------
step 7 "mypy strict vert sur src/"
if python -m uv run mypy src --strict 2>&1 | grep -q "Success"; then
  ok "mypy strict vert"
else
  fail "mypy strict échoue — voir erreurs ci-dessus"
fi

# -------------------------------------------------------------------
# Step 8 : E2E live (optionnel avec --skip-live)
# -------------------------------------------------------------------
step 8 "E2E live : vidscope add + creator show (réseau requis)"
if [ "$SKIP_LIVE" = true ]; then
  skip "Skipped (--skip-live)"
else
  LIVE_URL="https://www.youtube.com/shorts/dQw4w9WgXcW"
  TMPDB=$(mktemp -d)/test.db
  if python -m uv run vidscope add "$LIVE_URL" --db "$TMPDB" 2>&1 | grep -qiE "ok|success|created|ingested" && \
     python -m uv run vidscope creator list --db "$TMPDB" 2>&1 | grep -q "total creators"; then
    ok "E2E live : créateur peuplé après add"
  else
    fail "E2E live : vidscope add ou creator list échoue"
  fi
fi

# -------------------------------------------------------------------
# Résumé
# -------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e " Résultats : ${GREEN}${PASS} PASS${NC} · ${RED}${FAIL} FAIL${NC} · ${YELLOW}${SKIP} SKIP${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}✗ Vérification ÉCHOUÉE${NC}"
  exit 1
else
  echo -e "${GREEN}✓ Vérification PASSÉE${NC}"
  exit 0
fi
```

Rendre exécutable :
```bash
chmod +x scripts/verify-m006-s03.sh
```
</action>

<verify>
  <automated>bash scripts/verify-m006-s03.sh --skip-live --skip-full-suite</automated>
</verify>

<acceptance_criteria>
- `test -f scripts/verify-m006-s03.sh` exit 0
- `test -x scripts/verify-m006-s03.sh` exit 0
- `bash scripts/verify-m006-s03.sh --skip-live --skip-full-suite` exit 0 (6 étapes passent)
- `python -m uv run pytest -q` exit 0 (suite complète)
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
Harness E2E S03 créé et exécutable. 8 étapes couvrent fichiers, CLI, MCP, tests, architecture, mypy, E2E live.
</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MCP client → vidscope_get_creator | `handle` et `platform` viennent d'un agent IA externe |
| Tool → Use case | Isolation via DomainError → ValueError |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-S03P03-01 | **Tampering (T)** — handle MCP injecté dans SQL | `vidscope_get_creator(handle, platform)` → `find_by_handle` | LOW | accept | SQLAlchemy Core paramétrise toutes les valeurs. Aucune interpolation SQL. |
| T-S03P03-02 | **Tampering (T)** — `platform` MCP invalide | `Platform(platform.lower())` peut lever ValueError | LOW | mitigated | ValueError explicite levée avant le use case si `platform` n'est pas dans l'enum. Message "unknown platform '...' — valid: youtube, tiktok, instagram" affiché au client MCP. |
| T-S03P03-03 | **Information Disclosure** — `avatar_url` externe retourné | `_creator_to_dict` inclut `avatar_url` | INFO | accept | URL déjà publique (depuis yt-dlp). Pas de secret. Conforme à la politique M006 (pas de download image, juste URL string). |
</threat_model>

<verification>
```bash
# Tests MCP creator
python -m uv run pytest tests/unit/mcp/test_server_creator.py -x -q

# Non-régression globale
python -m uv run pytest -q

# Harness complet S03
bash scripts/verify-m006-s03.sh --skip-live

# Architecture
python -m uv run lint-imports

# Quality gates
python -m uv run ruff check src tests
python -m uv run mypy src
```
</verification>

<success_criteria>
- `vidscope_get_creator` tool dans `build_mcp_server` (server.py)
- `_creator_to_dict` helper avec tous les champs Creator
- 8 tests MCP unitaires verts
- `scripts/verify-m006-s03.sh` exécutable, exit 0 avec `--skip-live`
- Suite complète pytest verte
- 9 contrats import-linter verts (mcp n'importe pas adapters)
- mypy strict vert, ruff vert
</success_criteria>

<output>
À la fin du plan, créer `.gsd/milestones/M006/slices/S03/S03-P03-SUMMARY.md` résumant :
- `vidscope_get_creator` tool ajouté à `build_mcp_server`
- `_creator_to_dict` helper et ses champs
- Tests MCP unitaires : 8 tests verts
- Harness verify-m006-s03.sh créé
- Handoff : M006/S03 est complet — tous les critères "Done when" du M006-ROADMAP sont couverts
</output>
</content>
</invoke>
