#!/usr/bin/env bash
# End-to-end verification of M001/S01 — the VidScope socle.
#
# Runs every check that proves S01's success criteria hold on a clean
# environment. This script is the authoritative "does the socle work"
# signal. Re-run it any time after pulling a change that touches the
# package, the adapters, the CLI, or the quality gates.
#
# Exit codes
# ----------
# 0 — every step passed
# 1 — at least one step failed (see the output for the failing step)
#
# Portability
# -----------
# Runs on Windows git-bash, macOS, and Linux. Uses `python -m uv run`
# everywhere instead of a bare `uv` binary so it works whether uv is
# installed via the standalone installer, pip --user, or a system
# package manager.

set -euo pipefail

# Resolve the repository root from the script location so this script
# can be invoked from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Colors (disabled when stdout is not a TTY — CI logs stay clean)
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

# Use a temporary data directory so this script never touches the
# user's real %LOCALAPPDATA%/vidscope. Cleaned up on exit.
TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT

export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"
printf "${BOLD}Repo:${RESET}    %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET} %s\n" "${TMP_DATA_DIR}"

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
run_step "pytest suite" python -m uv run pytest -q

# ---------------------------------------------------------------------------
# 3. CLI smoke
# ---------------------------------------------------------------------------
run_step "vidscope --version" python -m uv run vidscope --version

# Capture --help output and assert every command is listed
help_output="$(python -m uv run vidscope --help 2>&1 || true)"
printf "\n${CYAN}${BOLD}[%02d] vidscope --help lists every command${RESET}\n" "$((step_count + 1))"
step_count=$((step_count + 1))
missing=()
for cmd in add show list search status doctor; do
    if ! echo "${help_output}" | grep -qE "(^|[[:space:]])${cmd}([[:space:]]|$)"; then
        missing+=("${cmd}")
    fi
done
if [[ "${#missing[@]}" -eq 0 ]]; then
    printf "${GREEN}✓${RESET} every command present: add show list search status doctor\n"
else
    printf "${RED}✗${RESET} missing commands in --help: %s\n" "${missing[*]}"
    failed_steps+=("vidscope --help lists every command")
fi

# ---------------------------------------------------------------------------
# 4. Database creation on first status call
# ---------------------------------------------------------------------------
run_step "vidscope status (empty DB)" python -m uv run vidscope status

# Assert the DB file was created with every expected table
run_step "DB schema verification" python -m uv run python -c "
from sqlalchemy import inspect
from vidscope.infrastructure.config import get_config, reset_config_cache
from vidscope.infrastructure.sqlite_engine import build_engine
reset_config_cache()
cfg = get_config()
assert cfg.db_path.exists(), f'db not created at {cfg.db_path}'
engine = build_engine(cfg.db_path)
names = set(inspect(engine).get_table_names())
required = {'videos', 'transcripts', 'frames', 'analyses', 'pipeline_runs', 'search_index'}
missing = required - names
assert not missing, f'missing tables: {missing}'
print('tables:', sorted(names))
"

# ---------------------------------------------------------------------------
# 5. Doctor command (tolerates ffmpeg missing — exit 0 OR 2)
# ---------------------------------------------------------------------------
printf "\n${CYAN}${BOLD}[%02d] vidscope doctor${RESET}\n" "$((step_count + 1))"
step_count=$((step_count + 1))
# Run doctor, capture both stdout and stderr and the real exit code.
# We cannot use `$(cmd || true)` because that masks the real exit via
# the `|| true`; we use `set +e; ...; set -e` instead.
set +e
doctor_output="$(python -m uv run vidscope doctor 2>&1)"
doctor_exit=$?
set -e
echo "${doctor_output}"
if [[ "${doctor_exit}" -eq 0 || "${doctor_exit}" -eq 2 ]]; then
    # Require both check names to appear in the report regardless of
    # whether ffmpeg is installed.
    if echo "${doctor_output}" | grep -q "ffmpeg" && \
       echo "${doctor_output}" | grep -q "yt-dlp"; then
        printf "${GREEN}✓${RESET} doctor printed both checks (exit ${doctor_exit})\n"
    else
        printf "${RED}✗${RESET} doctor output missing expected check names\n"
        failed_steps+=("vidscope doctor")
    fi
else
    printf "${RED}✗${RESET} doctor returned unexpected exit code ${doctor_exit}\n"
    failed_steps+=("vidscope doctor")
fi

# ---------------------------------------------------------------------------
# 6. Ingest happy path writes a PENDING pipeline_runs row
# ---------------------------------------------------------------------------
run_step "vidscope add (PENDING stub)" \
    python -m uv run vidscope add "https://www.youtube.com/watch?v=verify-s01"

run_step "vidscope status (after add, expects 1 run)" \
    python -m uv run python -c "
from vidscope.infrastructure.container import build_container
container = build_container()
with container.unit_of_work() as uow:
    runs = uow.pipeline_runs.list_recent(limit=10)
    assert len(runs) == 1, f'expected 1 run, got {len(runs)}'
    run = runs[0]
    assert run.phase.value == 'ingest', f'wrong phase: {run.phase}'
    assert run.status.value == 'pending', f'wrong status: {run.status}'
    assert run.source_url == 'https://www.youtube.com/watch?v=verify-s01'
    print('pipeline_run ok:', run.id, run.phase.value, run.status.value)
"

# ---------------------------------------------------------------------------
# 7. User-error exit code on empty URL
# ---------------------------------------------------------------------------
printf "\n${CYAN}${BOLD}[%02d] vidscope add '' exits 1 (user error)${RESET}\n" "$((step_count + 1))"
step_count=$((step_count + 1))
set +e
python -m uv run vidscope add "" >/dev/null 2>&1
empty_exit=$?
set -e
if [[ "${empty_exit}" -eq 1 ]]; then
    printf "${GREEN}✓${RESET} empty URL exits 1 as expected\n"
else
    printf "${RED}✗${RESET} empty URL exit code = %d (expected 1)\n" "${empty_exit}"
    failed_steps+=("vidscope add '' user-error exit code")
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf "\n${BOLD}=== Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ S01 verification PASSED${RESET}\n"
    printf "${DIM}The socle is ready for S02 to wire the real ingest stage.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ S01 verification FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
