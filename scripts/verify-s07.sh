#!/usr/bin/env bash
# End-to-end verification of M001/S07 — cookie-based authentication.
#
# Runs every check that proves S07's success criteria hold on a clean
# environment, plus the live integration tests with cookie awareness.
#
# Usage
# -----
#     bash scripts/verify-s07.sh                    # full run with integration
#     bash scripts/verify-s07.sh --skip-integration # fast loop, no network
#
# Cookie behavior
# ---------------
# - When VIDSCOPE_COOKIES_FILE is set and points at a real file, the
#   integration block runs the Instagram test expecting it to PASS
#   (cookies were opted in, so any failure is a real failure).
# - When the env var is unset or the file is missing, Instagram still
#   xfails — the script accepts that as expected behavior and reports
#   "Instagram test xfailed (cookies not provided)" in the summary.
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

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
SKIP_INTEGRATION=false
for arg in "$@"; do
    case "${arg}" in
        --skip-integration) SKIP_INTEGRATION=true ;;
        -h|--help)
            sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "unknown argument: ${arg}" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -t 1 ]]; then
    BOLD="\033[1m"
    GREEN="\033[0;32m"
    RED="\033[0;31m"
    YELLOW="\033[0;33m"
    CYAN="\033[0;36m"
    DIM="\033[2m"
    RESET="\033[0m"
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
        return "${exit_code}"
    fi
}

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-s07-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT

export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

# Detect whether the user has a real cookies file configured
COOKIES_AVAILABLE=false
COOKIES_PATH=""
if [[ -n "${VIDSCOPE_COOKIES_FILE:-}" ]] && [[ -f "${VIDSCOPE_COOKIES_FILE}" ]]; then
    COOKIES_AVAILABLE=true
    COOKIES_PATH="${VIDSCOPE_COOKIES_FILE}"
fi

printf "${BOLD}Repo:${RESET}              %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}           %s\n" "${TMP_DATA_DIR}"
printf "${BOLD}Cookies:${RESET}           %s\n" \
    "$([ "${COOKIES_AVAILABLE}" = true ] && echo "configured at ${COOKIES_PATH}" || echo 'NOT configured (Instagram tests will xfail)')"
printf "${BOLD}Integration tests:${RESET} %s\n" \
    "$([ "${SKIP_INTEGRATION}" = true ] && echo 'SKIPPED (--skip-integration)' || echo 'enabled')"

# ---------------------------------------------------------------------------
# 1. Dependency sync
# ---------------------------------------------------------------------------
run_step "uv sync" python -m uv sync

# ---------------------------------------------------------------------------
# 2. Quality gates
# ---------------------------------------------------------------------------
run_step "ruff check" python -m uv run ruff check src tests
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter" python -m uv run lint-imports
run_step "pytest unit suite" python -m uv run pytest -q

# ---------------------------------------------------------------------------
# 3. CLI smoke — help + doctor (with cookies row) + errors
# ---------------------------------------------------------------------------
run_step "vidscope --version" python -m uv run vidscope --version

help_output="$(python -m uv run vidscope --help 2>&1)"
printf "\n${CYAN}${BOLD}[%02d] vidscope --help lists every command${RESET}\n" \
    "$((step_count + 1))"
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

# vidscope doctor — must include the new cookies row
printf "\n${CYAN}${BOLD}[%02d] vidscope doctor (must include cookies row)${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
set +e
doctor_output="$(python -m uv run vidscope doctor 2>&1)"
doctor_exit=$?
set -e
echo "${doctor_output}"
if [[ "${doctor_exit}" -eq 0 || "${doctor_exit}" -eq 2 ]]; then
    if echo "${doctor_output}" | grep -q "ffmpeg" && \
       echo "${doctor_output}" | grep -q "yt-dlp" && \
       echo "${doctor_output}" | grep -q "cookies"; then
        printf "${GREEN}✓${RESET} doctor printed all 3 checks (exit ${doctor_exit})\n"
    else
        printf "${RED}✗${RESET} doctor output missing one of: ffmpeg, yt-dlp, cookies\n"
        failed_steps+=("vidscope doctor")
    fi
else
    printf "${RED}✗${RESET} doctor returned unexpected exit ${doctor_exit}\n"
    failed_steps+=("vidscope doctor")
fi

# Unsupported URL still rejected with exit 1
printf "\n${CYAN}${BOLD}[%02d] vidscope add 'https://vimeo.com/12345' exits 1${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
set +e
python -m uv run vidscope add "https://vimeo.com/12345" >/dev/null 2>&1
vimeo_exit=$?
set -e
if [[ "${vimeo_exit}" -eq 1 ]]; then
    printf "${GREEN}✓${RESET} unsupported platform rejected with exit 1\n"
else
    printf "${RED}✗${RESET} expected exit 1, got ${vimeo_exit}\n"
    failed_steps+=("unsupported URL rejection")
fi

# ---------------------------------------------------------------------------
# 4. Misconfigured cookies fails build_container
# ---------------------------------------------------------------------------
printf "\n${CYAN}${BOLD}[%02d] misconfigured VIDSCOPE_COOKIES_FILE fails fast${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
BAD_COOKIES_PATH="${TMP_DATA_DIR}/definitely-not-here.txt"
set +e
VIDSCOPE_COOKIES_FILE="${BAD_COOKIES_PATH}" \
    python -m uv run vidscope status >/dev/null 2>&1
bad_cookies_exit=$?
set -e
if [[ "${bad_cookies_exit}" -ne 0 ]]; then
    printf "${GREEN}✓${RESET} bad cookies path fails build_container (exit ${bad_cookies_exit})\n"
else
    printf "${RED}✗${RESET} bad cookies path should have failed but exit was 0\n"
    failed_steps+=("misconfigured cookies fail-fast")
fi

# ---------------------------------------------------------------------------
# 5. Integration tests — cookie-aware Instagram + always TikTok/YouTube
# ---------------------------------------------------------------------------
if [[ "${SKIP_INTEGRATION}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[integration] skipped via --skip-integration${RESET}\n"
else
    printf "\n${CYAN}${BOLD}[%02d] live integration tests (Instagram + TikTok + YouTube, priority order)${RESET}\n" \
        "$((step_count + 1))"
    step_count=$((step_count + 1))
    set +e
    python -m uv run pytest tests/integration -m integration -v
    integration_exit=$?
    set -e
    if [[ "${integration_exit}" -eq 0 ]]; then
        if [[ "${COOKIES_AVAILABLE}" = true ]]; then
            printf "${GREEN}✓${RESET} integration suite green (Instagram passing with cookies)\n"
        else
            printf "${GREEN}✓${RESET} integration suite green (Instagram xfailed, cookies not provided)\n"
        fi
    else
        printf "${RED}✗${RESET} integration suite failed (exit ${integration_exit})\n"
        failed_steps+=("live integration tests")
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf "\n${BOLD}=== Summary ===${RESET}\n"
printf "Total steps:       %d\n" "${step_count}"
printf "Failed:            %d\n" "${#failed_steps[@]}"
printf "Cookies status:    %s\n" \
    "$([ "${COOKIES_AVAILABLE}" = true ] && echo "configured (Instagram should pass)" || echo 'not configured (Instagram xfails as expected)')"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ S07 verification PASSED${RESET}\n"
    if [[ "${COOKIES_AVAILABLE}" = true ]]; then
        printf "${DIM}Instagram is alive on real networks. R001 validated for all three platforms.${RESET}\n"
    else
        printf "${DIM}S07 plumbing is correct. To validate Instagram in live, set VIDSCOPE_COOKIES_FILE per docs/cookies.md and re-run.${RESET}\n"
    fi
    exit 0
else
    printf "\n${RED}${BOLD}✗ S07 verification FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
