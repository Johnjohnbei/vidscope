#!/usr/bin/env bash
# End-to-end verification of M006/S02 — Ingest stage populates creator.
#
# Usage
# -----
#     bash scripts/verify-m006-s02.sh                    # full run
#     bash scripts/verify-m006-s02.sh --skip-full-suite  # M006/S02 targeted tests only
#
# Exit codes: 0 — every required step passed | 1 — at least one failed

set -euo pipefail

SKIP_FULL_SUITE=false
for arg in "$@"; do
    case "${arg}" in
        --skip-full-suite) SKIP_FULL_SUITE=true ;;
        -h|--help)
            sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
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

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-m006-s02-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT

export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

printf "${BOLD}Repo:${RESET}     %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}  %s\n" "${TMP_DATA_DIR}"

# --- 1. Dependency sync ---
run_step "uv sync" python -m uv sync

# --- 2. Quality gates ---
run_step "ruff check" python -m uv run ruff check src tests scripts
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter (9 contracts, pipeline-has-no-adapters key)" \
    python -m uv run lint-imports

# --- 3. M006/S02 targeted tests ---
run_step "P01 CreatorInfo contract tests" \
    python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py -x -q
run_step "P02 YtdlpDownloader creator extraction" \
    python -m uv run pytest \
      tests/unit/adapters/ytdlp/test_downloader.py::TestCreatorInfoExtraction -x -q
run_step "P03 IngestStage creator wiring (D-01/D-02/D-03/D-04)" \
    python -m uv run pytest \
      tests/unit/pipeline/stages/test_ingest.py::TestCreatorWiring -x -q

# --- 4. Regression guards ---
run_step "regression: IngestStage existing tests" \
    python -m uv run pytest \
      tests/unit/pipeline/stages/test_ingest.py::TestHappyPath \
      tests/unit/pipeline/stages/test_ingest.py::TestErrorPaths \
      tests/unit/pipeline/stages/test_ingest.py::TestStageIdentity -x -q
run_step "regression: YtdlpDownloader existing suite" \
    python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q
run_step "regression: S01 foundation tests" \
    python -m uv run pytest \
      tests/unit/adapters/sqlite/test_creator_repository.py \
      tests/unit/adapters/sqlite/test_video_repository.py::TestWriteThroughAuthor \
      tests/unit/adapters/sqlite/test_unit_of_work.py -x -q

# --- 5. Full suite ---
if [[ "${SKIP_FULL_SUITE}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[full pytest suite] skipped${RESET}\n"
else
    run_step "full pytest suite" python -m uv run pytest -q
fi

# --- Summary ---
printf "\n${BOLD}=== Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ M006/S02 verification PASSED${RESET}\n"
    printf "${DIM}Every new vidscope add <url> now upserts a creator row (when yt-dlp exposes uploader_id) and links it via videos.creator_id — D-01/D-02/D-03/D-04 all enforced.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ M006/S02 verification FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
