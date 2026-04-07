"""OpenRouterAnalyzer — concrete LLM analyzer for OpenRouter.

OpenRouter is an aggregator that provides a unified OpenAI-compatible
endpoint for hundreds of LLM providers:
``POST https://openrouter.ai/api/v1/chat/completions``

Free tier: 50 model API requests per day with no credits, 1000/day
once at least 10 credits have been purchased. 29 models tagged
``:free`` (e.g. ``meta-llama/llama-3.3-70b-instruct:free``).

OpenRouter supports two optional headers (``HTTP-Referer`` and
``X-Title``) that surface your app on the OpenRouter leaderboards.
We send them so VidScope is identifiable.

The shared helper :func:`vidscope.adapters.llm._base.run_openai_compatible`
does the network work — this file owns the URL + default model +
identification headers.
"""

from __future__ import annotations

import httpx

from vidscope.adapters.llm._base import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    run_openai_compatible,
)
from vidscope.domain import Analysis, AnalysisError, Transcript

__all__ = ["OpenRouterAnalyzer"]


_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
_PROVIDER_NAME = "openrouter"
_APP_REFERER = "https://github.com/Johnjohnbei/vidscope"
_APP_TITLE = "VidScope"


class OpenRouterAnalyzer:
    """LLM analyzer backed by OpenRouter's unified API."""

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
                "OpenRouterAnalyzer requires a non-empty api_key — "
                "set VIDSCOPE_OPENROUTER_API_KEY",
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
                extra_headers={
                    "HTTP-Referer": _APP_REFERER,
                    "X-Title": _APP_TITLE,
                },
            )
        finally:
            if self._client is None:
                client.close()
