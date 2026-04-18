"""Shared LLM adapter helpers — prompt template, JSON parser, retry.

Each concrete provider (Groq, NVIDIA Build, OpenRouter, OpenAI,
Anthropic) reuses these helpers to stay under ~100 lines.

Public surface
--------------

- :func:`build_messages` — system + user message tuple asking for
  JSON output. Same prompt across every provider so output schemas
  match.
- :func:`parse_llm_json` — extract a JSON object from raw model
  output. Handles bare JSON, ```` ```json ... ``` ```` fenced JSON,
  ```` ``` ... ``` ```` un-tagged fences, and trailing prose.
- :func:`call_with_retry` — exponential-backoff retry loop for HTTP
  calls. Retries 429 + 5xx, fails fast on 4xx, fails fast on
  malformed responses.
- :func:`make_analysis` — turn parsed JSON dict + transcript into a
  domain :class:`Analysis` instance.
- :class:`LlmCallContext` — small bag of arguments threaded through
  the retry helper.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from vidscope.domain import (
    Analysis,
    AnalysisError,
    ContentType,
    Language,
    SentimentLabel,
    Transcript,
)

__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS",
    "LlmCallContext",
    "build_messages",
    "call_with_retry",
    "make_analysis",
    "parse_llm_json",
    "run_openai_compatible",
]


_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_REQUEST_TIMEOUT_SECONDS: float = 30.0
DEFAULT_MAX_ATTEMPTS: int = 3
_BACKOFF_BASE_SECONDS: float = 1.0
_BACKOFF_CAP_SECONDS: float = 8.0


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are a video-analysis assistant. Given the transcript of a "
    "short-form vertical video, return a strict JSON object with "
    "EXACTLY these keys and nothing else (no markdown, no prose):\n"
    '  "language": ISO 639-1 lowercase 2-letter code (e.g. "en" or "fr")\n'
    '  "keywords": array of 5-10 lowercase keywords from the transcript\n'
    '  "topics": array of 1-3 short topic phrases (2-4 words each)\n'
    '  "verticals": array of 0-5 lowercase vertical slugs that best '
    "describe the content (e.g. tech, beauty, fitness, finance, food, "
    "travel, gaming, education, fashion, music, productivity, ai)\n"
    '  "score": integer 0-100 measuring overall content quality and richness\n'
    '  "information_density": integer 0-100 measuring meaningful-content ratio\n'
    '  "actionability": integer 0-100 measuring how actionable the advice is '
    "(0 = pure entertainment, 100 = step-by-step tutorial)\n"
    '  "novelty": integer 0-100 measuring how novel/original the ideas are\n'
    '  "production_quality": integer 0-100 measuring pacing/clarity/structure '
    "(not video-quality — transcript-inferable signals only)\n"
    '  "sentiment": one of "positive", "negative", "neutral", "mixed"\n'
    '  "is_sponsored": boolean — true if the transcript signals a paid '
    'partnership (phrases like "sponsored by", "in partnership with", '
    '"#ad", "use code", "affiliate"), else false\n'
    '  "content_type": one of "tutorial", "review", "vlog", "news", '
    '"story", "opinion", "comedy", "educational", "promo", "unknown"\n'
    '  "reasoning": 2-3 short sentences explaining the verdict '
    "(why this content_type, what drove the sentiment, any sponsorship cue). "
    "Max 500 characters.\n"
    '  "summary": one-sentence factual summary, max 200 characters\n'
    "Numeric fields must be integers in [0, 100]. All strings must be "
    "lowercase except where noted. Return bare JSON — no code fences, "
    "no explanations, no preamble."
)


def build_messages(transcript: Transcript) -> list[dict[str, str]]:
    """Return the OpenAI-compatible chat messages for ``transcript``.

    Every provider in :mod:`vidscope.adapters.llm` uses the same
    messages list so the JSON output schema is identical across
    providers — keeps :func:`make_analysis` simple.
    """
    text = (transcript.full_text or "").strip()
    if not text:
        text = "[no speech detected]"

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Transcript language hint: {transcript.language.value}\n"
                f"Transcript:\n{text}"
            ),
        },
    ]


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


_FENCED_JSON = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE
)
_FIRST_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Extract a JSON object from a model's raw text output.

    Tries, in order:

    1. Bare JSON (the model followed instructions)
    2. Markdown-fenced JSON (```json { ... } ``` or ``` { ... } ```)
    3. First { ... } substring (handles trailing/leading prose)

    Raises
    ------
    AnalysisError
        If no parseable JSON object is found anywhere in ``raw``.
    """
    if not raw or not raw.strip():
        raise AnalysisError("LLM returned empty response", retryable=False)

    text = raw.strip()

    # 1. Bare JSON
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        result = None
    if isinstance(result, dict):
        return result

    # 2. Markdown-fenced JSON
    fenced = _FENCED_JSON.search(text)
    if fenced is not None:
        try:
            result = json.loads(fenced.group(1))
        except (json.JSONDecodeError, ValueError) as exc:
            raise AnalysisError(
                f"LLM returned malformed JSON inside markdown fence: {exc}",
                retryable=False,
            ) from exc
        if isinstance(result, dict):
            return result

    # 3. First { ... } substring
    obj_match = _FIRST_OBJECT.search(text)
    if obj_match is not None:
        candidate = obj_match.group(0)
        try:
            result = json.loads(candidate)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AnalysisError(
                f"LLM returned malformed JSON substring: {exc}",
                retryable=False,
            ) from exc
        if isinstance(result, dict):
            return result

    raise AnalysisError(
        f"LLM returned no parseable JSON object (got {len(raw)} chars)",
        retryable=False,
    )


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LlmCallContext:
    """Bag of arguments for one LLM HTTP request."""

    method: str
    url: str
    headers: dict[str, str]
    json_body: dict[str, Any]
    timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS


def call_with_retry(
    client: httpx.Client,
    ctx: LlmCallContext,
    *,
    sleep: Any = time.sleep,
) -> httpx.Response:
    """Execute one HTTP call with exponential-backoff retry on transient failures.

    Retries on:

    - HTTP 429 (rate limit)
    - HTTP 5xx (server error)
    - :class:`httpx.TimeoutException`
    - :class:`httpx.TransportError`

    Fails fast on:

    - HTTP 4xx other than 429
    - Any other exception

    The ``sleep`` parameter is injectable so tests can pass a no-op.

    Raises
    ------
    AnalysisError
        On unrecoverable failures or exhausted retries.
    """
    last_error: str | None = None
    for attempt in range(1, ctx.max_attempts + 1):
        try:
            response = client.request(
                method=ctx.method,
                url=ctx.url,
                headers=ctx.headers,
                json=ctx.json_body,
                timeout=ctx.timeout,
            )
        except httpx.TimeoutException as exc:
            last_error = f"timeout after {ctx.timeout}s"
            _logger.warning(
                "LLM call attempt %d/%d timed out: %s",
                attempt,
                ctx.max_attempts,
                exc,
            )
            if attempt == ctx.max_attempts:
                raise AnalysisError(
                    f"LLM request timed out after {ctx.max_attempts} attempts",
                    cause=exc,
                    retryable=True,
                ) from exc
            sleep(_backoff_seconds(attempt))
            continue
        except httpx.TransportError as exc:
            last_error = f"transport: {exc}"
            _logger.warning(
                "LLM call attempt %d/%d transport error: %s",
                attempt,
                ctx.max_attempts,
                exc,
            )
            if attempt == ctx.max_attempts:
                raise AnalysisError(
                    f"LLM transport failed after {ctx.max_attempts} attempts: {exc}",
                    cause=exc,
                    retryable=True,
                ) from exc
            sleep(_backoff_seconds(attempt))
            continue

        # Got an HTTP response — inspect status
        if 200 <= response.status_code < 300:
            return response

        if response.status_code == 429 or response.status_code >= 500:
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            _logger.warning(
                "LLM call attempt %d/%d returned %d: %s",
                attempt,
                ctx.max_attempts,
                response.status_code,
                response.text[:200],
            )
            if attempt == ctx.max_attempts:
                raise AnalysisError(
                    f"LLM returned {response.status_code} after "
                    f"{ctx.max_attempts} attempts: {response.text[:200]}",
                    retryable=True,
                )
            sleep(_backoff_seconds(attempt))
            continue

        # 4xx other than 429: fail fast
        raise AnalysisError(
            f"LLM returned {response.status_code}: {response.text[:200]}",
            retryable=False,
        )

    # Defensive: loop exited without return or raise
    raise AnalysisError(
        f"LLM call exhausted retries: {last_error or 'unknown'}",
        retryable=True,
    )


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff: 1s, 2s, 4s, ... capped at 8s."""
    multiplier: float = float(2 ** (attempt - 1))
    return min(_BACKOFF_BASE_SECONDS * multiplier, _BACKOFF_CAP_SECONDS)


# ---------------------------------------------------------------------------
# JSON → Analysis
# ---------------------------------------------------------------------------


def run_openai_compatible(
    *,
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    transcript: Transcript,
    provider_name: str,
    timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    extra_headers: dict[str, str] | None = None,
    use_json_response_format: bool = True,
) -> Analysis:
    """Run a chat-completion call against an OpenAI-compatible endpoint.

    Used by the Groq, NVIDIA Build, OpenRouter, and OpenAI adapters
    — every one of those exposes ``POST {base_url}/chat/completions``
    with the OpenAI request schema and the same response shape.

    Anthropic does NOT use this helper because it expects the native
    ``/v1/messages`` schema with a different request and response
    layout — see :mod:`vidscope.adapters.llm.anthropic`.

    Parameters
    ----------
    client
        :class:`httpx.Client` to use. Caller owns its lifecycle.
    base_url
        Provider base URL ending with ``/v1`` (no trailing slash).
    api_key
        Authentication token. Sent as ``Bearer <token>``.
    model
        Model identifier passed in the request body.
    transcript
        Transcript to analyze.
    provider_name
        Name written into :attr:`Analysis.provider`.
    timeout
        Per-request timeout in seconds.
    extra_headers
        Optional additional headers (e.g. OpenRouter's ``X-Title``).
    use_json_response_format
        Whether to send ``response_format: {type: 'json_object'}``.
        Some providers (older NVIDIA models) reject this parameter
        — set ``False`` for those.

    Raises
    ------
    AnalysisError
        On any failure: HTTP error, malformed response, JSON parse
        failure.
    """
    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    body: dict[str, Any] = {
        "model": model,
        "messages": build_messages(transcript),
        "temperature": 0.2,
        "max_tokens": 512,
    }
    if use_json_response_format:
        body["response_format"] = {"type": "json_object"}

    ctx = LlmCallContext(
        method="POST",
        url=f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json_body=body,
        timeout=timeout,
    )

    response = call_with_retry(client, ctx)

    try:
        payload = response.json()
    except ValueError as exc:
        raise AnalysisError(
            f"{provider_name} returned non-JSON response: {response.text[:200]}",
            cause=exc,
            retryable=False,
        ) from exc

    choices = payload.get("choices") or []
    if not choices:
        raise AnalysisError(
            f"{provider_name} response missing 'choices' field",
            retryable=False,
        )

    message = choices[0].get("message") or {}
    raw_content = message.get("content") or ""
    if not raw_content:
        raise AnalysisError(
            f"{provider_name} response missing message.content",
            retryable=False,
        )

    parsed = parse_llm_json(raw_content)
    return make_analysis(parsed, transcript, provider=provider_name)


# ---------------------------------------------------------------------------
# M010 — defensive field parsers
# ---------------------------------------------------------------------------


def _parse_score_100(value: Any) -> float | None:
    """Parse a 0-100 numeric score. Returns None for non-numeric inputs.

    Accepts int, float, or numeric string. Clamps to [0.0, 100.0].
    """
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    return max(0.0, min(100.0, num))


def _parse_sentiment(value: Any) -> SentimentLabel | None:
    """Parse a sentiment string case-insensitively. None on invalid."""
    if value is None:
        return None
    if isinstance(value, SentimentLabel):
        return value
    if not isinstance(value, str):
        return None
    try:
        return SentimentLabel(value.strip().lower())
    except ValueError:
        return None


def _parse_content_type(value: Any) -> ContentType | None:
    """Parse a content_type string case-insensitively. None on invalid."""
    if value is None:
        return None
    if isinstance(value, ContentType):
        return value
    if not isinstance(value, str):
        return None
    try:
        return ContentType(value.strip().lower())
    except ValueError:
        return None


_TRUTHY_STRINGS: frozenset[str] = frozenset({"true", "yes", "1", "t"})
_FALSY_STRINGS: frozenset[str] = frozenset({"false", "no", "0", "f"})


def _parse_bool_flag(value: Any) -> bool | None:
    """Parse a boolean flag tolerantly. None on unrecognised inputs.

    Recognises: True/False, 0/1, 'true'/'false' (case-insensitive),
    'yes'/'no', 't'/'f'. Any other value → None.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in _TRUTHY_STRINGS:
            return True
        if norm in _FALSY_STRINGS:
            return False
        return None
    return None


def _parse_verticals(value: Any, *, max_count: int = 5) -> tuple[str, ...]:
    """Parse a verticals array. Returns () for invalid input.

    Normalises to lowercase stripped strings. Deduplicates while
    preserving order. Caps at ``max_count``.
    """
    if not isinstance(value, list):
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for v in value:
        if not isinstance(v, str):
            continue
        norm = v.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
        if len(result) >= max_count:
            break
    return tuple(result)


_REASONING_MAX_CHARS: int = 500


def _parse_reasoning(value: Any) -> str | None:
    """Parse reasoning text. None for empty/non-string. Truncated at 500."""
    if value is None or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > _REASONING_MAX_CHARS:
        text = text[:_REASONING_MAX_CHARS].rstrip() + "..."
    return text


# ---------------------------------------------------------------------------
# JSON → Analysis
# ---------------------------------------------------------------------------


def make_analysis(
    parsed: dict[str, Any], transcript: Transcript, *, provider: str
) -> Analysis:
    """Convert parsed LLM JSON output into an :class:`Analysis`.

    Defensive about missing/malformed keys — falls back to safe defaults
    rather than raising. Extended in M010 to parse the 9 new fields
    (verticals, 4 score dimensions, sentiment, is_sponsored, content_type,
    reasoning). The score is clamped to [0, 100].

    Raises
    ------
    AnalysisError
        Only if the parsed object isn't a dict (caller bug).
    """
    if not isinstance(parsed, dict):
        raise AnalysisError(
            f"expected dict from parse_llm_json, got {type(parsed).__name__}",
            retryable=False,
        )

    # --- V1 fields (preserved) ---
    keywords_raw = parsed.get("keywords") or []
    if not isinstance(keywords_raw, list):
        keywords_raw = []
    keywords = tuple(
        str(k).strip().lower() for k in keywords_raw if k and str(k).strip()
    )[:10]

    topics_raw = parsed.get("topics") or []
    if not isinstance(topics_raw, list):
        topics_raw = []
    topics = tuple(
        str(t).strip() for t in topics_raw if t and str(t).strip()
    )[:3]

    score = _parse_score_100(parsed.get("score"))

    summary_raw = parsed.get("summary")
    summary: str | None
    if summary_raw is None:
        summary = None
    else:
        summary_text = str(summary_raw).strip()
        summary = summary_text[:200] if summary_text else None

    # Resolve language: prefer transcript's detected language, fall
    # back to LLM's value if transcript was unknown.
    language = transcript.language
    if language == Language.UNKNOWN:
        lang_raw = parsed.get("language")
        if lang_raw:
            try:
                language = Language(str(lang_raw).lower())
            except ValueError:
                language = Language.UNKNOWN

    # --- M010 fields (all defensive, never raise) ---
    verticals = _parse_verticals(parsed.get("verticals"))
    information_density = _parse_score_100(parsed.get("information_density"))
    actionability = _parse_score_100(parsed.get("actionability"))
    novelty = _parse_score_100(parsed.get("novelty"))
    production_quality = _parse_score_100(parsed.get("production_quality"))
    sentiment = _parse_sentiment(parsed.get("sentiment"))
    is_sponsored = _parse_bool_flag(parsed.get("is_sponsored"))
    content_type = _parse_content_type(parsed.get("content_type"))
    reasoning = _parse_reasoning(parsed.get("reasoning"))

    return Analysis(
        video_id=transcript.video_id,
        provider=provider,
        language=language,
        keywords=keywords,
        topics=topics,
        score=score,
        summary=summary,
        verticals=verticals,
        information_density=information_density,
        actionability=actionability,
        novelty=novelty,
        production_quality=production_quality,
        sentiment=sentiment,
        is_sponsored=is_sponsored,
        content_type=content_type,
        reasoning=reasoning,
    )
