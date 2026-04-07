"""NvidiaBuildAnalyzer — concrete LLM analyzer for the NVIDIA Build API.

NVIDIA Build (build.nvidia.com) exposes hosted LLM endpoints with an
OpenAI-compatible chat-completion schema:
``POST https://integrate.api.nvidia.com/v1/chat/completions``

API keys are issued via the NVIDIA Developer Program at
build.nvidia.com and prefixed ``nvapi-``. Free tier ships with 1000
inference credits at signup.

The shared helper :func:`vidscope.adapters.llm._base.run_openai_compatible`
does the network work — this file owns the URL + default model.
"""

from __future__ import annotations

import httpx

from vidscope.adapters.llm._base import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    run_openai_compatible,
)
from vidscope.domain import Analysis, AnalysisError, Transcript

__all__ = ["NvidiaBuildAnalyzer"]


_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
_DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"
_PROVIDER_NAME = "nvidia"


class NvidiaBuildAnalyzer:
    """LLM analyzer backed by NVIDIA Build hosted endpoints."""

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
                "NvidiaBuildAnalyzer requires a non-empty api_key — "
                "set VIDSCOPE_NVIDIA_API_KEY",
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
