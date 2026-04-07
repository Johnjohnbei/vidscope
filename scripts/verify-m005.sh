#!/usr/bin/env bash
# Final M005 milestone verification — the authoritative "is M005 done" signal.
#
# Runs every quality gate, the full unit suite, then performs deterministic
# stub-HTTP smoke tests for the cookies sub-application: validator, status,
# set, clear, and probe (via stubbed yt_dlp.YoutubeDL). No real network.
#
# Usage:
#   bash scripts/verify-m005.sh                    # full run
#   bash scripts/verify-m005.sh --skip-integration # skip subprocess MCP tests
#
# Manual live validation:
#   1. Export cookies.txt from your browser (see docs/cookies.md)
#   2. vidscope cookies set ~/Downloads/cookies.txt
#   3. vidscope cookies test
#   4. vidscope add https://www.instagram.com/reel/<id>/

set -euo pipefail

SKIP_INTEGRATION=false
for arg in "$@"; do
    case "${arg}" in
        --skip-integration) SKIP_INTEGRATION=true ;;
        -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-m005-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT
export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"
unset VIDSCOPE_COOKIES_FILE || true

printf "\n${BOLD}=== M005 Final Verification ===${RESET}\n"
printf "${BOLD}Repo:${RESET}              %s\n" "${REPO_ROOT}"
printf "${BOLD}Sandbox:${RESET}           %s\n" "${TMP_DATA_DIR}"
printf "${BOLD}Integration tests:${RESET} %s\n" \
    "$([ "${SKIP_INTEGRATION}" = true ] && echo 'SKIPPED' || echo 'enabled')"

# 1. Quality gates
run_step "uv sync" python -m uv sync
run_step "ruff check" python -m uv run ruff check src tests
run_step "mypy strict" python -m uv run mypy src
run_step "import-linter (9 contracts)" python -m uv run lint-imports
run_step "pytest unit suite" python -m uv run pytest -q

# 2. CLI surface — vidscope cookies sub-application is registered
help_output="$(python -m uv run vidscope --help 2>&1)"
printf "\n${CYAN}${BOLD}[%02d] vidscope --help lists cookies sub-application${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
if echo "${help_output}" | grep -qE "(^|[[:space:]])cookies([[:space:]]|$)"; then
    printf "${GREEN}✓${RESET} cookies command registered\n"
else
    printf "${RED}✗${RESET} cookies command not in vidscope --help\n"
    failed_steps+=("vidscope --help missing cookies")
fi

cookies_help="$(python -m uv run vidscope cookies --help 2>&1)"
printf "\n${CYAN}${BOLD}[%02d] vidscope cookies --help lists 4 subcommands${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
missing=()
for sub in set status test clear; do
    if ! echo "${cookies_help}" | grep -qE "(^|[[:space:]])${sub}([[:space:]]|$)"; then
        missing+=("${sub}")
    fi
done
if [[ "${#missing[@]}" -eq 0 ]]; then
    printf "${GREEN}✓${RESET} every cookies subcommand present\n"
else
    printf "${RED}✗${RESET} missing cookies subcommands: %s\n" "${missing[*]}"
    failed_steps+=("vidscope cookies --help")
fi

# 3. End-to-end set/status/clear cycle (no network, no real cookies)
printf "\n${CYAN}${BOLD}[%02d] cookies set/status/clear end-to-end${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
TMP_COOKIES="$(mktemp -t vidscope-test-cookies-XXXXXX.txt)"
cat > "${TMP_COOKIES}" <<'COOKIESEOF'
# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	1893456000	sessionid	abc123stub
.instagram.com	TRUE	/	FALSE	1893456000	csrftoken	def456stub
COOKIESEOF

# 1. status before — should report missing
status_before="$(python -m uv run vidscope cookies status 2>&1)"
# 2. set
set_output="$(python -m uv run vidscope cookies set "${TMP_COOKIES}" 2>&1)"
# 3. status after — should report present + 2 entries
status_after="$(python -m uv run vidscope cookies status 2>&1)"
# 4. clear
clear_output="$(python -m uv run vidscope cookies clear --yes 2>&1)"
# 5. status final — should report missing again
status_final="$(python -m uv run vidscope cookies status 2>&1)"
rm -f "${TMP_COOKIES}"
set -e

cycle_ok=true
if echo "${status_before}" | grep -qi "feature disabled"; then
    :  # ok
else
    echo "${status_before}"
    printf "${YELLOW}!${RESET} status before: expected 'feature disabled'\n"
    cycle_ok=false
fi
if echo "${set_output}" | grep -q "copied 2"; then
    :
else
    echo "${set_output}"
    printf "${YELLOW}!${RESET} set: expected 'copied 2'\n"
    cycle_ok=false
fi
if echo "${status_after}" | grep -q "2 entries"; then
    :
else
    echo "${status_after}"
    printf "${YELLOW}!${RESET} status after: expected '2 entries'\n"
    cycle_ok=false
fi
if echo "${clear_output}" | grep -q "removed"; then
    :
else
    echo "${clear_output}"
    printf "${YELLOW}!${RESET} clear: expected 'removed'\n"
    cycle_ok=false
fi
if echo "${status_final}" | grep -qi "feature disabled"; then
    :
else
    echo "${status_final}"
    printf "${YELLOW}!${RESET} status final: expected 'feature disabled'\n"
    cycle_ok=false
fi

if [[ "${cycle_ok}" = true ]]; then
    printf "${GREEN}✓${RESET} set/status/clear cycle works end-to-end\n"
else
    printf "${RED}✗${RESET} cookies cycle had failures\n"
    failed_steps+=("cookies set/status/clear cycle")
fi

# 4. Probe demo via stubbed yt_dlp
printf "\n${CYAN}${BOLD}[%02d] cookies probe demo (stubbed yt_dlp)${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
probe_output="$(python -m uv run python -c "
import yt_dlp
from yt_dlp.utils import DownloadError

# Stub YoutubeDL with a class that returns auth-required for one URL
# and ok for another, to validate both probe paths.
class StubYoutubeDL:
    def __init__(self, options):
        self._options = options
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def extract_info(self, url, *, download=True):
        if 'private' in url:
            raise DownloadError('ERROR: login required to view this content')
        return {'id': 'stub', 'title': 'Stub Reel', 'webpage_url': url}

yt_dlp.YoutubeDL = StubYoutubeDL

from vidscope.adapters.ytdlp.downloader import YtdlpDownloader
from vidscope.application.cookies import CookiesProbeUseCase
from vidscope.ports import ProbeStatus

downloader = YtdlpDownloader()

# OK case
ok_use_case = CookiesProbeUseCase(downloader=downloader, cookies_configured=False)
ok_result = ok_use_case.execute('https://www.instagram.com/reel/public/')
assert ok_result.probe.status == ProbeStatus.OK, f'expected OK, got {ok_result.probe.status}'
assert 'Stub Reel' in ok_result.interpretation
print(f'OK case: {ok_result.interpretation}')

# AUTH_REQUIRED case
auth_use_case = CookiesProbeUseCase(downloader=downloader, cookies_configured=True)
auth_result = auth_use_case.execute('https://www.instagram.com/reel/private/')
assert auth_result.probe.status == ProbeStatus.AUTH_REQUIRED, f'expected AUTH_REQUIRED, got {auth_result.probe.status}'
assert 'expired' in auth_result.interpretation
print(f'AUTH case: {auth_result.interpretation}')

print('PROBE DEMO OK')
" 2>&1)"
probe_exit=$?
set -e
echo "${probe_output}"

if [[ "${probe_exit}" -eq 0 ]] && echo "${probe_output}" | grep -q "PROBE DEMO OK"; then
    printf "${GREEN}✓${RESET} probe handles OK + AUTH_REQUIRED via stubbed yt_dlp\n"
else
    printf "${RED}✗${RESET} probe demo failed (exit ${probe_exit})\n"
    failed_steps+=("cookies probe demo")
fi

# 5. CookieAuthError detection in vidscope add error path
printf "\n${CYAN}${BOLD}[%02d] CookieAuthError raised on auth-marker yt_dlp errors${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
auth_error_output="$(python -m uv run python -c "
from yt_dlp.utils import DownloadError, ExtractorError

from vidscope.adapters.ytdlp.downloader import (
    _translate_download_error,
    _translate_extractor_error,
)
from vidscope.domain import CookieAuthError, IngestError

# Cookie auth marker → CookieAuthError
err1 = _translate_download_error(
    DownloadError('ERROR: login required to view this content'),
    'https://www.instagram.com/reel/abc/',
)
assert isinstance(err1, CookieAuthError), f'expected CookieAuthError, got {type(err1).__name__}'
assert 'vidscope cookies test' in str(err1)
print(f'download path: CookieAuthError with vidscope cookies test mention')

err2 = _translate_extractor_error(
    ExtractorError('Sign in to confirm you are not a bot'),
    'https://www.youtube.com/shorts/xyz',
)
assert isinstance(err2, CookieAuthError)
print(f'extractor path: CookieAuthError')

# Non-auth error → plain IngestError (NOT CookieAuthError)
err3 = _translate_download_error(
    DownloadError('ERROR: connection refused'),
    'https://example.com/x',
)
assert isinstance(err3, IngestError)
assert not isinstance(err3, CookieAuthError)
print(f'non-auth: plain IngestError (no CookieAuthError)')

print('AUTH ERROR OK')
" 2>&1)"
auth_error_exit=$?
set -e
echo "${auth_error_output}"

if [[ "${auth_error_exit}" -eq 0 ]] && echo "${auth_error_output}" | grep -q "AUTH ERROR OK"; then
    printf "${GREEN}✓${RESET} CookieAuthError detection works in both paths\n"
else
    printf "${RED}✗${RESET} CookieAuthError detection failed\n"
    failed_steps+=("CookieAuthError detection")
fi

# 6. MCP subprocess integration tests (still part of project)
if [[ "${SKIP_INTEGRATION}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[MCP subprocess integration] skipped${RESET}\n"
else
    run_step "MCP subprocess integration tests" \
        python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v
fi

# Summary
printf "\n${BOLD}=== M005 Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ M005 VERIFICATION PASSED${RESET}\n"
    printf "${DIM}Cookies UX complete: vidscope cookies set/status/test/clear + CookieAuthError remediation. Instagram Reels now usable in 4 commands.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ M005 VERIFICATION FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
