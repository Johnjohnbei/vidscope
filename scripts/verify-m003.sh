#!/usr/bin/env bash
# Final M003 milestone verification — the authoritative "is M003 done" signal.
#
# Runs every quality gate, the full unit suite, then performs a deterministic
# end-to-end watchlist demo: seeds an account directly, monkeypatches
# list_channel_videos to return preset entries, runs `vidscope watch refresh`,
# asserts new videos were ingested, then runs refresh again and asserts
# idempotence.
#
# Usage:
#   bash scripts/verify-m003.sh                    # full run
#   bash scripts/verify-m003.sh --skip-integration # skip subprocess MCP tests
#
# The demo does NOT hit the real network so the script is reproducible
# in CI. Manual live validation: `vidscope watch add https://www.youtube.com/@YouTube`
# followed by `vidscope watch refresh`.

set -euo pipefail

SKIP_INTEGRATION=false
for arg in "$@"; do
    case "${arg}" in
        --skip-integration) SKIP_INTEGRATION=true ;;
        -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-m003-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT
export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

printf "\n${BOLD}=== M003 Final Verification ===${RESET}\n"
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

# 2. CLI smoke — vidscope watch is registered
help_output="$(python -m uv run vidscope --help 2>&1)"
printf "\n${CYAN}${BOLD}[%02d] vidscope --help lists watch sub-application${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
if echo "${help_output}" | grep -qE "(^|[[:space:]])watch([[:space:]]|$)"; then
    printf "${GREEN}✓${RESET} watch command registered\n"
else
    printf "${RED}✗${RESET} watch command not in vidscope --help\n"
    failed_steps+=("vidscope --help missing watch")
fi

watch_help="$(python -m uv run vidscope watch --help 2>&1)"
printf "\n${CYAN}${BOLD}[%02d] vidscope watch --help lists 4 subcommands${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))
missing=()
for sub in add list remove refresh; do
    if ! echo "${watch_help}" | grep -qE "(^|[[:space:]])${sub}([[:space:]]|$)"; then
        missing+=("${sub}")
    fi
done
if [[ "${#missing[@]}" -eq 0 ]]; then
    printf "${GREEN}✓${RESET} every watch subcommand present\n"
else
    printf "${RED}✗${RESET} missing watch subcommands: %s\n" "${missing[*]}"
    failed_steps+=("vidscope watch --help")
fi

# 3. MCP subprocess integration tests (still part of project)
if [[ "${SKIP_INTEGRATION}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[MCP subprocess integration] skipped${RESET}\n"
else
    run_step "MCP subprocess integration tests" \
        python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v
fi

# 4. End-to-end watchlist refresh demo (deterministic, no network)
printf "\n${CYAN}${BOLD}[%02d] watchlist refresh end-to-end demo${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
demo_output="$(python -m uv run python -c "
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from vidscope.adapters.ytdlp.downloader import YtdlpDownloader
from vidscope.application.watchlist import (
    AddWatchedAccountUseCase,
    ListWatchedAccountsUseCase,
    RefreshWatchlistUseCase,
)
from vidscope.domain import PlatformId
from vidscope.infrastructure.container import build_container
from vidscope.ports import ChannelEntry

# Stub yt_dlp YoutubeDL so the pipeline can complete without real network
import yt_dlp
class FakeYoutubeDL:
    def __init__(self, options):
        self._options = options
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def extract_info(self, url, *, download=True):
        outtmpl = str(self._options.get('outtmpl', ''))
        platform_id = url.rsplit('=', 1)[-1] or 'm003-stub'
        dest = Path(outtmpl.replace('%(id)s', platform_id).replace('%(ext)s', 'mp4'))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b'fake content for m003 demo')
        return {
            'id': platform_id,
            'extractor_key': 'Youtube',
            'webpage_url': url,
            'title': f'M003 demo video {platform_id}',
            'uploader': 'Demo Author',
            'duration': 12.5,
            'upload_date': '20260401',
            'view_count': 42,
            'requested_downloads': [{'filepath': str(dest)}],
        }
yt_dlp.YoutubeDL = FakeYoutubeDL

# Stub faster_whisper
import faster_whisper
class FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text
class FakeInfo:
    language = 'en'
    language_probability = 0.99
class FakeWhisperModel:
    def __init__(self, *a, **kw):
        pass
    def transcribe(self, media_path, **kwargs):
        return iter([FakeSegment(0.0, 1.0, 'demo m003')]), FakeInfo()
faster_whisper.WhisperModel = FakeWhisperModel

# Stub ffmpeg
from vidscope.adapters.ffmpeg import frame_extractor as fe_module
import shutil
fe_module.shutil.which = lambda name: '/fake/ffmpeg'
class FakeCompleted:
    returncode = 0
    stdout = ''
    stderr = ''
def fake_run(cmd, **kw):
    out_template = cmd[-1]
    out_dir = Path(out_template).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        (out_dir / f'frame_{i:04d}.jpg').write_bytes(b'fake jpg')
    return FakeCompleted()
fe_module.subprocess.run = fake_run

# Stub list_channel_videos to return 2 entries
def fake_list_channel_videos(self, url, *, limit=10):
    return [
        ChannelEntry(
            platform_id=PlatformId('m003-v1'),
            url='https://www.youtube.com/watch?v=m003-v1',
        ),
        ChannelEntry(
            platform_id=PlatformId('m003-v2'),
            url='https://www.youtube.com/watch?v=m003-v2',
        ),
    ]
YtdlpDownloader.list_channel_videos = fake_list_channel_videos

container = build_container()

# Add the account
adder = AddWatchedAccountUseCase(unit_of_work_factory=container.unit_of_work)
add_result = adder.execute('https://www.youtube.com/@YouTube')
assert add_result.success, f'add failed: {add_result.message}'
print(f'added: {add_result.account.platform.value}/{add_result.account.handle}')

# First refresh — should ingest 2 new videos
refresh = RefreshWatchlistUseCase(
    unit_of_work_factory=container.unit_of_work,
    pipeline_runner=container.pipeline_runner,
    downloader=container.downloader,
    clock=container.clock,
)
first = refresh.execute()
print(f'first refresh: checked={first.accounts_checked} new={first.new_videos_ingested} errors={len(first.errors)}')
assert first.accounts_checked == 1, 'should check 1 account'
assert first.new_videos_ingested == 2, f'should ingest 2 videos, got {first.new_videos_ingested}'
assert len(first.errors) == 0, f'unexpected errors: {first.errors}'

# Second refresh — must be idempotent (0 new)
second = refresh.execute()
print(f'second refresh: checked={second.accounts_checked} new={second.new_videos_ingested}')
assert second.new_videos_ingested == 0, f'second refresh should be idempotent, got {second.new_videos_ingested}'

# List the accounts
lister = ListWatchedAccountsUseCase(unit_of_work_factory=container.unit_of_work)
listed = lister.execute()
print(f'listed: {listed.total} account(s)')
assert listed.total == 1
assert listed.accounts[0].last_checked_at is not None, 'last_checked_at should be set after refresh'

print('M003 DEMO OK')
" 2>&1)"
demo_exit=$?
set -e
echo "${demo_output}"

if [[ "${demo_exit}" -eq 0 ]] && echo "${demo_output}" | grep -q "M003 DEMO OK"; then
    printf "${GREEN}✓${RESET} watchlist refresh demo passed\n"
else
    printf "${RED}✗${RESET} watchlist refresh demo failed (exit ${demo_exit})\n"
    failed_steps+=("watchlist refresh demo")
fi

# 5. Watchlist DB rows actually persisted
printf "\n${CYAN}${BOLD}[%02d] watch_refreshes table has at least one row${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
db_check="$(python -m uv run python -c "
from vidscope.infrastructure.container import build_container
container = build_container()
with container.unit_of_work() as uow:
    rows = uow.watch_refreshes.list_recent(limit=10)
    print(f'watch_refreshes count: {len(rows)}')
    if rows:
        print(f'last refresh: accounts={rows[0].accounts_checked} new={rows[0].new_videos_ingested}')
" 2>&1)"
db_exit=$?
set -e
echo "${db_check}"

if [[ "${db_exit}" -eq 0 ]] && echo "${db_check}" | grep -q "watch_refreshes count: 2"; then
    printf "${GREEN}✓${RESET} watch_refreshes table populated by demo\n"
else
    printf "${RED}✗${RESET} watch_refreshes count mismatch (expected 2)\n"
    failed_steps+=("watch_refreshes persistence")
fi

# Summary
printf "\n${BOLD}=== M003 Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ M003 VERIFICATION PASSED${RESET}\n"
    printf "${DIM}Watchlist + scheduled refresh ready. Accounts can be tracked across YouTube/TikTok/Instagram.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ M003 VERIFICATION FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
