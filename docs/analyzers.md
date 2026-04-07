# Analyzer providers

VidScope ships with **two zero-cost defaults** and **five pluggable LLM
providers**. Switch between them by setting the `VIDSCOPE_ANALYZER`
environment variable. The default is `heuristic` — pure-Python, zero
cost, no network calls. Suitable for everything VidScope was designed
to do out of the box.

LLM providers are opt-in. They never run automatically: you choose them
with `VIDSCOPE_ANALYZER=<name>` and provide an API key via a per-provider
env var. The pipeline doesn't change — only the `Analysis` row in the
database carries a different `provider` field.

## Quick reference

| Name         | Cost          | Env var                          | Default model                                  | Signup                                              |
|--------------|---------------|----------------------------------|------------------------------------------------|-----------------------------------------------------|
| `heuristic`  | free          | _(none — default)_               | _(stdlib)_                                     | _n/a_                                               |
| `stub`       | free          | _(none — tests only)_            | _(no-op)_                                      | _n/a_                                               |
| `groq`       | **free tier** | `VIDSCOPE_GROQ_API_KEY`          | `llama-3.1-8b-instant`                         | <https://console.groq.com>                          |
| `nvidia`     | **free tier** | `VIDSCOPE_NVIDIA_API_KEY`        | `meta/llama-3.1-8b-instruct`                   | <https://build.nvidia.com>                          |
| `openrouter` | **free tier** | `VIDSCOPE_OPENROUTER_API_KEY`    | `meta-llama/llama-3.3-70b-instruct:free`       | <https://openrouter.ai>                             |
| `openai`     | paid (with starter credits) | `VIDSCOPE_OPENAI_API_KEY` | `gpt-4o-mini`                                  | <https://platform.openai.com>                       |
| `anthropic`  | paid          | `VIDSCOPE_ANTHROPIC_API_KEY`     | `claude-haiku-4-5`                             | <https://console.anthropic.com>                     |

Each provider also accepts a `VIDSCOPE_<PROVIDER>_MODEL` env var to
override the default model.

## How analyzers fit into the pipeline

The pipeline runs five stages: ingest → transcribe → frames → analyze → index.
Only the **analyze** stage talks to the analyzer. Every analyzer
implements the same `Analyzer` Protocol:

```python
class Analyzer(Protocol):
    @property
    def provider_name(self) -> str: ...
    def analyze(self, transcript: Transcript) -> Analysis: ...
```

The `Analysis` row written to the database always has the same shape
(`provider`, `language`, `keywords`, `topics`, `score`, `summary`)
regardless of which analyzer produced it. So you can swap providers
mid-project — old rows keep their old `provider` value and new rows
get the new one. There's no migration.

## The default: heuristic

```bash
# Already the default. No env var needed.
vidscope add https://www.youtube.com/shorts/abc123
```

The heuristic analyzer is pure stdlib (regex + Counter). It produces:

- `keywords`: top 8 most frequent non-stopword tokens, lowercased
- `topics`: top 3 keywords as a quick proxy
- `score`: composite of text length, vocabulary diversity, and segment count, normalized 0-100
- `summary`: first 200 characters of `full_text`, truncated at the last space

Zero cost. Zero network. Perfect for the baseline. Use this until you
have a specific reason to upgrade.

## LLM providers

All five LLM providers share the same prompt template and the same
output schema. Switching between them changes the underlying model and
the cost — not the database shape.

### Groq

```bash
# Sign up at console.groq.com (no credit card)
export VIDSCOPE_GROQ_API_KEY=gsk_...
export VIDSCOPE_ANALYZER=groq

vidscope add https://www.youtube.com/shorts/abc123
vidscope show abc123
# → analysis row with provider='groq'
```

**Free tier**: 30 requests/minute, 14 400 requests/day on `llama-3.1-8b-instant`.
No credit card required. Genuinely free for prototyping. Hardware-accelerated
inference via Groq's LPU chips — typically 500+ tokens/second.

**Default model**: `llama-3.1-8b-instant`. Override with `VIDSCOPE_GROQ_MODEL`,
e.g. `llama-3.3-70b-versatile` for better quality at lower throughput.

### NVIDIA Build

```bash
# Sign up at build.nvidia.com (NVIDIA Developer Program, free)
export VIDSCOPE_NVIDIA_API_KEY=nvapi-...
export VIDSCOPE_ANALYZER=nvidia

vidscope add https://www.youtube.com/shorts/abc123
```

**Free tier**: 1 000 inference credits at signup. Larger models consume
more credits per request. Once exhausted, you need to upgrade.

**Default model**: `meta/llama-3.1-8b-instruct`. Override with
`VIDSCOPE_NVIDIA_MODEL`. The catalog includes Llama, Mistral, DeepSeek,
GLM, and NVIDIA's own Nemotron family — see the model picker on
build.nvidia.com.

API keys are prefixed `nvapi-`. Endpoint:
`https://integrate.api.nvidia.com/v1/chat/completions` (OpenAI-compatible).

### OpenRouter

```bash
# Sign up at openrouter.ai
export VIDSCOPE_OPENROUTER_API_KEY=sk-or-...
export VIDSCOPE_ANALYZER=openrouter

vidscope add https://www.youtube.com/shorts/abc123
```

**Free tier**: 50 requests/day on free-tier models without credits, 1 000/day
once you've purchased at least $10 in credits. 29+ models tagged `:free`
including Llama 3.3 70B, NVIDIA Nemotron, OpenAI GPT-OSS 120B, Google Gemma 3.

**Default model**: `meta-llama/llama-3.3-70b-instruct:free`. The `:free`
suffix is OpenRouter's convention for the no-cost variants. Override with
`VIDSCOPE_OPENROUTER_MODEL` to pick another model from the catalog.

VidScope sends optional `HTTP-Referer` and `X-Title` headers so it shows up
on the OpenRouter leaderboards. No personal data leaks — just the project name.

### OpenAI

```bash
# Sign up at platform.openai.com
export VIDSCOPE_OPENAI_API_KEY=sk-...
export VIDSCOPE_ANALYZER=openai

vidscope add https://www.youtube.com/shorts/abc123
```

**Cost**: New accounts receive a small amount of free credits (historically
$5-18, varies). Once exhausted, pay-per-token. `gpt-4o-mini` is OpenAI's
cheapest production model and is more than enough for short transcript
analysis — typically a fraction of a cent per video.

**Default model**: `gpt-4o-mini`. Override with `VIDSCOPE_OPENAI_MODEL`,
e.g. `gpt-4o` for higher quality.

### Anthropic

```bash
# Sign up at console.anthropic.com
export VIDSCOPE_ANTHROPIC_API_KEY=sk-ant-...
export VIDSCOPE_ANALYZER=anthropic

vidscope add https://www.youtube.com/shorts/abc123
```

**Cost**: Pay-per-token. New accounts receive starter credits. Claude
Haiku 4.5 is Anthropic's cheapest model and is well-suited to short
transcripts.

**Default model**: `claude-haiku-4-5`. Override with `VIDSCOPE_ANTHROPIC_MODEL`,
e.g. `claude-sonnet-4-6` for higher quality.

**Important — native API, not the compatibility layer**: VidScope's
`AnthropicAnalyzer` targets Anthropic's native `/v1/messages` endpoint,
NOT the OpenAI-compatibility layer at `/v1/chat/completions`. Anthropic's
own docs describe the compatibility layer as "primarily intended to test
and compare model capabilities, and is not considered a long-term or
production-ready solution." We use the native API to avoid that caveat.

Auth uses the `x-api-key` header (Anthropic's native convention) plus
the required `anthropic-version: 2023-06-01` header.

## Verifying your setup

```bash
vidscope doctor
```

This now shows a row for the active analyzer:

```
analyzer    ok   heuristic (default, zero cost)
```

or, with an LLM provider configured:

```
analyzer    ok   groq (LLM key present)
```

or, when something is wrong:

```
analyzer    fail groq: VIDSCOPE_GROQ_API_KEY not set
```

The remediation block underneath the table tells you exactly what to do.

## Switching providers mid-project

Yes, you can. Existing `Analysis` rows in the database keep their
original `provider` value — there's no migration. New ingests use the
new provider. You can mix providers across videos. Re-analyzing the
same video with a different provider isn't a supported command yet —
the workaround is to delete the row directly from `vidscope.db` and
re-run `vidscope add <url>`, which will go through the analyze stage
again with the currently-configured provider.

## Adding a new provider

VidScope's analyzer architecture is **one file per provider**. To add a
new LLM provider, you need exactly:

1. A new file at `src/vidscope/adapters/llm/<name>.py` containing a class
   that implements the `Analyzer` Protocol (`provider_name` property +
   `analyze(transcript) -> Analysis` method).
2. A factory function in `src/vidscope/infrastructure/analyzer_registry.py`
   that reads the env vars, validates the API key, and constructs the adapter.
3. A test file at `tests/unit/adapters/llm/test_<name>.py` using
   `httpx.MockTransport`.

For OpenAI-compatible endpoints (anything that exposes `POST /chat/completions`
with the OpenAI request schema), the existing
`vidscope.adapters.llm._base.run_openai_compatible` helper does most of the
work — your adapter file ends up around 50 lines. See `groq.py` or `openai.py`
as a reference.

For non-OpenAI-compatible APIs (e.g. native Anthropic, Bedrock, Cohere), you'll
need to write the request/response shape yourself but you can still reuse
`_base.parse_llm_json`, `_base.make_analysis`, `_base.call_with_retry`, and
`_base.LlmCallContext`. See `anthropic.py` as a reference.

The `llm-never-imports-other-adapters` import-linter contract enforces
that your new file only imports `_base.py` + domain. No surprises.

## Costs and quotas — comparison table

| Provider     | Free / monthly | Pay-per-use after | Best for |
|--------------|----------------|-------------------|----------|
| `heuristic`  | unlimited      | n/a               | Default — zero cost, zero setup |
| `groq`       | 14 400 req/day | n/a (free tier persistent) | Best free LLM tier, fastest inference |
| `openrouter` | 50-1000 req/day | $10 minimum credits | Try multiple models from one key |
| `nvidia`     | 1000 credits   | upgrade required  | Access to NVIDIA-optimized models |
| `openai`     | small starter credit | yes              | Highest model quality, mature API |
| `anthropic`  | small starter credit | yes              | Best reasoning, longest context |

Quotas current as of April 2026. Always check the provider's current
pricing page before relying on free-tier numbers — they can change.

## Privacy notes

- **Heuristic**: nothing leaves your machine.
- **All LLM providers**: each transcript text is sent to the provider's
  servers as part of the analysis request. Free-tier providers (especially
  free `:free` models on OpenRouter) may use your prompts for training
  unless you opt out. If your transcripts contain anything sensitive,
  stay on `heuristic` or use a paid provider with a no-training agreement
  (Groq, OpenAI, Anthropic all offer this on paid tiers).
- **No keys are logged**. VidScope's logging surfaces include only
  provider names and HTTP status codes — never the API key value.
