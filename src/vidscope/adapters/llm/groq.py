"""GroqAnalyzer — concrete LLM analyzer using Groq's cloud API.

Groq exposes an OpenAI-compatible chat-completion endpoint:
``POST https://api.groq.com/openai/v1/chat/completions``

This adapter is the M004/S01 reference implementation. The shared
helper :func:`vidscope.adapters.llm._base.run_openai_compatible` does
all the heavy lifting — this file just owns the auth + URL + model
defaults specific to Groq.
"""

from __future__ import annotations

import httpx

from vidscope.adapters.llm._base import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    run_openai_compatible,
)
from vidscope.domain import Analysis, AnalysisError, Transcript

__all__ = ["GroqAnalyzer"]


_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_MODEL = "llama-3.1-8b-instant"
_PROVIDER_NAME = "groq"


class GroqAnalyzer:
    """LLM analyzer backed by Groq's free/paid cloud."""

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
                "GroqAnalyzer requires a non-empty api_key — "
                "set VIDSCOPE_GROQ_API_KEY",
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
