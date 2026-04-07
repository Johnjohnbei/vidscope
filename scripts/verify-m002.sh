#!/usr/bin/env bash
# Final M002 milestone verification — the authoritative "is M002 done" signal.
#
# Runs every quality gate, the full unit suite, the MCP subprocess integration
# tests, then performs a real CLI demo: seed 2 videos via inline Python,
# call `vidscope suggest` to verify the suggestion engine end-to-end.
#
# Usage:
#   bash scripts/verify-m002.sh                    # full run incl integration
#   bash scripts/verify-m002.sh --skip-integration # fast loop, skip subprocess

set -euo pipefail

SKIP_INTEGRATION=false
for arg in "$@"; do
    case "${arg}" in
        --skip-integration) SKIP_INTEGRATION=true ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-m002-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT
export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

printf "\n${BOLD}=== M002 Final Verification ===${RESET}\n"
printf "${BOLD}Repo:${RESET}              %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}           %s\n" "${TMP_DATA_DIR}"
printf "${BOLD}Integration tests:${RESET} %s\n" \
    "$([ "${SKIP_INTEGRATION}" = true ] && echo 'SKIPPED' || echo 'enabled')"

# 1. Quality gates
run_step "uv sync" python -m uv sync
run_step "ruff check" python -m uv run ruff check src tests
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter" python -m uv run lint-imports
run_step "pytest unit suite" python -m uv run pytest -q

# 2. CLI smoke
run_step "vidscope --version" python -m uv run vidscope --version

help_output="$(python -m uv run vidscope --help 2>&1)"
printf "\n${CYAN}${BOLD}[%02d] vidscope --help lists every command (incl suggest + mcp)${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
missing=()
for cmd in add show list search status doctor suggest mcp; do
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

# 3. Doctor includes mcp check
printf "\n${CYAN}${BOLD}[%02d] vidscope doctor includes mcp row${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
set +e
doctor_output="$(python -m uv run vidscope doctor 2>&1)"
set -e
if echo "${doctor_output}" | grep -q "mcp"; then
    printf "${GREEN}✓${RESET} doctor shows mcp check\n"
else
    printf "${RED}✗${RESET} doctor missing mcp row\n"
    failed_steps+=("doctor mcp check")
fi

# 4. MCP subprocess integration tests
if [[ "${SKIP_INTEGRATION}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[MCP subprocess integration] skipped${RESET}\n"
else
    run_step "MCP subprocess integration tests" \
        python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v
fi

# 5. End-to-end suggestion engine demo (no network needed — seed directly)
printf "\n${CYAN}${BOLD}[%02d] suggestion engine end-to-end demo${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
demo_output="$(python -m uv run python -c "
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Analysis, Language, Platform, PlatformId, Video,
)
from vidscope.infrastructure.container import build_container

container = build_container()
with container.unit_of_work() as uow:
    source = uow.videos.upsert_by_platform_id(
        Video(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId('demo-source'),
            url='https://example.com/demo-source',
            title='Python cooking tutorial',
            media_key='videos/youtube/demo-source/media.mp4',
        )
    )
    matching = uow.videos.upsert_by_platform_id(
        Video(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId('demo-match'),
            url='https://example.com/demo-match',
            title='Python recipe collection',
            media_key='videos/youtube/demo-match/media.mp4',
        )
    )
    uow.analyses.add(
        Analysis(
            video_id=source.id,
            provider='heuristic',
            language=Language.ENGLISH,
            keywords=('python', 'cooking', 'recipe', 'tips'),
            topics=('python',),
            score=60.0,
            summary='python cooking tutorial',
        )
    )
    uow.analyses.add(
        Analysis(
            video_id=matching.id,
            provider='heuristic',
            language=Language.ENGLISH,
            keywords=('python', 'recipe', 'food'),
            topics=('python',),
            score=55.0,
            summary='python recipe collection',
        )
    )
    print(f'seeded source_id={source.id} matching_id={matching.id}')
" 2>&1)"
demo_exit=$?
set -e
echo "${demo_output}"

if [[ "${demo_exit}" -ne 0 ]]; then
    printf "${RED}✗${RESET} seed step failed\n"
    failed_steps+=("seed 2 videos")
else
    # Run vidscope suggest 1 and verify output
    source_id="$(echo "${demo_output}" | grep -oE 'source_id=[0-9]+' | cut -d= -f2)"
    if [[ -z "${source_id}" ]]; then
        printf "${RED}✗${RESET} could not parse source_id from seed output\n"
        failed_steps+=("parse seed output")
    else
        set +e
        suggest_output="$(python -m uv run vidscope suggest "${source_id}" 2>&1)"
        suggest_exit=$?
        set -e
        echo "${suggest_output}"
        if [[ "${suggest_exit}" -eq 0 ]] && \
           echo "${suggest_output}" | grep -q "Python recipe collection"; then
            printf "${GREEN}✓${RESET} vidscope suggest returned matching video\n"
        else
            printf "${RED}✗${RESET} vidscope suggest did not return the matching video (exit ${suggest_exit})\n"
            failed_steps+=("vidscope suggest demo")
        fi
    fi
fi

# Summary
printf "\n${BOLD}=== M002 Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ M002 VERIFICATION PASSED${RESET}\n"
    printf "${DIM}MCP server + suggestion engine ready. AI agents can now drive the vidscope library.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ M002 VERIFICATION FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
