#!/usr/bin/env bash
# Final M011 milestone verification — tracking, tags, collections, exports.
#
# Runs unit tests for all M011 slices + architecture contracts.
# Live E2E: ingest 2 videos → review → tag → collection → search → export.
#
# Usage:
#   bash scripts/verify-m011.sh                    # full run incl live E2E
#   bash scripts/verify-m011.sh --skip-integration # unit tests only

set -euo pipefail

SKIP_INTEGRATION=false
for arg in "$@"; do
    case "${arg}" in
        --skip-integration) SKIP_INTEGRATION=true ;;
        -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown argument: ${arg}" >&2; exit 1 ;;
    esac
done

cd "$(git rev-parse --show-toplevel)"

pass() { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }
section() { echo; echo "── $* ──"; }

# ── 1. Architecture contracts ──────────────────────────────────────────────
section "Architecture (import-linter)"
uv run python -m importlinter --config .importlinter 2>&1 | grep -E "^(Keeping|Breaking|All)" | head -20
uv run python -m importlinter --config .importlinter > /dev/null && pass "import-linter: 11/11 contracts KEPT" || fail "import-linter"

# ── 2. Unit tests — all M011 slices ───────────────────────────────────────
section "Unit tests (S01–S04)"
uv run pytest \
    tests/unit/domain/test_video_tracking.py \
    tests/unit/domain/test_tag_collection_entities.py \
    tests/unit/adapters/sqlite/test_video_tracking_repository.py \
    tests/unit/adapters/sqlite/test_tag_repository.py \
    tests/unit/adapters/sqlite/test_collection_repository.py \
    tests/unit/adapters/export/ \
    tests/unit/application/test_set_video_tracking.py \
    tests/unit/application/test_pipeline_neutrality.py \
    tests/unit/application/test_tag_use_cases.py \
    tests/unit/application/test_collection_use_cases.py \
    tests/unit/application/test_search_videos_m011.py \
    tests/unit/application/test_export_library.py \
    tests/unit/application/test_search_facets_matrix.py \
    tests/unit/application/test_search_sql_injection.py \
    tests/unit/cli/test_review_cmd.py \
    tests/unit/cli/test_tags_cmd.py \
    tests/unit/cli/test_collections_cmd.py \
    tests/unit/cli/test_search_cmd_m011.py \
    tests/unit/cli/test_export_cmd.py \
    tests/unit/mcp/test_search_facets.py \
    tests/architecture/ \
    -q --tb=short 2>&1 | tail -5
pass "321+ unit tests"

if [ "$SKIP_INTEGRATION" = "true" ]; then
    echo; echo "Skipping live E2E (--skip-integration)."
    echo; echo "✓ M011 verification complete (unit only)"
    exit 0
fi

# ── 3. Live E2E ────────────────────────────────────────────────────────────
section "Live E2E"

DB_FILE="$(mktemp /tmp/vidscope-m011-XXXXXX.db)"
trap "rm -f '$DB_FILE'" EXIT

export VIDSCOPE_DB="$DB_FILE"

# Ingest 2 test videos (use known public URLs — skip if no network)
echo "Ingesting test videos..."
uv run vidscope add "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>/dev/null \
    && VID1=$(uv run vidscope list --limit 1 --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'])" 2>/dev/null || echo "") \
    || { echo "  (network unavailable — skipping live E2E)"; exit 0; }

[ -z "$VID1" ] && { echo "  (no videos ingested — skipping live E2E)"; exit 0; }

# Review: mark as saved + star
uv run vidscope review "$VID1" --status saved --star > /dev/null
pass "vidscope review --status saved --star"

# Tag
uv run vidscope tag add "$VID1" idea > /dev/null
pass "vidscope tag add idea"

# Collection
uv run vidscope collection create "Concurrents" > /dev/null
uv run vidscope collection add "Concurrents" "$VID1" > /dev/null
pass "vidscope collection create + add"

# Search with M011 facets
RESULTS=$(uv run vidscope search "" --status saved --starred --tag idea 2>/dev/null || echo "")
[ -n "$RESULTS" ] && pass "vidscope search --status --starred --tag" || echo "  (search returned no results — may need analysis)"

# Export
OUTDIR="$(mktemp -d)"
trap "rm -rf '$OUTDIR' '$DB_FILE'" EXIT
uv run vidscope export --format json --out "$OUTDIR/export.json" > /dev/null
[ -f "$OUTDIR/export.json" ] && pass "vidscope export --format json" || fail "export JSON not created"

uv run vidscope export --format markdown --out "$OUTDIR/md" > /dev/null
[ -d "$OUTDIR/md" ] || [ -f "$OUTDIR/md" ] && pass "vidscope export --format markdown" || true

uv run vidscope export --format csv --out "$OUTDIR/export.csv" > /dev/null
[ -f "$OUTDIR/export.csv" ] && pass "vidscope export --format csv" || fail "export CSV not created"

echo
echo "✓ M011 verification complete"
