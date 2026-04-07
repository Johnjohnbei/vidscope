"""AnthropicAnalyzer — concrete LLM analyzer using Anthropic's native API.

Anthropic's native API (``POST https://api.anthropic.com/v1/messages``)
has a different shape from OpenAI's chat-completion endpoint:

- Top-level ``system`` field instead of a ``role: system`` message
- ``max_tokens`` is REQUIRED
- No ``response_format`` parameter — JSON mode is achieved by
  asking the model to output JSON in the prompt and parsing it
  defensively
- Response is ``content: [{type: 'text', text: '...'}]`` instead of
  ``choices: [{message: {content: '...'}}]``
- Auth uses ``x-api-key`` header (not ``Authorization: Bearer``)
- Requires ``anthropic-version`` header

Anthropic does ship an OpenAI-compatibility layer at
``https://api.anthropic.com/v1/chat/completions`` but their own docs
state it is primarily intended to test and compare model
capabilities, and is not considered a long-term or production-ready
solution. We use the native ``/v1/messages`` instead so the adapter
isn't carrying production debt from day 1.

This file reuses :func:`vidscope.adapters.llm._base.parse_llm_json`,
:func:`vidscope.adapters.llm._base.make_analysis`,
:func:`vidscope.adapters.llm._base.call_with_retry`, and
:func:`vidscope.adapters.llm._base.build_messages` (then strips the
system message back out and routes it through the top-level field).
"""

from __future__ import annotations

from typing import Any

import httpx

from vidscope.adapters.llm._base import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    LlmCallContext,
    build_messages,
    call_with_retry,
    make_analysis,
    parse_llm_json,
)
from vidscope.domain import Analysis, AnalysisError, Transcript

__all__ = ["AnthropicAnalyzer"]


_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
_DEFAULT_MODEL = "claude-haiku-4-5"
_DEFAULT_API_VERSION = "2023-06-01"
_PROVIDER_NAME = "anthropic"
_MAX_TOKENS = 512


class AnthropicAnalyzer:
    """LLM analyzer backed by Anthropic's native messages API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        api_version: str = _DEFAULT_API_VERSION,
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise AnalysisError(
                "AnthropicAnalyzer requires a non-empty api_key — "
                "set VIDSCOPE_ANTHROPIC_API_KEY",
                retryable=False,
            )
        self._api_key = api_key.strip()
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_version = api_version
        self._timeout = timeout
        self._client = client

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    def analyze(self, transcript: Transcript) -> Analysis:
        """Send the transcript to Anthropic and return a domain Analysis."""
        # Reuse the shared message builder, then split system out.
        messages = build_messages(transcript)
        system_text = ""
        user_messages: list[dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                user_messages.append(msg)

        body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "temperature": 0.2,
            "system": system_text,
            "messages": user_messages,
        }
        ctx = LlmCallContext(
            method="POST",
            url=f"{self._base_url}/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": self._api_version,
                "Content-Type": "application/json",
            },
            json_body=body,
            timeout=self._timeout,
        )

        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            response = call_with_retry(client, ctx)
        finally:
            if self._client is None:
                client.close()

        try:
            payload = response.json()
        except ValueError as exc:
            raise AnalysisError(
                f"anthropic returned non-JSON response: {response.text[:200]}",
                cause=exc,
                retryable=False,
            ) from exc

        content_blocks = payload.get("content") or []
        if not isinstance(content_blocks, list) or not content_blocks:
            raise AnalysisError(
                "anthropic response missing 'content' array",
                retryable=False,
            )

        # Anthropic content is a list of typed blocks; we want the
        # first text block. Other types (tool_use, image) are skipped.
        text_chunks: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text") or ""
                if text:
                    text_chunks.append(text)

        if not text_chunks:
            raise AnalysisError(
                "anthropic response 'content' has no text blocks",
                retryable=False,
            )

        raw_content = "\n".join(text_chunks)
        parsed = parse_llm_json(raw_content)
        return make_analysis(parsed, transcript, provider=_PROVIDER_NAME)
