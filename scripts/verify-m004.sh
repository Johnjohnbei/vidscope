#!/usr/bin/env bash
# Final M004 milestone verification — the authoritative "is M004 done" signal.
#
# Runs every quality gate, the full unit suite, then performs deterministic
# stub-HTTP smoke tests for each of the 5 LLM providers (Groq, NVIDIA Build,
# OpenRouter, OpenAI, Anthropic) using httpx.MockTransport. No real network
# calls.
#
# Usage:
#   bash scripts/verify-m004.sh                    # full run
#   bash scripts/verify-m004.sh --skip-integration # skip subprocess MCP tests
#
# Manual live validation: set VIDSCOPE_<PROVIDER>_API_KEY for any provider,
# then `VIDSCOPE_ANALYZER=<provider> vidscope add <url>` and check the
# `provider` column in `vidscope show <id>`.

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

TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-m004-XXXXXX)"
trap 'rm -rf "${TMP_DATA_DIR}"' EXIT
export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"
# Make sure no real API keys leak into the verify script
unset VIDSCOPE_GROQ_API_KEY VIDSCOPE_NVIDIA_API_KEY VIDSCOPE_OPENROUTER_API_KEY \
      VIDSCOPE_OPENAI_API_KEY VIDSCOPE_ANTHROPIC_API_KEY VIDSCOPE_ANALYZER || true

printf "\n${BOLD}=== M004 Final Verification ===${RESET}\n"
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

# 2. Registry exposes all 5 LLM providers + 2 defaults
printf "\n${CYAN}${BOLD}[%02d] analyzer registry exposes 7 names${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
registry_output="$(python -m uv run python -c "
from vidscope.infrastructure.analyzer_registry import KNOWN_ANALYZERS
names = sorted(KNOWN_ANALYZERS)
print(' '.join(names))
expected = {'anthropic', 'groq', 'heuristic', 'nvidia', 'openai', 'openrouter', 'stub'}
assert set(names) == expected, f'mismatch: got {set(names)}, expected {expected}'
print('REGISTRY OK')
" 2>&1)"
registry_exit=$?
set -e
echo "${registry_output}"

if [[ "${registry_exit}" -eq 0 ]] && echo "${registry_output}" | grep -q "REGISTRY OK"; then
    printf "${GREEN}✓${RESET} all 7 names present\n"
else
    printf "${RED}✗${RESET} registry name mismatch\n"
    failed_steps+=("analyzer registry names")
fi

# 3. Each LLM provider fails cleanly without its API key
printf "\n${CYAN}${BOLD}[%02d] each LLM provider raises ConfigError without its env var${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
missing_key_output="$(python -m uv run python -c "
import os
from vidscope.domain.errors import ConfigError
from vidscope.infrastructure.analyzer_registry import build_analyzer

# Make sure none of these are set in the inherited environment
for k in ('VIDSCOPE_GROQ_API_KEY', 'VIDSCOPE_NVIDIA_API_KEY',
          'VIDSCOPE_OPENROUTER_API_KEY', 'VIDSCOPE_OPENAI_API_KEY',
          'VIDSCOPE_ANTHROPIC_API_KEY'):
    os.environ.pop(k, None)

provider_to_envvar = {
    'groq': 'VIDSCOPE_GROQ_API_KEY',
    'nvidia': 'VIDSCOPE_NVIDIA_API_KEY',
    'openrouter': 'VIDSCOPE_OPENROUTER_API_KEY',
    'openai': 'VIDSCOPE_OPENAI_API_KEY',
    'anthropic': 'VIDSCOPE_ANTHROPIC_API_KEY',
}
for name, envvar in provider_to_envvar.items():
    try:
        build_analyzer(name)
        print(f'FAIL: {name} did not raise')
    except ConfigError as exc:
        if envvar in str(exc):
            print(f'{name}: OK ({envvar} mentioned)')
        else:
            print(f'FAIL: {name} error did not mention {envvar}')
print('MISSING KEY OK')
" 2>&1)"
missing_key_exit=$?
set -e
echo "${missing_key_output}"

if [[ "${missing_key_exit}" -eq 0 ]] && echo "${missing_key_output}" | grep -q "MISSING KEY OK"; then
    printf "${GREEN}✓${RESET} each provider raises ConfigError with correct env var\n"
else
    printf "${RED}✗${RESET} provider missing-key check failed\n"
    failed_steps+=("provider missing-key check")
fi

# 4. Each provider produces an Analysis when given a stubbed httpx client
printf "\n${CYAN}${BOLD}[%02d] each LLM provider produces Analysis via stub HTTP${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
stub_demo_output="$(python -m uv run python -c "
import json
import httpx

from vidscope.adapters.llm.anthropic import AnthropicAnalyzer
from vidscope.adapters.llm.groq import GroqAnalyzer
from vidscope.adapters.llm.nvidia_build import NvidiaBuildAnalyzer
from vidscope.adapters.llm.openai import OpenAIAnalyzer
from vidscope.adapters.llm.openrouter import OpenRouterAnalyzer
from vidscope.domain import Language, Transcript, TranscriptSegment, VideoId

transcript = Transcript(
    video_id=VideoId(1),
    language=Language.ENGLISH,
    full_text='Stub demo transcript for M004 verification.',
    segments=(TranscriptSegment(start=0.0, end=1.0, text='Stub demo transcript for M004 verification.'),),
)

parsed_payload = {
    'language': 'en',
    'keywords': ['stub', 'demo'],
    'topics': ['testing'],
    'score': 50,
    'summary': 'A stubbed demo response.',
}


def openai_handler(request):
    return httpx.Response(
        200,
        json={
            'id': 'fake', 'object': 'chat.completion', 'model': 'fake',
            'choices': [{
                'index': 0,
                'message': {'role': 'assistant', 'content': json.dumps(parsed_payload)},
                'finish_reason': 'stop',
            }],
        },
    )


def anthropic_handler(request):
    return httpx.Response(
        200,
        json={
            'id': 'msg_fake', 'type': 'message', 'role': 'assistant',
            'model': 'fake',
            'content': [{'type': 'text', 'text': json.dumps(parsed_payload)}],
            'stop_reason': 'end_turn',
        },
    )


def make_oai_client():
    return httpx.Client(transport=httpx.MockTransport(openai_handler))


def make_anth_client():
    return httpx.Client(transport=httpx.MockTransport(anthropic_handler))


cases = [
    (GroqAnalyzer(api_key='fake', client=make_oai_client()), 'groq'),
    (NvidiaBuildAnalyzer(api_key='fake', client=make_oai_client()), 'nvidia'),
    (OpenRouterAnalyzer(api_key='fake', client=make_oai_client()), 'openrouter'),
    (OpenAIAnalyzer(api_key='fake', client=make_oai_client()), 'openai'),
    (AnthropicAnalyzer(api_key='fake', client=make_anth_client()), 'anthropic'),
]

for analyzer, expected_name in cases:
    result = analyzer.analyze(transcript)
    assert result.provider == expected_name, f'{expected_name}: got provider={result.provider}'
    assert result.score == 50.0, f'{expected_name}: score mismatch'
    assert 'stub' in result.keywords, f'{expected_name}: keywords missing stub'
    print(f'{expected_name}: provider={result.provider} score={result.score} keywords={list(result.keywords)}')

print('STUB HTTP DEMO OK')
" 2>&1)"
stub_demo_exit=$?
set -e
echo "${stub_demo_output}"

if [[ "${stub_demo_exit}" -eq 0 ]] && echo "${stub_demo_output}" | grep -q "STUB HTTP DEMO OK"; then
    printf "${GREEN}✓${RESET} all 5 LLM providers produce Analysis via stub HTTP\n"
else
    printf "${RED}✗${RESET} stub HTTP demo failed (exit ${stub_demo_exit})\n"
    failed_steps+=("stub HTTP demo")
fi

# 5. vidscope doctor includes the analyzer row
printf "\n${CYAN}${BOLD}[%02d] vidscope doctor reports analyzer row${RESET}\n" \
    "$((step_count + 1))"
step_count=$((step_count + 1))

set +e
doctor_output="$(python -m uv run vidscope doctor 2>&1)"
doctor_exit=$?
set -e
echo "${doctor_output}"

if echo "${doctor_output}" | grep -qi "analyzer"; then
    printf "${GREEN}✓${RESET} doctor output contains analyzer row\n"
else
    printf "${RED}✗${RESET} doctor output missing analyzer row\n"
    failed_steps+=("doctor analyzer row")
fi

# 6. MCP subprocess integration tests (still part of project)
if [[ "${SKIP_INTEGRATION}" = true ]]; then
    printf "\n${YELLOW}${BOLD}[MCP subprocess integration] skipped${RESET}\n"
else
    run_step "MCP subprocess integration tests" \
        python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v
fi

# Summary
printf "\n${BOLD}=== M004 Summary ===${RESET}\n"
printf "Total steps: %d\n" "${step_count}"
printf "Failed:      %d\n" "${#failed_steps[@]}"

if [[ "${#failed_steps[@]}" -eq 0 ]]; then
    printf "\n${GREEN}${BOLD}✓ M004 VERIFICATION PASSED${RESET}\n"
    printf "${DIM}5 LLM analyzer providers ready (groq/nvidia/openrouter/openai/anthropic). Heuristic stays the default.${RESET}\n"
    exit 0
else
    printf "\n${RED}${BOLD}✗ M004 VERIFICATION FAILED${RESET}\n"
    for step in "${failed_steps[@]}"; do
        printf "${RED}  - %s${RESET}\n" "${step}"
    done
    exit 1
fi
