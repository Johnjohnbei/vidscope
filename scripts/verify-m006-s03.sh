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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' BOLD='' NC=''
fi

PASS=0; FAIL=0; SKIP=0
SKIP_LIVE=false; SKIP_FULL_SUITE=false

for arg in "$@"; do
  case $arg in
    --skip-live)          SKIP_LIVE=true ;;
    --skip-full-suite)    SKIP_FULL_SUITE=true ;;
    -h|--help)
        sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
  esac
done

TOTAL_STEPS=8
_step=0

step() {
  _step=$((_step + 1))
  echo -e "\n${CYAN}${BOLD}[${_step}/${TOTAL_STEPS}]${NC} $1"
}

ok()   { echo -e "  ${GREEN}✓ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}✗ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
skip() { echo -e "  ${YELLOW}○ SKIP${NC}: $1"; SKIP=$((SKIP + 1)); }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " VERIFY M006/S03 — CLI + MCP surfaces"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Repo: ${REPO_ROOT}"

# -------------------------------------------------------------------
# Step 1 : Fichiers clés livrés
# -------------------------------------------------------------------
step "Fichiers clés S03 existent"
missing=()
for f in \
  "src/vidscope/application/get_creator.py" \
  "src/vidscope/application/list_creators.py" \
  "src/vidscope/application/list_creator_videos.py" \
  "src/vidscope/mcp/server.py"; do
  [ -f "$f" ] || missing+=("$f")
done
if [ ${#missing[@]} -eq 0 ]; then
  ok "Tous les fichiers cibles S03 existent"
else
  fail "Fichiers manquants: ${missing[*]}"
fi

# -------------------------------------------------------------------
# Step 2 : CLI creator (S03-P02 — peut ne pas être encore fusionné)
# -------------------------------------------------------------------
step "vidscope creator apparaît dans --help (S03-P02)"
if python -m uv run vidscope --help 2>&1 | grep -q "creator"; then
  ok "vidscope creator visible dans --help"
elif [ -f "src/vidscope/cli/commands/creators.py" ]; then
  fail "creators.py existe mais vidscope creator absent de --help"
else
  skip "S03-P02 pas encore fusionné — creators.py absent"
fi

# -------------------------------------------------------------------
# Step 3 : vidscope_get_creator dans MCP server
# -------------------------------------------------------------------
step "vidscope_get_creator enregistré dans MCP server"
if grep -q "vidscope_get_creator" src/vidscope/mcp/server.py; then
  ok "vidscope_get_creator trouvé dans server.py"
else
  fail "vidscope_get_creator manquant dans server.py"
fi

# -------------------------------------------------------------------
# Step 4 : Tests unitaires S03 verts
# -------------------------------------------------------------------
step "Tests unitaires S03 application + MCP verts"
_test_files=(
  "tests/unit/application/test_get_creator.py"
  "tests/unit/application/test_list_creators.py"
  "tests/unit/application/test_list_creator_videos.py"
  "tests/unit/mcp/test_server_creator.py"
)
# Ajouter les tests CLI creator si disponibles (S03-P02)
if [ -f "tests/unit/cli/test_creators.py" ]; then
  _test_files+=("tests/unit/cli/test_creators.py")
fi

if python -m uv run pytest "${_test_files[@]}" -x -q --tb=short 2>&1 | tail -3 | grep -q "passed"; then
  ok "Tests unitaires S03 verts"
else
  fail "Des tests unitaires S03 échouent — relancer avec -v pour détails"
fi

# -------------------------------------------------------------------
# Step 5 : Suite complète sans régression
# -------------------------------------------------------------------
step "Suite complète pytest sans régression"
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
step "9 contrats import-linter verts"
_linter_out=$(python -m uv run lint-imports 2>&1)
if echo "$_linter_out" | grep -q "kept" && ! echo "$_linter_out" | grep -q "BROKEN"; then
  ok "import-linter : 9 contrats verts"
else
  fail "import-linter : contrats cassés"
  echo "$_linter_out"
fi

# -------------------------------------------------------------------
# Step 7 : mypy strict vert
# -------------------------------------------------------------------
step "mypy vert sur src/"
if python -m uv run mypy src 2>&1 | grep -q "Success"; then
  ok "mypy vert"
else
  fail "mypy échoue — voir erreurs ci-dessus"
  python -m uv run mypy src 2>&1 | tail -10
fi

# -------------------------------------------------------------------
# Step 8 : E2E live (optionnel avec --skip-live)
# -------------------------------------------------------------------
step "E2E live : vidscope add + creator show (réseau requis)"
if [ "$SKIP_LIVE" = true ]; then
  skip "Skipped (--skip-live)"
else
  LIVE_URL="https://www.youtube.com/shorts/dQw4w9WgXcW"
  TMPDB=$(mktemp -d)/test.db
  export VIDSCOPE_DATA_DIR="$(dirname "$TMPDB")"
  if python -m uv run vidscope add "$LIVE_URL" 2>&1 | grep -qiE "ok|success|created|ingested"; then
    if python -m uv run vidscope creator list 2>&1 | grep -qiE "total|creator|@"; then
      ok "E2E live : créateur peuplé après add"
    else
      fail "E2E live : vidscope creator list échoue ou ne montre aucun créateur"
    fi
  else
    fail "E2E live : vidscope add échoue"
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
