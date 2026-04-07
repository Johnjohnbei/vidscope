"""OpenAIAnalyzer — concrete LLM analyzer for OpenAI's chat API.

OpenAI exposes the canonical chat-completion endpoint:
``POST https://api.openai.com/v1/chat/completions``

API keys start with ``sk-`` and are issued at platform.openai.com.
New accounts get a small amount of free credits, after which usage
is pay-per-token. The default model is ``gpt-4o-mini`` — OpenAI's
cheapest production model, suitable for short transcript analysis.

The shared helper :func:`vidscope.adapters.llm._base.run_openai_compatible`
does the network work — this file is the canonical example of "the
same shape every other OpenAI-compatible adapter follows".
"""

from __future__ import annotations

import httpx

from vidscope.adapters.llm._base import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    run_openai_compatible,
)
from vidscope.domain import Analysis, AnalysisError, Transcript

__all__ = ["OpenAIAnalyzer"]


_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"
_PROVIDER_NAME = "openai"


class OpenAIAnalyzer:
    """LLM analyzer backed by OpenAI's chat-completion API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise AnalysisError(
                "OpenAIAnalyzer requires a non-empty api_key — "
                "set VIDSCOPE_OPENAI_API_KEY",
                retryable=False,
            )
        self._api_key = api_key.strip()
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._client = client

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    def analyze(self, transcript: Transcript) -> Analysis:
        """Send the transcript through the shared OpenAI-compatible helper.

        The helper handles message building, JSON-mode request,
        retry/backoff, response parsing, and Analysis construction.
        Per-call client lifecycle: when the caller injected a client
        (tests), we never close it. Otherwise the temporary client
        we built is closed in the finally branch.
        """
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            return run_openai_compatible(
                client=client,
                base_url=self._base_url,
                api_key=self._api_key,
                model=self._model,
                transcript=transcript,
                provider_name=_PROVIDER_NAME,
                timeout=self._timeout,
            )
        finally:
            if self._client is None:
                client.close()
