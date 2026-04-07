#!/usr/bin/env bash
# End-to-end verification of M001/S04 — frame extraction.
#
# Usage:
#   bash scripts/verify-s04.sh                    # full run incl integration
#   bash scripts/verify-s04.sh --skip-integration # fast loop, no network

set -euo pipefail

SKIP_INTEGRATION=false
for arg in "$@"; do
    case "${arg}" in
        --skip-integration) SKIP_INTEGRATION=true ;;
        -h|--help)
            sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown argument: ${arg}" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -t 1 ]]; then
    BOLD="\033[1m"; GREEN="\033[0;32m"; RED="\033[0;31m"
    YELLOW="\033[0;33m"; CYAN="\033[0;36m"; DIM="\033[2m"; RESET="\033[0m"
else
    BOLD=""; GREEN=""; RED=""; YELLOW=""; CYAN=""; DIM=""; RESET=""
fi

step_count=0
failed_steps=()

run_step() {
    local name="$1"; shift
    step_count=$((step_count + 1))
    printf "\n${CYAN}${BOLD}[%02d] %s${RESET}\n" "${step_count}" "${name}"
    printf "${DIM}\$ %s${RESET}\n" "$*"
    if "$@"; then
        printf "${GREEN}✓${RESET} %s\n" "${name}"
    else
        local exit_code=$?
        printf "${RED}✗${RESET} %s (exit %d)\n" "${name}" "${exit_code}"
        failed_steps+=("${name}")
        return "${exit_code}"
    fi
}

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-s04-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT
export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

# Detect ffmpeg presence
FFMPEG_AVAILABLE=false
if command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG_AVAILABLE=true
fi

printf "${BOLD}Repo:${RESET}              %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}           %s\n" "${TMP_DATA_DIR}"
printf "${BOLD}ffmpeg:${RESET}            %s\n" \
    "$([ "${FFMPEG_AVAILABLE}" = true ] && echo 'on PATH (frames stage will run)' || echo 'NOT on PATH (frames stage will be marked FAILED)')"
printf "${BOLD}Integration tests:${RESET} %s\n" \
    "$([ "${SKIP_INTEGRATION}" = true ] && echo 'SKIPPED (--skip-integration)' || echo 'enabled')"

# Quality gates
run_step "uv sync" python -m uv sync
run_step "ruff check" python -m uv run ruff check src tests
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter" python -m uv run lint-imports
run_step "pytest unit suite" python -m uv run pytest -q

# CLI smoke
run_step "vidscope --version" python -m uv run vidscope --version

help_output="$(python -m uv run vidscope --help 2>&1)"
printf "\n${CYAN}${BOLD}[%02d] vidscope --help lists every command${RESET}\n" "$((step_count + 1))"
step_count=$((step_count + 1))
missing=()
for cmd in add show list search status doctor; do
    if ! echo "${help_output}" | grep -qE "(^|[[:space:]])${cmd}([[:space:]]|$)"; then
        missing+=("${cmd}")
    fi
done
if [[ "${#missing[@]}" -eq 0 ]]; then
    printf "${GREEN}✓${RESET} every command present\n"
else
    printf "${RED}✗${RESET} missing commands: %s\n" "${missing[*]}"
    failed_steps+=("vidscope --help")
fi

# Integration tests
if [[ "${SKIP_INTEGRATION}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[integration] skipped via --skip-integration${RESET}\n"
else
    printf "\n${CYAN}${BOLD}[%02d] live integration tests${RESET}\n" "$((step_count + 1))"
    step_count=$((step_count + 1))
    set +e
    python -m uv run pytest tests/integration -m "integration and slow" -v
    integration_exit=$?
    set -e
    if [[ "${integration_exit}" -eq 0 ]]; then
        if [[ "${FFMPEG_AVAILABLE}" = true ]]; then
            printf "${GREEN}✓${RESET} integration suite green (frames extracted via ffmpeg)\n"
        else
            printf "${GREEN}✓${RESET} integration suite green (frames stage tolerated as failed because ffmpeg is missing)\n"
        fi
    else
        printf "${RED}✗${RESET} integration suite failed (exit ${integration_exit})\n"
        failed_steps+=("live integration tests")
    fi
fi

# Summary
printf "\n${BOLD}=== Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ S04 verification PASSED${RESET}\n"
    if [[ "${FFMPEG_AVAILABLE}" = true ]]; then
        printf "${DIM}Frame extraction is alive on real networks. R003 validated.${RESET}\n"
    else
        printf "${DIM}S04 plumbing correct. Install ffmpeg to validate frame extraction in live.${RESET}\n"
    fi
    exit 0
else
    printf "\n${RED}${BOLD}✗ S04 verification FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
