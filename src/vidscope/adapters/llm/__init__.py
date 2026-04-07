"""LLM-backed analyzer adapters.

Each provider lives in its own file (one external SDK or HTTP client
per file, never two). The shared :mod:`._base` module supplies the
prompt template, JSON parser, and retry helper so every concrete
provider stays under ~100 lines.

Providers (M004):

- :class:`vidscope.adapters.llm.groq.GroqAnalyzer` — Groq cloud (S01)
- :class:`vidscope.adapters.llm.nvidia_build.NvidiaBuildAnalyzer` — NVIDIA Build (S02)
- :class:`vidscope.adapters.llm.openrouter.OpenRouterAnalyzer` — OpenRouter (S02)
- :class:`vidscope.adapters.llm.openai.OpenAIAnalyzer` — OpenAI (S02)
- :class:`vidscope.adapters.llm.anthropic.AnthropicAnalyzer` — Anthropic (S02)

The package is registered as a layer in :file:`.importlinter` and
must only be imported from :mod:`vidscope.infrastructure.analyzer_registry`.
The application, pipeline, ports, and domain layers never see it.
"""

from __future__ import annotations
