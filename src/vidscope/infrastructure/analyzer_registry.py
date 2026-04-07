"""Analyzer registry — picks an Analyzer implementation by name.

Implements R010 (pluggable analyzer providers) by exposing a single
factory function ``build_analyzer(name)`` that maps a provider name
string to a concrete :class:`Analyzer` instance.

Currently registered:

- ``"heuristic"`` → :class:`HeuristicAnalyzer` (default, zero cost)
- ``"stub"`` → :class:`StubAnalyzer` (placeholder, only for tests)
- ``"groq"`` → :class:`GroqAnalyzer` (M004/S01, free tier via console.groq.com)
- ``"nvidia"`` → :class:`NvidiaBuildAnalyzer` (M004/S02)
- ``"openrouter"`` → :class:`OpenRouterAnalyzer` (M004/S02)
- ``"openai"`` → :class:`OpenAIAnalyzer` (M004/S02)
- ``"anthropic"`` → :class:`AnthropicAnalyzer` (M004/S02)

LLM providers read their API key from a per-provider environment
variable (e.g. ``VIDSCOPE_GROQ_API_KEY``) at factory invocation
time, not at module import time, so importing this module never
fails on missing keys. The factory raises :class:`ConfigError` only
if the user explicitly selects a provider whose key is missing.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Final

from vidscope.adapters.heuristic import HeuristicAnalyzer, StubAnalyzer
from vidscope.adapters.llm.anthropic import AnthropicAnalyzer
from vidscope.adapters.llm.groq import GroqAnalyzer
from vidscope.adapters.llm.nvidia_build import NvidiaBuildAnalyzer
from vidscope.adapters.llm.openai import OpenAIAnalyzer
from vidscope.adapters.llm.openrouter import OpenRouterAnalyzer
from vidscope.domain.errors import AnalysisError, ConfigError
from vidscope.ports import Analyzer

__all__ = ["KNOWN_ANALYZERS", "build_analyzer"]


# ---------------------------------------------------------------------------
# Per-provider env-var conventions and defaults
# ---------------------------------------------------------------------------

_ENV_GROQ_API_KEY = "VIDSCOPE_GROQ_API_KEY"
_ENV_GROQ_MODEL = "VIDSCOPE_GROQ_MODEL"
_DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"

_ENV_NVIDIA_API_KEY = "VIDSCOPE_NVIDIA_API_KEY"
_ENV_NVIDIA_MODEL = "VIDSCOPE_NVIDIA_MODEL"
_DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"

_ENV_OPENROUTER_API_KEY = "VIDSCOPE_OPENROUTER_API_KEY"
_ENV_OPENROUTER_MODEL = "VIDSCOPE_OPENROUTER_MODEL"
_DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

_ENV_OPENAI_API_KEY = "VIDSCOPE_OPENAI_API_KEY"
_ENV_OPENAI_MODEL = "VIDSCOPE_OPENAI_MODEL"
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

_ENV_ANTHROPIC_API_KEY = "VIDSCOPE_ANTHROPIC_API_KEY"
_ENV_ANTHROPIC_MODEL = "VIDSCOPE_ANTHROPIC_MODEL"
_DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"


def _build_groq() -> Analyzer:
    """Build a GroqAnalyzer from ``VIDSCOPE_GROQ_API_KEY`` + ``VIDSCOPE_GROQ_MODEL``."""
    api_key = os.environ.get(_ENV_GROQ_API_KEY, "").strip()
    if not api_key:
        raise ConfigError(
            f"groq analyzer requires {_ENV_GROQ_API_KEY} environment variable. "
            f"Get a free API key at https://console.groq.com"
        )
    model = (
        os.environ.get(_ENV_GROQ_MODEL, _DEFAULT_GROQ_MODEL).strip()
        or _DEFAULT_GROQ_MODEL
    )
    try:
        return GroqAnalyzer(api_key=api_key, model=model)
    except AnalysisError as exc:
        raise ConfigError(f"failed to build groq analyzer: {exc}") from exc


def _build_nvidia() -> Analyzer:
    """Build a NvidiaBuildAnalyzer from ``VIDSCOPE_NVIDIA_API_KEY`` + ``VIDSCOPE_NVIDIA_MODEL``."""
    api_key = os.environ.get(_ENV_NVIDIA_API_KEY, "").strip()
    if not api_key:
        raise ConfigError(
            f"nvidia analyzer requires {_ENV_NVIDIA_API_KEY} environment variable. "
            f"Get a free API key at https://build.nvidia.com (key prefixed nvapi-)"
        )
    model = (
        os.environ.get(_ENV_NVIDIA_MODEL, _DEFAULT_NVIDIA_MODEL).strip()
        or _DEFAULT_NVIDIA_MODEL
    )
    try:
        return NvidiaBuildAnalyzer(api_key=api_key, model=model)
    except AnalysisError as exc:
        raise ConfigError(f"failed to build nvidia analyzer: {exc}") from exc


def _build_openrouter() -> Analyzer:
    """Build an OpenRouterAnalyzer from env (``VIDSCOPE_OPENROUTER_API_KEY``)."""
    api_key = os.environ.get(_ENV_OPENROUTER_API_KEY, "").strip()
    if not api_key:
        raise ConfigError(
            f"openrouter analyzer requires {_ENV_OPENROUTER_API_KEY} env variable. "
            f"Get a free API key at https://openrouter.ai "
            f"(50 free requests/day, 1000/day with $10 in credits)"
        )
    model = (
        os.environ.get(_ENV_OPENROUTER_MODEL, _DEFAULT_OPENROUTER_MODEL).strip()
        or _DEFAULT_OPENROUTER_MODEL
    )
    try:
        return OpenRouterAnalyzer(api_key=api_key, model=model)
    except AnalysisError as exc:
        raise ConfigError(f"failed to build openrouter analyzer: {exc}") from exc


def _build_openai() -> Analyzer:
    """Build an OpenAIAnalyzer from ``VIDSCOPE_OPENAI_API_KEY`` + ``VIDSCOPE_OPENAI_MODEL``."""
    api_key = os.environ.get(_ENV_OPENAI_API_KEY, "").strip()
    if not api_key:
        raise ConfigError(
            f"openai analyzer requires {_ENV_OPENAI_API_KEY} environment variable. "
            f"Get an API key at https://platform.openai.com (pay-per-use after free credits)"
        )
    model = (
        os.environ.get(_ENV_OPENAI_MODEL, _DEFAULT_OPENAI_MODEL).strip()
        or _DEFAULT_OPENAI_MODEL
    )
    try:
        return OpenAIAnalyzer(api_key=api_key, model=model)
    except AnalysisError as exc:
        raise ConfigError(f"failed to build openai analyzer: {exc}") from exc


def _build_anthropic() -> Analyzer:
    """Build an AnthropicAnalyzer from env (``VIDSCOPE_ANTHROPIC_API_KEY``)."""
    api_key = os.environ.get(_ENV_ANTHROPIC_API_KEY, "").strip()
    if not api_key:
        raise ConfigError(
            f"anthropic analyzer requires {_ENV_ANTHROPIC_API_KEY} environment variable. "
            f"Get an API key at https://console.anthropic.com (pay-per-use)"
        )
    model = (
        os.environ.get(_ENV_ANTHROPIC_MODEL, _DEFAULT_ANTHROPIC_MODEL).strip()
        or _DEFAULT_ANTHROPIC_MODEL
    )
    try:
        return AnthropicAnalyzer(api_key=api_key, model=model)
    except AnalysisError as exc:
        raise ConfigError(f"failed to build anthropic analyzer: {exc}") from exc


_FACTORIES: Final[dict[str, Callable[[], Analyzer]]] = {
    "heuristic": HeuristicAnalyzer,
    "stub": StubAnalyzer,
    "groq": _build_groq,
    "nvidia": _build_nvidia,
    "openrouter": _build_openrouter,
    "openai": _build_openai,
    "anthropic": _build_anthropic,
}

#: Public read-only view of the registered analyzer names. Useful
#: for ``vidscope doctor`` or future ``vidscope analyzers list``.
KNOWN_ANALYZERS: Final[frozenset[str]] = frozenset(_FACTORIES.keys())


def build_analyzer(name: str) -> Analyzer:
    """Return an Analyzer instance for the given provider ``name``.

    Raises
    ------
    ConfigError
        If ``name`` is not a registered provider, or if the selected
        provider requires an environment variable that is missing.
    """
    factory = _FACTORIES.get(name)
    if factory is None:
        raise ConfigError(
            f"unknown analyzer provider: {name!r}. "
            f"Registered providers: {sorted(KNOWN_ANALYZERS)}"
        )
    return factory()
