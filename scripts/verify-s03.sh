#!/usr/bin/env bash
# End-to-end verification of M001/S03 — real ingest + transcription.
#
# Usage
# -----
#     bash scripts/verify-s03.sh                    # full run incl. integration
#     bash scripts/verify-s03.sh --skip-integration # fast loop, no network
#
# Note
# ----
# The first integration run downloads the faster-whisper base model
# (~150MB) into <data_dir>/models/. Subsequent runs reuse the cache.

set -euo pipefail

SKIP_INTEGRATION=false
for arg in "$@"; do
    case "${arg}" in
        --skip-integration) SKIP_INTEGRATION=true ;;
        -h|--help)
            sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
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

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-s03-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT
export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

printf "${BOLD}Repo:${RESET}              %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}           %s\n" "${TMP_DATA_DIR}"
printf "${BOLD}Whisper model:${RESET}     %s\n" "${VIDSCOPE_WHISPER_MODEL:-base}"
printf "${BOLD}Integration tests:${RESET} %s\n" \
    "$([ "${SKIP_INTEGRATION}" = true ] && echo 'SKIPPED (--skip-integration)' || echo 'enabled (will download whisper model on first run, ~150MB)')"

# 1. Dependency sync
run_step "uv sync" python -m uv sync

# 2. Quality gates
run_step "ruff check" python -m uv run ruff check src tests
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter" python -m uv run lint-imports
run_step "pytest unit suite" python -m uv run pytest -q

# 3. CLI smoke
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
    failed_steps+=("vidscope --help lists every command")
fi

# 4. Integration tests with transcription
if [[ "${SKIP_INTEGRATION}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[integration] skipped via --skip-integration${RESET}\n"
else
    printf "\n${CYAN}${BOLD}[%02d] live integration tests (ingest + transcribe)${RESET}\n" \
        "$((step_count + 1))"
    step_count=$((step_count + 1))
    printf "${YELLOW}note:${RESET} first run downloads faster-whisper base model (~150MB)\n"
    set +e
    python -m uv run pytest tests/integration -m "integration and slow" -v
    integration_exit=$?
    set -e
    if [[ "${integration_exit}" -eq 0 ]]; then
        printf "${GREEN}✓${RESET} integration suite green (Instagram xfail expected without cookies)\n"
    else
        printf "${RED}✗${RESET} integration suite failed (exit ${integration_exit})\n"
        failed_steps+=("live integration tests")
    fi

    # Verify the sandboxed DB has at least one transcript row
    printf "\n${CYAN}${BOLD}[%02d] sandboxed DB has transcript rows${RESET}\n" \
        "$((step_count + 1))"
    step_count=$((step_count + 1))
    set +e
    python -m uv run vidscope add \
        "https://www.youtube.com/shorts/34WNvQ1sIw4" >/dev/null 2>&1
    add_exit=$?
    set -e
    if [[ "${add_exit}" -eq 0 ]]; then
        check_output="$(python -m uv run python -c "
from vidscope.infrastructure.container import build_container
c = build_container()
with c.unit_of_work() as uow:
    videos = uow.videos.list_recent(limit=10)
    if not videos:
        print('NO_VIDEOS')
        raise SystemExit(1)
    v = videos[0]
    t = uow.transcripts.get_for_video(v.id)
    if t is None:
        print('NO_TRANSCRIPT')
        raise SystemExit(1)
    print(f'video_id={v.id} title={v.title!r} lang={t.language.value} segments={len(t.segments)}')
" 2>&1)"
        check_exit=$?
        echo "${check_output}"
        if [[ "${check_exit}" -eq 0 ]]; then
            printf "${GREEN}✓${RESET} sandbox has real video + transcript rows\n"
        else
            printf "${RED}✗${RESET} round-trip verification failed\n"
            failed_steps+=("sandbox DB verification")
        fi
    else
        printf "${YELLOW}⚠${RESET}  live add failed (exit ${add_exit}) — likely transient\n"
    fi
fi

# Summary
printf "\n${BOLD}=== Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ S03 verification PASSED${RESET}\n"
    printf "${DIM}Transcription brick is alive on real networks. S04 can wire ffmpeg frame extraction.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ S03 verification FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
