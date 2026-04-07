# M004: Pluggable LLM analyzers

## Vision
Users can opt into LLM-powered analysis by setting `VIDSCOPE_ANALYZER` to one of the supported providers (nvidia, groq, openrouter, openai, anthropic) and providing the matching API key. The heuristic remains the zero-cost default. Each provider lives in its own adapter file behind the existing `Analyzer` Protocol — zero changes to the pipeline, the use cases, or the CLI. Per-provider rate-limit handling, retry, cost guards.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | LLM adapter foundation: shared base + first concrete provider (Groq) | high | — | ✅ | VIDSCOPE_ANALYZER=groq with a stub HTTP client produces an Analysis row through the existing pipeline. |
| S02 | Remaining 4 providers (NVIDIA Build, OpenRouter, OpenAI, Anthropic) | medium | S01 | ✅ | All 5 LLM analyzers register and pass their unit tests. |
| S03 | Doctor integration, docs, verify-m004.sh, milestone closure | low | S02 | ✅ | vidscope doctor reports analyzer + key status. docs/analyzers.md is the user-facing reference. verify-m004.sh runs 9-10 steps green. |
