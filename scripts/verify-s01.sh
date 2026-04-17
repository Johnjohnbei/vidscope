#!/usr/bin/env bash
# End-to-end verification of M006/S01 — Creator domain foundation.
#
# Runs every check that proves S01's success criteria hold on a
# clean environment plus an offline backfill smoke.
#
# Usage
# -----
#     bash scripts/verify-s01.sh                       # full run
#     bash scripts/verify-s01.sh --skip-backfill-smoke # quality gates only
#
# Exit codes
# ----------
# 0 — every required step passed
# 1 — at least one required step failed
#
# Portability
# -----------
# Works on Windows git-bash, macOS, and Linux via `python -m uv run`.

set -euo pipefail

SKIP_BACKFILL=false
for arg in "$@"; do
    case "${arg}" in
        --skip-backfill-smoke) SKIP_BACKFILL=true ;;
        -h|--help)
            sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "unknown argument: ${arg}" >&2
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -t 1 ]]; then
    BOLD="\033[1m" GREEN="\033[0;32m" RED="\033[0;31m"
    YELLOW="\033[0;33m" CYAN="\033[0;36m" DIM="\033[2m" RESET="\033[0m"
else
    BOLD="" GREEN="" RED="" YELLOW="" CYAN="" DIM="" RESET=""
fi

step_count=0
failed_steps=()

run_step() {
    local name="$1"
    shift
    step_count=$((step_count + 1))
    printf "\n${CYAN}${BOLD}[%02d] %s${RESET}\n" "${step_count}" "${name}"
    printf "${DIM}\$ %s${RESET}\n" "$*"
    if "$@"; then
        printf "${GREEN}✓${RESET} %s\n" "${name}"
    else
        local exit_code=$?
        printf "${RED}✗${RESET} %s (exit %d)\n" "${name}" "${exit_code}"
        failed_steps+=("${name}")
    fi
}

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-s01-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT

export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

printf "${BOLD}Repo:${RESET}     %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}  %s\n" "${TMP_DATA_DIR}"

# --- 1. Dependency sync ---
run_step "uv sync" python -m uv sync

# --- 2. Quality gates ---
run_step "ruff check" python -m uv run ruff check src tests scripts
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter (9 contracts)" python -m uv run lint-imports
run_step "pytest unit suite" python -m uv run pytest -q

# --- 3. M006/S01 targeted tests ---
run_step "creator repo tests" \
    python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py -x -q
run_step "schema creators tests" \
    python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py::TestCreatorsSchema tests/unit/adapters/sqlite/test_schema.py::TestVideosCreatorIdAlter -x -q
run_step "write-through regression" \
    python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py::TestWriteThroughAuthor -x -q
run_step "UoW creator-txn tests" \
    python -m uv run pytest tests/unit/adapters/sqlite/test_unit_of_work.py::TestCreatorInTransaction -x -q
run_step "backfill tests" \
    python -m uv run pytest tests/unit/scripts/test_backfill_creators.py -x -q

# --- 4. Backfill script smoke (offline: --help + dry-run on empty sandbox) ---
if [[ "${SKIP_BACKFILL}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[backfill smoke] skipped${RESET}\n"
else
    run_step "backfill --help" \
        python -m uv run python scripts/backfill_creators.py --help
    # Dry-run on an empty sandbox: nothing to probe, exits 0, zero writes.
    run_step "backfill dry-run on empty sandbox" \
        python -m uv run python scripts/backfill_creators.py
fi

# --- Summary ---
printf "\n${BOLD}=== Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ S01 verification PASSED${RESET}\n"
    printf "${DIM}M006/S01 foundations shippable: Creator domain + CreatorRepository + SqlCreatorRepository + schema migration + backfill script.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ S01 verification FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
